import argparse
import csv
from collections import defaultdict
from pathlib import Path


REQUIRED_COLUMNS = {
    "id",
    "in_lot_uuid",
    "out_lot_uuid",
    "segment_name",
}


def has_cycle(graph: dict[str, set[str]]) -> bool:
    visiting = set()
    visited = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True

        if node in visited:
            return False

        visiting.add(node)

        for neighbor in graph.get(node, set()):
            if visit(neighbor):
                return True

        visiting.remove(node)
        visited.add(node)

        return False

    for node in graph:
        if node not in visited and visit(node):
            return True

    return False


def validate_edges(csv_path: Path):
    errors = []
    warnings = []

    seen_ids = set()
    seen_edges = set()

    graph = defaultdict(set)

    with csv_path.open(
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        columns = set(reader.fieldnames or [])

        missing = REQUIRED_COLUMNS - columns

        if missing:
            errors.append(
                "Missing columns: "
                + ", ".join(sorted(missing))
            )

            return errors, warnings

        for line_number, row in enumerate(
            reader,
            start=2,
        ):
            input_lot = row["in_lot_uuid"].strip()
            output_lot = row["out_lot_uuid"].strip()

            try:
                edge_id = int(row["id"])
            except ValueError:
                errors.append(
                    f"Line {line_number}: invalid ID"
                )
                continue

            if edge_id in seen_ids:
                errors.append(
                    f"Line {line_number}: duplicate ID {edge_id}"
                )

            seen_ids.add(edge_id)

            if not input_lot:
                errors.append(
                    f"Line {line_number}: missing input lot"
                )

            if not output_lot:
                errors.append(
                    f"Line {line_number}: missing output lot"
                )

            if not row["segment_name"].strip():
                errors.append(
                    f"Line {line_number}: missing segment name"
                )

            if input_lot == output_lot:
                errors.append(
                    f"Line {line_number}: self-loop on {input_lot}"
                )

            edge = (
                input_lot,
                output_lot,
            )

            if edge in seen_edges:
                errors.append(
                    f"Line {line_number}: duplicate edge "
                    f"{input_lot} -> {output_lot}"
                )

            seen_edges.add(edge)

            if input_lot and output_lot:
                graph[input_lot].add(output_lot)

    if has_cycle(graph):
        warnings.append(
            "Genealogy contains a cycle"
        )

    return errors, warnings


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "csv_path",
        type=Path,
    )

    args = parser.parse_args()

    errors, warnings = validate_edges(args.csv_path)

    print("Dataset Validation")
    print("------------------")

    for warning in warnings:
        print(f"WARNING: {warning}")

    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"\nFAIL: {len(errors)} errors")
        return 1

    print(f"\nPASS: {len(warnings)} warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
