"""Incrementally load generated stream data into Neo4j.

The Neo4j counterpart of the postgres stream loader. Each stream Parquet file (one per
simulated hour) is processed in its own transaction:

1. Read and deduplicate the generated events (the same function as the base loaders).
2. Add the new lot states and USED_IN relationships with the same Cypher as
   load_neo4j.py.

A file is either applied completely or not at all. MERGE never duplicates anything,
so files that were already loaded are safe to rerun. Unlike the closure table, there
is nothing to recompute, Neo4j follows the new relationships at query time.

"""

import argparse
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase, ManagedTransaction

from loaders.load_edges import BACKEND_DIRECTORY, read_and_deduplicate
from loaders.load_neo4j import (
    BATCH_SIZE,
    COUNT_GRAPH,
    MERGE_INPUT_STATES,
    MERGE_OUTPUT_STATES,
    MERGE_USED_IN,
    SCHEMA,
    SET_DISPOSALS,
    split_events,
)
from loaders.load_stream_postgres import resolve_stream_files

# Same order as the base loader: inputs before outputs, so a state that is both keeps
# its producing event's details; relationships once both ends exist.
STEPS = (
    (MERGE_INPUT_STATES, "inputs"),
    (MERGE_OUTPUT_STATES, "outputs"),
    (MERGE_USED_IN, "used_in"),
    (SET_DISPOSALS, "disposals"),
)


def apply_events(tx: ManagedTransaction, parts: dict[str, list[dict[str, Any]]]) -> tuple[int, int]:
    """Run every statement for one file inside one transaction.

    Returns the number of Lot nodes and USED_IN relationships that were new.
    """
    lots_added = links_added = 0
    for query, key in STEPS:
        rows = parts[key]
        for start in range(0, len(rows), BATCH_SIZE):
            counters = tx.run(query, rows=rows[start:start + BATCH_SIZE]).consume().counters
            lots_added += counters.nodes_created
            links_added += counters.relationships_created
    return lots_added, links_added


def load_stream_file(
    driver: Driver, database: str, parquet_path: Path, include_properties: bool
) -> tuple[int, int, int, int]:
    """Load one stream file atomically. Returns raw rows, duplicates, new lots, new links."""
    rows, raw_count = read_and_deduplicate(parquet_path)
    parts = split_events(rows, include_properties)
    with driver.session(database=database) as session:
        lots_added, links_added = session.execute_write(apply_events, parts)
    return raw_count, raw_count - len(rows), lots_added, links_added


def load_stream(stream_path: Path, driver: Driver, database: str, include_properties: bool) -> None:
    parquet_files = resolve_stream_files(stream_path)

    for statement in SCHEMA:
        driver.execute_query(statement, database_=database)

    records, _, _ = driver.execute_query(COUNT_GRAPH, database_=database)
    if records[0]["lots"] == 0:
        raise RuntimeError(
            "Neo4j is empty. Load the base data first: "
            "uv run python -m loaders.load_neo4j"
        )

    total_raw = total_duplicates = total_lots = total_links = 0
    start = time.perf_counter()

    for parquet_file in parquet_files:
        file_start = time.perf_counter()
        raw_count, duplicate_count, lots_added, links_added = load_stream_file(
            driver, database, parquet_file, include_properties
        )
        total_raw += raw_count
        total_duplicates += duplicate_count
        total_lots += lots_added
        total_links += links_added
        print(
            f"{parquet_file.parent.name}/{parquet_file.name}: "
            f"read {raw_count:,}, removed {duplicate_count:,} duplicates, "
            f"added {lots_added:,} lot states and {links_added:,} USED_IN relationships "
            f"({(time.perf_counter() - file_start) * 1000:.0f} ms)"
        )

    elapsed = time.perf_counter() - start
    print(
        f"Finished: {len(parquet_files):,} files; read {total_raw:,} events; "
        f"removed {total_duplicates:,} duplicates; added {total_lots:,} lot states and "
        f"{total_links:,} USED_IN relationships in {elapsed:.1f} s "
        f"({elapsed / len(parquet_files) * 1000:.0f} ms per file on average)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incrementally load mes-genealogy-synth stream data into Neo4j"
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
        help="Dataset beneath backend/out/ when stream_path is omitted (default: smoke)",
    )
    parser.add_argument(
        "--properties", action="store_true",
        help="also store each state's properties and recipe JSON (use if the base load did)",
    )
    args = parser.parse_args()

    load_dotenv()
    uri = os.environ.get("NEO4J_URI")
    if not uri:
        raise SystemExit("NEO4J_URI is not configured (set it in backend/.env)")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    stream_path = args.stream_path or BACKEND_DIRECTORY / "out" / args.dataset / "stream"

    with GraphDatabase.driver(
        uri, auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"])
    ) as driver:
        driver.verify_connectivity()
        load_stream(stream_path, driver, database, args.properties)

        records, _, _ = driver.execute_query(COUNT_GRAPH, database_=database)
        print(
            f"Neo4j now holds {records[0]['lots']:,} Lot nodes and "
            f"{records[0]['used_in']:,} USED_IN relationships"
        )


if __name__ == "__main__":
    main()
