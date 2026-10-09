"""Load the generator's base Parquet files into Neo4j.

Reads the same files as load_edges.py (backend/out/<dataset>/base) and removes duplicates
with the same function, so Neo4j and PostgreSQL hold identical data.

Graph model:
    (:Lot {lot_id, lot_name, sequence, material, status,
           segment_name, segment_uuid, equipment_path, location, location_type,
           operator, begin_ts})
    (:Lot)-[:USED_IN {event_id, segment_name, begin_ts, qty_in}]->(:Lot)

Neo4j settings come from .env: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE.
"""

import argparse
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

from loaders.load_edges import BACKEND_DIRECTORY, read_and_deduplicate, resolve_base_directory

BATCH_SIZE = 5_000

SCHEMA = [
    "CREATE CONSTRAINT lot_id IF NOT EXISTS FOR (l:Lot) REQUIRE l.lot_id IS UNIQUE",
    "CREATE INDEX lot_name IF NOT EXISTS FOR (l:Lot) ON (l.lot_name)",
    "CREATE INDEX lot_equipment_time IF NOT EXISTS FOR (l:Lot) ON (l.equipment_path, l.begin_ts)",
    "CREATE INDEX lot_segment_time IF NOT EXISTS FOR (l:Lot) ON (l.segment_name, l.begin_ts)",
]


MERGE_INPUT_STATES = """
UNWIND $rows AS row
MERGE (lot:Lot {lot_id: row.lot_id})
ON CREATE SET lot.lot_name = row.lot_name, lot.sequence = row.sequence,
              lot.material = row.material, lot.status = row.status
"""

MERGE_OUTPUT_STATES = """
UNWIND $rows AS row
MERGE (lot:Lot {lot_id: row.lot_id})
SET lot += row
"""

MERGE_USED_IN = """
UNWIND $rows AS row
MATCH (input:Lot {lot_id: row.in_lot_id})
MATCH (output:Lot {lot_id: row.out_lot_id})
MERGE (input)-[edge:USED_IN]->(output)
SET edge.event_id = row.event_id, edge.segment_name = row.segment_name,
    edge.begin_ts = row.begin_ts, edge.qty_in = row.qty_in
"""

SET_DISPOSALS = """
UNWIND $rows AS row
MATCH (lot:Lot {lot_id: row.lot_id})
SET lot.disposal_equipment_path = row.equipment_path, lot.disposal_ts = row.begin_ts
"""

COUNT_GRAPH = "RETURN COUNT { (:Lot) } AS lots, COUNT { ()-[:USED_IN]->() } AS used_in"


def split_events(
    rows: list[dict[str, Any]], include_properties: bool
) -> dict[str, list[dict[str, Any]]]:
    """Turn deduplicated event rows into the rows each Cypher statement expects."""
    parts: dict[str, list[dict[str, Any]]] = {
        "inputs": [], "outputs": [], "used_in": [], "disposals": [],
    }
    for row in rows:
        has_input = row["in_lot_uuid"] is not None
        has_output = row["out_lot_uuid"] is not None

        if has_input:
            parts["inputs"].append({
                "lot_id": row["in_lot_uuid"],
                "lot_name": row["in_lot_name"],
                "sequence": row["in_lot_sequence"],
                "material": row["in_material"],
                "status": row["in_lot_status"],
            })
        if has_output:
            output = {
                "lot_id": row["out_lot_uuid"],
                "lot_name": row["out_lot_name"],
                "sequence": row["out_lot_sequence"],
                "material": row["out_material"],
                "status": row["out_lot_status"],
                "segment_name": row["segment_name"],
                "segment_uuid": row["segment_uuid"],
                "equipment_path": row["equipment_path"],
                "location": row["location"],
                "location_type": row["location_type"],
                "operator": row["operator"],
                "begin_ts": row["begin_ts"],
            }
            if include_properties:
                output["properties"] = row["out_properties"]
                output["recipe"] = row["recipe_json"]
            parts["outputs"].append(output)
        if has_input and has_output:
            parts["used_in"].append({
                "in_lot_id": row["in_lot_uuid"],
                "out_lot_id": row["out_lot_uuid"],
                "event_id": row["id"],
                "segment_name": row["segment_name"],
                "begin_ts": row["begin_ts"],
                "qty_in": row["qty_in"],
            })
        if has_input and not has_output:
            parts["disposals"].append({
                "lot_id": row["in_lot_uuid"],
                "equipment_path": row["equipment_path"],
                "begin_ts": row["begin_ts"],
            })
    return parts


