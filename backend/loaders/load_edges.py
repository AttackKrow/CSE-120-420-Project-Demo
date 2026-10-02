import csv
import os
from pathlib import Path

import psycopg


def load_edges(csv_path: Path) -> None:
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        with open("app/db/schema.sql", encoding="utf-8") as schema_file:
            cursor.execute(schema_file.read())

        with csv_path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)

            rows = [
                (
                    int(row["id"]),
                    row["in_lot_uuid"],
                    row["out_lot_uuid"],
                    row["segment_name"],
                )
                for row in reader
            ]

        cursor.executemany(
            """
                INSERT INTO genealogy_edges (
                    id,
                    in_lot_uuid,
                    out_lot_uuid,
                    segment_name
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
            rows,
        )

    print(f"Loaded {len(rows)} edges")


if __name__ == "__main__":
    load_edges(Path("loaders/sample_data/edges.csv"))