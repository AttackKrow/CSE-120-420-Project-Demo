"""Build the PostgreSQL closure table from the loaded genealogy edge table."""

import os
from pathlib import Path

import psycopg

BACKEND_DIRECTORY = Path(__file__).parents[1]

BUILD_CLOSURE_SQL = """
WITH RECURSIVE
    direct_edges AS MATERIALIZED (
        SELECT DISTINCT
            in_lot_uuid AS ancestor_uuid,
            out_lot_uuid AS descendent_uuid
        FROM genealogy_edges
        WHERE in_lot_uuid IS NOT NULL
          AND out_lot_uuid IS NOT NULL
    ),
    paths(ancestor_uuid, descendent_uuid, distance) AS (
        SELECT
            ancestor_uuid,
            descendent_uuid,
            1
        FROM direct_edges

        UNION

        SELECT
            paths.ancestor_uuid,
            direct_edges.descendent_uuid,
            paths.distance + 1
        FROM paths
        JOIN direct_edges
          ON direct_edges.ancestor_uuid = paths.descendent_uuid
    )
INSERT INTO genealogy_closure (
    ancestor_uuid,
    descendent_uuid,
    distance
)
SELECT
    ancestor_uuid,
    descendent_uuid,
    MIN(distance) AS distance
FROM paths
GROUP BY ancestor_uuid, descendent_uuid;
"""


def load_closure(database_url: str) -> int:
    """Populate an empty closure table from genealogy_edges."""
    schema_path = BACKEND_DIRECTORY / "app" / "db" / "schema.sql"

    # The connection context makes the entire build atomic. If closure-table
    # construction fails, PostgreSQL rolls back all inserted closure rows.
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(schema_path.read_text(encoding="utf-8"))

        cursor.execute("SELECT EXISTS (SELECT 1 FROM genealogy_edges LIMIT 1)")
        if not cursor.fetchone()[0]:
            raise RuntimeError(
                "genealogy_edges is empty; run the edge base loader first"
            )

        cursor.execute(
            "SELECT EXISTS (SELECT 1 FROM genealogy_closure LIMIT 1)"
        )
        if cursor.fetchone()[0]:
            raise RuntimeError(
                "genealogy_closure is not empty; truncate it before rebuilding"
            )

        cursor.execute(BUILD_CLOSURE_SQL)

        cursor.execute("SELECT COUNT(*) FROM genealogy_closure")
        closure_rows = cursor.fetchone()[0]

    return closure_rows


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not configured")

    closure_rows = load_closure(database_url)
    print(f"Finished: loaded {closure_rows:,} closure relationships")


if __name__ == "__main__":
    main()