def run_in_batches(driver: Driver, database: str, query: str, rows: list[dict[str, Any]]) -> None:
    for start in range(0, len(rows), BATCH_SIZE):
        driver.execute_query(query, rows=rows[start:start + BATCH_SIZE], database_=database)


def wipe(driver: Driver, database: str) -> None:
    """Delete every node and relationship, a batch at a time."""
    deleted = 0
    while True:
        records, _, _ = driver.execute_query(
            "MATCH (n) WITH n LIMIT 10000 DETACH DELETE n RETURN count(*) AS deleted",
            database_=database,
        )
        if records[0]["deleted"] == 0:
            break
        deleted += records[0]["deleted"]
    print(f"Deleted {deleted:,} nodes")


def load_base(base_path: Path, driver: Driver, database: str, include_properties: bool) -> None:
    base_directory = resolve_base_directory(base_path)
    parquet_files = sorted(base_directory.rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No Parquet files found in {base_directory}")

    for statement in SCHEMA:
        driver.execute_query(statement, database_=database)

    total_raw = total_loaded = 0
    for parquet_file in parquet_files:
        rows, raw_count = read_and_deduplicate(parquet_file)
        parts = split_events(rows, include_properties)

        run_in_batches(driver, database, MERGE_INPUT_STATES, parts["inputs"])
        run_in_batches(driver, database, MERGE_OUTPUT_STATES, parts["outputs"])
        run_in_batches(driver, database, MERGE_USED_IN, parts["used_in"])
        run_in_batches(driver, database, SET_DISPOSALS, parts["disposals"])

        total_raw += raw_count
        total_loaded += len(rows)
        print(
            f"{parquet_file.name}: read {raw_count:,}, "
            f"removed {raw_count - len(rows):,}, loaded {len(rows):,}"
        )

    print(f"Loaded {total_loaded:,} events; removed {total_raw - total_loaded:,} duplicates")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load deduplicated mes-genealogy-synth base data into Neo4j"
    )
    parser.add_argument(
        "--dataset",
        choices=("smoke", "official"),
        default="smoke",
        help="Dataset beneath backend/out/ to load (default: smoke)",
    )
    parser.add_argument("--wipe", action="store_true", help="delete everything in Neo4j first")
    parser.add_argument(
        "--properties", action="store_true",
        help="also store each state's properties and recipe JSON (as text)",
    )
    args = parser.parse_args()

    load_dotenv()
    uri = os.environ.get("NEO4J_URI")
    if not uri:
        raise SystemExit("NEO4J_URI is not configured (set it in backend/.env)")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    start = time.time()
    with GraphDatabase.driver(
        uri, auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"])
    ) as driver:
        driver.verify_connectivity()
        if args.wipe:
            wipe(driver, database)
        else:
            records, _, _ = driver.execute_query(COUNT_GRAPH, database_=database)
            if records[0]["lots"]:
                raise SystemExit(
                    f"Neo4j already holds {records[0]['lots']:,} Lot nodes; "
                    "re-run with --wipe to replace them"
                )

        load_base(BACKEND_DIRECTORY / "out" / args.dataset, driver, database, args.properties)

        records, _, _ = driver.execute_query(COUNT_GRAPH, database_=database)
        print(
            f"Neo4j now holds {records[0]['lots']:,} Lot nodes and "
            f"{records[0]['used_in']:,} USED_IN relationships ({time.time() - start:.0f} s)"
        )


if __name__ == "__main__":
    main()
