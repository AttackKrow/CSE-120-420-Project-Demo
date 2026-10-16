"""Run the generator's 8 reference queries in Cypher and check them against its expected answers.

The generator (mes-genealogy-synth) defines each query in SQL and gives each one's inputs and its correct answer
These are the same 8 questions written in Cypher for the graph built by loaders/load_neo4j.py and loaders/load_stream_neo4j.py.

The expected answers cover the base and the stream data, so both need to be loaded first.

"""

import argparse
import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase, RoutingControl

BACKEND_DIRECTORY = Path(__file__).parents[1]

# Graph model (see loaders/load_neo4j.py): one (:Lot) node per lot state, holding the
# details of the event that produced it; (:Lot)-[:USED_IN]->(:Lot) from input to output.
QUERIES: dict[str, dict[str, Any]] = {
    "q1": {
        "name": "q1_ancestry",
        "question": "What was this lot state made from?",
        "parameters": {"lot_uuid": "q1_lot_uuid"},
        "columns": ["lot_uuid"],
        "cypher": """
            MATCH (:Lot {lot_id: $lot_uuid})<-[:USED_IN*1..]-(ancestor:Lot)
            RETURN DISTINCT ancestor.lot_id AS lot_uuid
        """,
    },
    "q2": {
        "name": "q2_descendants",
        "question": "What was made from this lot state?",
        "parameters": {"lot_uuid": "q2_lot_uuid"},
        "columns": ["lot_uuid"],
        "cypher": """
            MATCH (:Lot {lot_id: $lot_uuid})-[:USED_IN*1..]->(descendant:Lot)
            RETURN DISTINCT descendant.lot_id AS lot_uuid
        """,
    },
    "q3": {
        "name": "q3_commonality",
        "question": "Which equipment do the units that failed the test step have in common?",
        "parameters": {"segment": "q3_segment", "from": "q3_from", "to": "q3_to"},
        "columns": ["equipment_path", "failing", "passing"],
        "cypher": """
            MATCH (member:Lot {segment_name: $segment})
            WHERE member.begin_ts >= $from AND member.begin_ts < $to
            WITH member, EXISTS { (member)-[:USED_IN]->(:Lot {status: 'ST_2'}) } AS failed
            MATCH (upstream:Lot)-[:USED_IN*0..]->(member)
            WITH DISTINCT member, failed, upstream.equipment_path AS equipment_path
            WHERE equipment_path IS NOT NULL
            RETURN equipment_path,
                   count(CASE WHEN failed THEN 1 END) AS failing,
                   count(CASE WHEN NOT failed THEN 1 END) AS passing
        """,
    },
    "q4": {
        "name": "q4_bom",
        "question": "What went into this lot (every other lot name among its ancestors)?",
        "parameters": {"lot_name": "q4_lot_name"},
        "columns": ["lot_name"],
        "cypher": """
            MATCH (:Lot {lot_name: $lot_name})<-[:USED_IN*1..]-(ancestor:Lot)
            WHERE ancestor.lot_name <> $lot_name
            RETURN DISTINCT ancestor.lot_name AS lot_name
        """,
    },
    "q5": {
        "name": "q5_where_used",
        "question": "Where was this lot used (every other lot name among its descendants)?",
        "parameters": {"lot_name": "q5_lot_name"},
        "columns": ["lot_name"],
        "cypher": """
            MATCH (:Lot {lot_name: $lot_name})-[:USED_IN*1..]->(descendant:Lot)
            WHERE descendant.lot_name <> $lot_name
            RETURN DISTINCT descendant.lot_name AS lot_name
        """,
    },
    "q6": {
        "name": "q6_processed_on",
        "question": "What was processed on this machine in this time window?",
        "parameters": {"equipment": "q6_equipment", "from": "q6_from", "to": "q6_to"},
        "columns": ["lot_name"],
        "cypher": """
            MATCH (produced:Lot {equipment_path: $equipment})
            WHERE produced.begin_ts >= $from AND produced.begin_ts < $to
            RETURN produced.lot_name AS lot_name
            UNION
            MATCH (consumed:Lot)-[:USED_IN]->(produced:Lot {equipment_path: $equipment})
            WHERE produced.begin_ts >= $from AND produced.begin_ts < $to
            RETURN consumed.lot_name AS lot_name
            UNION
            MATCH (disposed:Lot {disposal_equipment_path: $equipment})
            WHERE disposed.disposal_ts >= $from AND disposed.disposal_ts < $to
            RETURN disposed.lot_name AS lot_name
        """,
    },
    "q7": {
        "name": "q7_excursion_impact",
        "question": "What could a machine problem in this window have affected?",
        "parameters": {"equipment": "q7_equipment", "from": "q7_from", "to": "q7_to"},
        "columns": ["lot_name"],
        "cypher": """
            MATCH (produced:Lot {equipment_path: $equipment})
            WHERE produced.begin_ts >= $from AND produced.begin_ts < $to
            MATCH (produced)-[:USED_IN*0..]->(affected:Lot)
            RETURN DISTINCT affected.lot_name AS lot_name
        """,
    },
    "q8": {
        "name": "q8_device_history",
        "question": "What is this lot's history (every state, with the event that produced it)?",
        "parameters": {"lot_name": "q8_lot_name"},
        "columns": ["lot_uuid", "sequence", "material", "segment_name",
                    "equipment_path", "location", "begin_ts"],
        "cypher": """
            MATCH (state:Lot {lot_name: $lot_name})
            RETURN state.lot_id AS lot_uuid, state.sequence AS sequence,
                   CASE WHEN state.segment_name IS NULL THEN null ELSE state.material END AS material,
                   state.segment_name AS segment_name, state.equipment_path AS equipment_path,
                   state.location AS location, state.begin_ts AS begin_ts
        """,
    },
}


