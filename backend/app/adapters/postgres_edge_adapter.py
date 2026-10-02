import os

import psycopg
from app.adapters.adapter import Adapter

ANCESTORS_QUERY = """
    WITH RECURSIVE ancestors(lot_uuid, depth, path) AS (
        SELECT
            in_lot_uuid,
            1,
            ARRAY[out_lot_uuid, in_lot_uuid]
        FROM genealogy_edges
        WHERE out_lot_uuid = %s

        UNION ALL

        SELECT
            edge.in_lot_uuid,
            ancestors.depth + 1,
            ancestors.path || edge.in_lot_uuid
        FROM genealogy_edges AS edge
        JOIN ancestors
            ON edge.out_lot_uuid = ancestors.lot_uuid
        WHERE ancestors.depth < %s
          AND NOT edge.in_lot_uuid = ANY(ancestors.path)
    )
    SELECT
        lot_uuid,
        MIN(depth) AS minimum_depth
    FROM ancestors
    GROUP BY lot_uuid
    ORDER BY minimum_depth, lot_uuid;
"""


DESCENDANTS_QUERY = """
    WITH RECURSIVE descendants(lot_uuid, depth, path) AS (
        SELECT
            out_lot_uuid,
            1,
            ARRAY[in_lot_uuid, out_lot_uuid]
        FROM genealogy_edges
        WHERE in_lot_uuid = %s

        UNION ALL

        SELECT
            edge.out_lot_uuid,
            descendants.depth + 1,
            descendants.path || edge.out_lot_uuid
        FROM genealogy_edges AS edge
        JOIN descendants
            ON edge.in_lot_uuid = descendants.lot_uuid
        WHERE descendants.depth < %s
          AND NOT edge.out_lot_uuid = ANY(descendants.path)
    )
    SELECT
        lot_uuid,
        MIN(depth) AS minimum_depth
    FROM descendants
    GROUP BY lot_uuid
    ORDER BY minimum_depth, lot_uuid;
"""


class PostgresEdgeAdapter(Adapter):
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.environ["DATABASE_URL"]

    async def _run_traversal(
        self,
        query: str,
        lot_uuid: str,
        max_depth: int,
    ) -> list[str]:
        async with await psycopg.AsyncConnection.connect(
            self.database_url
        ) as connection, connection.cursor() as cursor:
            await cursor.execute(
                query,
                (lot_uuid, max_depth),
            )
            rows = await cursor.fetchall()

        return [row[0] for row in rows]

    async def get_ancestors(
        self,
        lot_uuid: str,
        max_depth: int = 20,
    ) -> list[str]:
        return await self._run_traversal(
            ANCESTORS_QUERY,
            lot_uuid,
            max_depth,
        )

    async def get_descendants(
        self,
        lot_uuid: str,
        max_depth: int = 20,
    ) -> list[str]:
        return await self._run_traversal(
            DESCENDANTS_QUERY,
            lot_uuid,
            max_depth,
        )