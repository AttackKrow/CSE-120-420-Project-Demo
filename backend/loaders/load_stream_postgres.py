"""Incrementally load generated stream data into PostgreSQL.

Each stream Parquet file is processed in its own transaction:

1. Read and deduplicate the generated events.
2. Insert previously unseen events into genealogy_edges.
3. Incrementally update genealogy_closure for the new edges.

The edge and closure updates commit together, so the two tables cannot be left
out of sync if processing a stream file fails.
"""

import argparse
import os
from pathlib import Path
from typing import Any

import psycopg
from loaders.load_edges import (
    BACKEND_DIRECTORY,
    EVENT_COLUMNS,
    postgres_row,
    read_and_deduplicate,
)
from psycopg import sql

UPDATE_CLOSURE_SQL = """
WITH
ancestors(ancestor_uuid, distance) AS (
    SELECT
        %s::TEXT,
        0

    UNION ALL

    SELECT
        ancestor_uuid,
        distance
    FROM genealogy_closure
    WHERE descendent_uuid = %s
),
descendants(descendent_uuid, distance) AS (
    SELECT
        %s::TEXT,
        0

    UNION ALL

    SELECT
        descendent_uuid,
        distance
    FROM genealogy_closure
    WHERE ancestor_uuid = %s
),
new_paths AS (
    SELECT
        ancestors.ancestor_uuid,
        descendants.descendent_uuid,
        ancestors.distance + 1 + descendants.distance AS distance
    FROM ancestors
    CROSS JOIN descendants
    WHERE ancestors.ancestor_uuid <> descendants.descendent_uuid
)
INSERT INTO genealogy_closure (
    ancestor_uuid,
    descendent_uuid,
    distance
)
SELECT
    ancestor_uuid,
    descendent_uuid,
    MIN(distance)
FROM new_paths
GROUP BY
    ancestor_uuid,
    descendent_uuid
ON CONFLICT (ancestor_uuid, descendent_uuid)
DO UPDATE SET
    distance = EXCLUDED.distance
WHERE genealogy_closure.distance > EXCLUDED.distance;
"""


def resolve_stream_files(stream_path: Path) -> list[Path]:
    """Return the stream Parquet files represented by a file or directory."""
    stream_path = stream_path.resolve()

    if stream_path.is_file():
        if stream_path.suffix.lower() != ".parquet":
            raise ValueError(f"Expected a Parquet file: {stream_path}")

        return [stream_path]

    if not stream_path.is_dir():
        raise FileNotFoundError(f"Stream path not found: {stream_path}")

    parquet_files = sorted(stream_path.rglob("*.parquet"))

    if not parquet_files:
        raise FileNotFoundError(
            f"No Parquet files found beneath {stream_path}"
        )

    return parquet_files


def check_initial_state(connection: psycopg.Connection[Any]) -> None:
    """Ensure the base closure table was built before stream ingestion."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM genealogy_edges
                WHERE in_lot_uuid IS NOT NULL
                  AND out_lot_uuid IS NOT NULL
            )
            """
        )
        has_edges = cursor.fetchone()[0]

        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM genealogy_closure)"
        )
        has_closure = cursor.fetchone()[0]

    if has_edges and not has_closure:
        raise RuntimeError(
            "genealogy_edges contains base edges, but genealogy_closure "
            "is empty. Run `uv run python -m loaders.load_closure` first."
        )


def update_closure_for_edge(
    cursor: psycopg.Cursor[Any],
    ancestor_uuid: str,
    descendent_uuid: str,
) -> int:
    """Add all closure relationships introduced by one new direct edge."""
    cursor.execute(
        UPDATE_CLOSURE_SQL,
        (
            ancestor_uuid,
            ancestor_uuid,
            descendent_uuid,
            descendent_uuid,
        ),
    )

    return cursor.rowcount


