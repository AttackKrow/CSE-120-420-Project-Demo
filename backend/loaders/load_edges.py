"""Bulk-load the generator's base Parquet files into PostgreSQL.

The loader intentionally stays standalone for the demo. It reads one Parquet
file at a time, applies the generator's documented duplicate rule in Python,
and sends the cleaned rows directly to PostgreSQL with COPY.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any

import psycopg
import pyarrow.parquet as pq
from psycopg import sql
from psycopg.types.json import Jsonb

EVENT_COLUMNS = (
    "id",
    "event_ts",
    "begin_ts",
    "end_ts",
    "segment_name",
    "segment_uuid",
    "operation_id",
    "in_lot_name",
    "in_lot_sequence",
    "in_lot_uuid",
    "in_material",
    "in_lot_status",
    "in_prev_segment",
    "out_lot_name",
    "out_lot_sequence",
    "out_lot_uuid",
    "out_material",
    "out_lot_status",
    "location",
    "location_type",
    "equipment_path",
    "operator",
    "work_order_id",
    "disposition",
    "disposition_codes",
    "ext_system_ref",
    "qty_in",
    "qty_out",
    "qty_net",
    "qty_available",
    "qty_scheduled",
    "unit",
    "in_properties",
    "out_properties",
    "recipe_json",
)

JSON_COLUMNS = {
    "disposition_codes",
    "in_properties",
    "out_properties",
    "recipe_json",
}

DEDUPLICATION_COLUMNS = (
    "in_lot_uuid",
    "out_lot_uuid",
    "segment_uuid",
    "begin_ts",
)


BACKEND_DIRECTORY = Path(__file__).parents[1]


def resolve_base_directory(path: Path) -> Path:
    """Accept either a scenario output directory or its base/ directory."""
    path = path.resolve()
    base_directory = path if path.name == "base" else path / "base"

    if not base_directory.is_dir():
        raise FileNotFoundError(f"Base directory not found: {base_directory}")

    return base_directory


def read_and_deduplicate(parquet_path: Path) -> tuple[list[dict[str, Any]], int]:
    """Read one file and keep the preferred row for each documented key."""
    table = pq.read_table(parquet_path)
    missing_columns = set(EVENT_COLUMNS) - set(table.column_names)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"{parquet_path} is missing columns: {missing}")

    raw_rows = table.select(EVENT_COLUMNS).to_pylist()
    selected: dict[tuple[Any, ...], dict[str, Any]] = {}

    for row in raw_rows:
        key = tuple(row[column] for column in DEDUPLICATION_COLUMNS)
        current = selected.get(key)

        # Prefer a populated in_prev_segment, then the lowest row id.
        row_rank = (row["in_prev_segment"] is None, row["id"])
        if current is None:
            selected[key] = row
        else:
            current_rank = (
                current["in_prev_segment"] is None,
                current["id"],
            )
            if row_rank < current_rank:
                selected[key] = row

    # Stable ordering makes the loaded table easier to inspect and reproduce.
    deduplicated_rows = sorted(selected.values(), key=lambda row: row["id"])
    return deduplicated_rows, len(raw_rows)


def postgres_row(row: dict[str, Any]) -> tuple[Any, ...]:
    """Convert JSON text from Parquet into values psycopg can send to JSONB."""
    values: list[Any] = []

    for column in EVENT_COLUMNS:
        value = row[column]
        if column in JSON_COLUMNS and value is not None:
            if isinstance(value, str):
                value = json.loads(value)
            value = Jsonb(value)
        values.append(value)

    return tuple(values)


def load_base(base_path: Path, database_url: str) -> tuple[int, int]:
    base_directory = resolve_base_directory(base_path)
    parquet_files = sorted(base_directory.rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No Parquet files found in {base_directory}")

    schema_path = BACKEND_DIRECTORY / "app" / "db" / "schema.sql"
    column_list = sql.SQL(", ").join(map(sql.Identifier, EVENT_COLUMNS))
    copy_statement = sql.SQL(
        "COPY genealogy_edges ({}) FROM STDIN"
    ).format(column_list)

    total_raw = 0
    total_loaded = 0

    # The connection context makes the complete base load one transaction. If
    # any file fails, PostgreSQL rolls the load back instead of leaving a
    # partially populated base dataset.
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute(schema_path.read_text(encoding="utf-8"))
        cursor.execute("SELECT EXISTS (SELECT 1 FROM genealogy_edges LIMIT 1)")
        if cursor.fetchone()[0]:
            raise RuntimeError(
                "genealogy_edges is not empty; base loading requires a fresh table"
            )

        for parquet_file in parquet_files:
            rows, raw_count = read_and_deduplicate(parquet_file)

            with cursor.copy(copy_statement) as copy:
                for row in rows:
                    copy.write_row(postgres_row(row))

            duplicate_count = raw_count - len(rows)
            total_raw += raw_count
            total_loaded += len(rows)
            print(
                f"{parquet_file.name}: read {raw_count:,}, "
                f"removed {duplicate_count:,}, loaded {len(rows):,}"
            )

    return total_loaded, total_raw - total_loaded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load deduplicated mes-genealogy-synth base data into PostgreSQL"
    )
    parser.add_argument(
        "--dataset",
        choices=("smoke", "official"),
        default="smoke",
        help="Dataset beneath backend/out/ to load (default: smoke)",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not configured")

    dataset_directory = BACKEND_DIRECTORY / "out" / args.dataset
    loaded, duplicates = load_base(dataset_directory, database_url)
    print(f"Finished: loaded {loaded:,} events; removed {duplicates:,} duplicates")


if __name__ == "__main__":
    main()