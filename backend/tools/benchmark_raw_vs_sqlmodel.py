import argparse
import asyncio
import os
import statistics
import time

import psycopg

# CURRENT IMPLEMENTATION: SQLModel ORM branch.
from app.adapters.postgres_closure_adapter import PostgresClosureAdapter
from app.adapters.postgres_edge_adapter import PostgresEdgeAdapter
from app.db.session import get_engine, get_session_factory


# OLD IMPLEMENTATION: these queries come from the main branch adapters.
OLD_EDGE_ANCESTORS = """
    WITH RECURSIVE ancestors(lot_uuid, depth, path) AS (
        SELECT in_lot_uuid, 1, ARRAY[out_lot_uuid, in_lot_uuid]
        FROM genealogy_edges
        WHERE out_lot_uuid = %s
        UNION ALL
        SELECT edge.in_lot_uuid, ancestors.depth + 1,
            ancestors.path || edge.in_lot_uuid
        FROM genealogy_edges AS edge
        JOIN ancestors ON edge.out_lot_uuid = ancestors.lot_uuid
        WHERE ancestors.depth < %s
        AND NOT edge.in_lot_uuid = ANY(ancestors.path)
    )
    SELECT lot_uuid, MIN(depth)
    FROM ancestors
    GROUP BY lot_uuid
    ORDER BY MIN(depth), lot_uuid;
"""

OLD_EDGE_DESCENDANTS = """
    WITH RECURSIVE descendants(lot_uuid, depth, path) AS (
        SELECT out_lot_uuid, 1, ARRAY[in_lot_uuid, out_lot_uuid]
        FROM genealogy_edges
        WHERE in_lot_uuid = %s
        UNION ALL
        SELECT edge.out_lot_uuid, descendants.depth + 1,
            descendants.path || edge.out_lot_uuid
        FROM genealogy_edges AS edge
        JOIN descendants ON edge.in_lot_uuid = descendants.lot_uuid
        WHERE descendants.depth < %s
        AND NOT edge.out_lot_uuid = ANY(descendants.path)
    )
    SELECT lot_uuid, MIN(depth)
    FROM descendants
    GROUP BY lot_uuid
    ORDER BY MIN(depth), lot_uuid;
"""

OLD_CLOSURE_ANCESTORS = """
    SELECT ancestor_uuid
    FROM genealogy_closure
    WHERE descendent_uuid = %s AND distance <= %s
    ORDER BY distance, ancestor_uuid;
"""

OLD_CLOSURE_DESCENDANTS = """
    SELECT descendent_uuid
    FROM genealogy_closure
    WHERE ancestor_uuid = %s AND distance <= %s
    ORDER BY distance, descendent_uuid;
"""


# OLD IMPLEMENTATION: run one raw psycopg query, like main.
async def run_old_query(query, database_url, lot_uuid, max_depth):
    async with await psycopg.AsyncConnection.connect(database_url) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(query, (lot_uuid, max_depth))
            rows = await cursor.fetchall()
    return [row[0] for row in rows]


def percentile_95(times):
    return sorted(times)[int(len(times) * 0.95)]

async def run_reused_query(connection, query, lot_uuid, max_depth):
    # raw SQL using one reused database connection.
    async with connection.cursor() as cursor:
        await cursor.execute(query, (lot_uuid, max_depth))
        rows = await cursor.fetchall()

    await connection.commit()
    return [row[0] for row in rows]