def load_stream_file(
    connection: psycopg.Connection[Any],
    parquet_path: Path,
) -> tuple[int, int, int, int]:
    """Load one stream file and update both tables atomically."""
    rows, raw_count = read_and_deduplicate(parquet_path)
    duplicate_count = raw_count - len(rows)

    column_list = sql.SQL(", ").join(
        map(sql.Identifier, EVENT_COLUMNS)
    )

    copy_statement = sql.SQL(
        "COPY staging_stream_events ({columns}) FROM STDIN"
    ).format(columns=column_list)

    insert_statement = sql.SQL(
        """
        INSERT INTO genealogy_edges ({columns})
        SELECT {columns}
        FROM staging_stream_events
        ON CONFLICT DO NOTHING
        RETURNING in_lot_uuid, out_lot_uuid
        """
    ).format(columns=column_list)

    # One transaction per file means an hourly stream batch is either applied
    # completely to both tables or not applied at all.
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
                CREATE TEMP TABLE staging_stream_events
                (LIKE genealogy_edges INCLUDING DEFAULTS)
                ON COMMIT DROP
                """
        )

        with cursor.copy(copy_statement) as copy:
            for row in rows:
                copy.write_row(postgres_row(row))

        cursor.execute(insert_statement)
        inserted_rows = cursor.fetchall()
        inserted_count = len(inserted_rows)

        closure_rows_changed = 0

        for in_lot_uuid, out_lot_uuid in inserted_rows:
            # Creation and disposal events do not form graph edges.
            if in_lot_uuid is None or out_lot_uuid is None:
                continue

            closure_rows_changed += update_closure_for_edge(
                cursor,
                ancestor_uuid=in_lot_uuid,
                descendent_uuid=out_lot_uuid,
            )

    return (
        raw_count,
        duplicate_count,
        inserted_count,
        closure_rows_changed,
    )


def load_stream(
    stream_path: Path,
    database_url: str,
) -> tuple[int, int, int, int]:
    """Process one stream file or every Parquet file under a directory."""
    parquet_files = resolve_stream_files(stream_path)
    schema_path = BACKEND_DIRECTORY / "app" / "db" / "schema.sql"

    total_raw = 0
    total_duplicates = 0
    total_inserted = 0
    total_closure_changed = 0

    with psycopg.connect(database_url) as connection:
        # Make sure the expected tables and indexes exist before processing.
        with connection.cursor() as cursor:
            cursor.execute(schema_path.read_text(encoding="utf-8"))

        connection.commit()
        check_initial_state(connection)
        connection.commit()

        for parquet_file in parquet_files:
            (
                raw_count,
                duplicate_count,
                inserted_count,
                closure_rows_changed,
            ) = load_stream_file(connection, parquet_file)

            total_raw += raw_count
            total_duplicates += duplicate_count
            total_inserted += inserted_count
            total_closure_changed += closure_rows_changed

            print(
                f"{parquet_file}: "
                f"read {raw_count:,}, "
                f"removed {duplicate_count:,} duplicates, "
                f"inserted {inserted_count:,} events, "
                f"changed {closure_rows_changed:,} closure relationships"
            )

    return (
        total_raw,
        total_duplicates,
        total_inserted,
        total_closure_changed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Incrementally load mes-genealogy-synth stream data into "
            "genealogy_edges and genealogy_closure"
        )
    )
    parser.add_argument(
        "stream_path",
        nargs="?",
        type=Path,
        help=(
            "A stream Parquet file or directory. If omitted, the loader "
            "uses backend/out/<dataset>/stream."
        ),
    )
    parser.add_argument(
        "--dataset",
        default="smoke",
        help=(
            "Dataset beneath backend/out/ when stream_path is omitted "
            "(default: smoke)"
        ),
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not configured")

    stream_path = args.stream_path
    if stream_path is None:
        stream_path = (
            BACKEND_DIRECTORY
            / "out"
            / args.dataset
            / "stream"
        )

    (
        raw_count,
        duplicate_count,
        inserted_count,
        closure_rows_changed,
    ) = load_stream(stream_path, database_url)

    print(
        "Finished: "
        f"read {raw_count:,} events; "
        f"removed {duplicate_count:,} duplicates; "
        f"inserted {inserted_count:,} new events; "
        f"changed {closure_rows_changed:,} closure relationships"
    )


if __name__ == "__main__":
    main()