def read_parameters(path: Path) -> dict[str, Any]:
    """Parse `SET VARIABLE name = 'text';` and `... = TIMESTAMP 'YYYY-MM-DD HH:MM:SS';` lines."""
    values: dict[str, Any] = {}
    pattern = re.compile(r"SET VARIABLE (\w+) = (TIMESTAMP )?'([^']*)'")
    for name, is_timestamp, value in pattern.findall(path.read_text(encoding="utf-8")):
        values[name] = datetime.fromisoformat(value) if is_timestamp else value
    return values


def normalize(value: Any) -> str:
    """One text form for both sides: '' for null, YYYY-MM-DD HH:MM:SS.ffffff for timestamps."""
    if value is None or value == "":
        return ""
    if hasattr(value, "to_native"):          # neo4j.time.DateTime / LocalDateTime
        value = value.to_native()
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?", value):
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M:%S.%f")
    return str(value)


def read_expected(path: Path, columns: list[str]) -> set[tuple[str, ...]]:
    with path.open(newline="", encoding="utf-8") as f:
        return {tuple(normalize(row[c]) for c in columns) for row in csv.DictReader(f)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Neo4j against the generator's reference answers")
    parser.add_argument("mesgen_repo", type=Path, help="the mes-genealogy-synth repository folder")
    parser.add_argument("--dataset", default="smoke",
                        help="dataset beneath backend/out/ that is loaded in Neo4j (default: smoke)")
    parser.add_argument("--only", nargs="+", choices=sorted(QUERIES), help="run only these queries")
    args = parser.parse_args()

    # Which scenario is loaded, and is it exactly the data the answers were computed on
    manifest = json.loads((BACKEND_DIRECTORY / "out" / args.dataset / "manifest.json").read_text())
    scenario = manifest["scenario"]["name"]
    expected_dir = args.mesgen_repo.expanduser() / "expected" / scenario
    expected_sha = (expected_dir / "content_sha256.txt").read_text().strip()
    if manifest["content_sha256"] != expected_sha:
        print(f"WARNING: out/{args.dataset} is not the data the expected answers were computed on "
              "(content_sha256 differs). Regenerate it by scenario name without --seed or --profile.\n")
    parameters = read_parameters(expected_dir / "parameters.sql")

    load_dotenv()
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    passed = 0
    selected = args.only or sorted(QUERIES)

    with GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    ) as driver:
        driver.verify_connectivity()
        print(f"Scenario {scenario}: checking {len(selected)} reference queries against Neo4j\n")

        for key in selected:
            query = QUERIES[key]
            params = {name: parameters[source] for name, source in query["parameters"].items()}
            start = time.perf_counter()
            records, _, _ = driver.execute_query(
                query["cypher"], params, database_=database, routing_=RoutingControl.READ
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            got = {tuple(normalize(record[c]) for c in query["columns"]) for record in records}
            expected = read_expected(expected_dir / f"{query['name']}.csv", query["columns"])
            ok = got == expected
            passed += ok
            print(f"{key.upper()} {query['name']:<21} {'OK      ' if ok else 'MISMATCH'} "
                  f"{len(expected):>6,} expected rows, {len(got):>6,} returned, {elapsed_ms:8.1f} ms")
            if not ok:
                print(f"    {query['question']}")
                print(f"    missing from Neo4j: {sorted(expected - got)[:3]}")
                print(f"    not in the answer:  {sorted(got - expected)[:3]}")

    print(f"\n{passed} of {len(selected)} queries match the expected answers.")
    if passed < len(selected):
        print("If several differ, check that both the base and the stream are loaded "
              "(load_neo4j, then load_stream_neo4j) for this dataset.")


if __name__ == "__main__":
    main()
