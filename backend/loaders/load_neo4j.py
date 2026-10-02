import csv
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

LOAD_QUERY = """
    UNWIND $rows AS row
    MERGE (input:Lot {lot_id: row.in_lot_uuid})
    MERGE (output:Lot {lot_id: row.out_lot_uuid})
    MERGE (input)-[edge:USED_IN]->(output)
    SET edge.edge_id = row.id, edge.step = row.segment_name
"""


def load_edges(csv_path: Path) -> None:
    load_dotenv()
    database = os.environ.get("NEO4J_DATABASE", "neo4j")

    with csv_path.open(encoding="utf-8", newline="") as csv_file:
        rows = [
            {
                "id": int(row["id"]),
                "in_lot_uuid": row["in_lot_uuid"],
                "out_lot_uuid": row["out_lot_uuid"],
                "segment_name": row["segment_name"],
            }
            for row in csv.DictReader(csv_file)
        ]

    with GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
    ) as driver:
        driver.execute_query(
            "CREATE CONSTRAINT lot_id IF NOT EXISTS FOR (l:Lot) REQUIRE l.lot_id IS UNIQUE",
            database_=database,
        )
        driver.execute_query(LOAD_QUERY, rows=rows, database_=database)

    print(f"Loaded {len(rows)} edges into Neo4j")


if __name__ == "__main__":
    load_edges(Path("loaders/sample_data/edges.csv"))