async def benchmark(
    name,
    old_query,
    current_call,
    database_url,
    lot_uuid,
    max_depth,
    iterations,
    warmups,
):
    async with await psycopg.AsyncConnection.connect(database_url) as connection:
        # OLD IMPLEMENTATION: main branch opens a new connection per query.
        old_result = await run_old_query(
            old_query,
            database_url,
            lot_uuid,
            max_depth,
        )

        # OLD IMPLEMENTATION w/ raw SQL with a reused connection.
        reused_result = await run_reused_query(
            connection,
            old_query,
            lot_uuid,
            max_depth,
        )

        # CURRENT IMPLEMENTATION: SQLModel ORM adapter.
        current_result = await current_call()

        if old_result != reused_result or old_result != current_result:
            raise RuntimeError(
                f"{name}: old and current results do not match"
            )

        # warm up before recording timings.
        for _ in range(warmups):
            await run_old_query(
                old_query,
                database_url,
                lot_uuid,
                max_depth,
            )
            await run_reused_query(
                connection,
                old_query,
                lot_uuid,
                max_depth,
            )
            await current_call()

        old_times = []
        reused_times = []
        current_times = []

        for _ in range(iterations):
            # OLD IMPLEMENTATION: new connection every query.
            start = time.perf_counter()
            await run_old_query(
                old_query,
                database_url,
                lot_uuid,
                max_depth,
            )
            old_times.append((time.perf_counter() - start) * 1000)

            # OLD IMPLEMENTATION w/ raw SQL with a reused connection.
            start = time.perf_counter()
            await run_reused_query(
                connection,
                old_query,
                lot_uuid,
                max_depth,
            )
            reused_times.append((time.perf_counter() - start) * 1000)

            # CURRENT IMPLEMENTATION: SQLModel ORM.
            start = time.perf_counter()
            await current_call()
            current_times.append((time.perf_counter() - start) * 1000)

        print(f"\n{name} ({len(old_result)} rows)")

        print(
            " Old raw SQL (new connection): "
            f"Median {statistics.median(old_times):.3f} ms, "
            f"95% of queries took: {percentile_95(old_times):.3f} ms"
        )

        print(
            " Old raw SQL (reused connection): "
            f"Median {statistics.median(reused_times):.3f} ms, "
            f"95% of queries took: {percentile_95(reused_times):.3f} ms"
        )

        print(
            " Current SQLModel ORM: "
            f"Median {statistics.median(current_times):.3f} ms, "
            f"95% of queries took: {percentile_95(current_times):.3f} ms"
        )

async def main(args):
    database_url = os.environ["DATABASE_URL"]
    edge = PostgresEdgeAdapter()
    closure = PostgresClosureAdapter()
    session_factory = get_session_factory()

    # CURRENT IMPLEMENTATION: call the SQLModel edge adapter with a session.
    async def current_ancestors():
        async with session_factory() as session:
            return await edge.get_ancestors(
                args.lot_uuid, args.max_depth, session=session
            )

    async def current_descendants():
        async with session_factory() as session:
            return await edge.get_descendants(
                args.lot_uuid, args.max_depth, session=session
            )

    # CURRENT IMPLEMENTATION: call the SQLModel closure adapter with a session.
    async def current_closure_ancestors():
        async with session_factory() as session:
            return await closure.get_ancestors(
                args.lot_uuid, args.max_depth, session=session
            )

    async def current_closure_descendants():
        async with session_factory() as session:
            return await closure.get_descendants(
                args.lot_uuid, args.max_depth, session=session
            )

    tests = [
        ("recursive ancestors", OLD_EDGE_ANCESTORS, current_ancestors),
        ("recursive descendants", OLD_EDGE_DESCENDANTS, current_descendants),
        ("closure ancestors", OLD_CLOSURE_ANCESTORS, current_closure_ancestors),
        ("closure descendants", OLD_CLOSURE_DESCENDANTS, current_closure_descendants),
    ]

    for name, old_query, current_call in tests:
        await benchmark(
            name, old_query, current_call, database_url, args.lot_uuid,
            args.max_depth, args.iterations, args.warmups
        )

    await get_engine().dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lot-uuid", default=os.getenv("LOT_UUID"))
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--warmups", type=int, default=25)
    options = parser.parse_args()

    if not options.lot_uuid:
        parser.error("set LOT_UUID or use --lot-uuid")

    asyncio.run(main(options))

