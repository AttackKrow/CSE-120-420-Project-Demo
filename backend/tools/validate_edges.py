import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping


EVENT_COLUMNS = {
    "id", "event_ts", "begin_ts", "end_ts", "segment_name", "segment_uuid",
    "operation_id", "in_lot_name", "in_lot_sequence", "in_lot_uuid",
    "in_material", "in_lot_status", "in_prev_segment", "out_lot_name",
    "out_lot_sequence", "out_lot_uuid", "out_material", "out_lot_status",
    "location", "location_type", "equipment_path", "operator", "work_order_id",
    "disposition", "disposition_codes", "ext_system_ref", "qty_in", "qty_out",
    "qty_net", "qty_available", "qty_scheduled", "unit", "in_properties",
    "out_properties", "recipe_json",
}

NULLABLE_EVENT_COLUMNS = {
    "in_lot_name", "in_lot_sequence", "in_lot_uuid", "in_material",
    "in_lot_status", "in_prev_segment", "out_lot_name", "out_lot_sequence",
    "out_lot_uuid", "out_material", "out_lot_status", "location", "location_type",
    "equipment_path", "operator", "work_order_id", "disposition",
    "disposition_codes", "ext_system_ref", "qty_in", "qty_out", "qty_net",
    "qty_available", "qty_scheduled", "unit", "in_properties", "out_properties",
    "recipe_json",
}

JSON_COLUMNS = {
    "disposition_codes",
    "in_properties",
    "out_properties",
    "recipe_json",
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


def _empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _parse_timestamp(value: object) -> datetime | None:
    if _empty(value):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def validate_event_rows(
    rows: Iterable[Mapping[str, object]],
) -> tuple[list[str], list[str]]:
    """Validate rows from the synthetic MES event schema."""
    errors = []
    warnings = []
    seen_ids = set()
    event_keys = set()
    duplicate_event_count = 0
    graph = defaultdict(set)

    for line_number, row in enumerate(rows, start=2):
        missing = EVENT_COLUMNS - set(row)
        if missing:
            errors.append(
                f"Line {line_number}: missing columns: "
                + ", ".join(sorted(missing))
            )
            continue

        for column in EVENT_COLUMNS - NULLABLE_EVENT_COLUMNS:
            if _empty(row.get(column)):
                errors.append(f"Line {line_number}: missing {column}")

        try:
            event_id = int(row["id"])
        except (ValueError, TypeError, KeyError):
            errors.append(f"Line {line_number}: invalid ID")
            event_id = None

        if event_id is not None:
            if event_id in seen_ids:
                errors.append(f"Line {line_number}: duplicate ID {event_id}")
            seen_ids.add(event_id)

        input_uuid = row.get("in_lot_uuid")
        output_uuid = row.get("out_lot_uuid")
        input_present = not _empty(input_uuid)
        output_present = not _empty(output_uuid)

        if not input_present and not output_present:
            errors.append(f"Line {line_number}: event has neither input nor output lot")
        if input_present and _empty(row.get("in_lot_name")):
            errors.append(f"Line {line_number}: input lot UUID has no input lot name")
        if output_present and _empty(row.get("out_lot_name")):
            errors.append(f"Line {line_number}: output lot UUID has no output lot name")
        if not input_present and not _empty(row.get("in_lot_name")):
            errors.append(
                f"Line {line_number}: creation event has input details without input UUID"
            )
        if not output_present and not _empty(row.get("out_lot_name")):
            errors.append(
                f"Line {line_number}: disposal event has output details without output UUID"
            )

        if input_present and output_present:
            if str(input_uuid) == str(output_uuid):
                errors.append(f"Line {line_number}: self-loop on {input_uuid}")
            graph[str(input_uuid)].add(str(output_uuid))

        for prefix, present in (("in", input_present), ("out", output_present)):
            sequence = row.get(f"{prefix}_lot_sequence")
            if present:
                try:
                    if int(sequence) < 0:
                        errors.append(
                            f"Line {line_number}: {prefix} lot sequence is negative"
                        )
                except (ValueError, TypeError):
                    errors.append(
                        f"Line {line_number}: invalid {prefix} lot sequence"
                    )
            elif not _empty(sequence):
                errors.append(
                    f"Line {line_number}: {prefix} sequence exists without lot UUID"
                )

        if (
            input_present
            and output_present
            and row.get("in_lot_name") == row.get("out_lot_name")
        ):
            try:
                in_sequence = int(row["in_lot_sequence"])
                out_sequence = int(row["out_lot_sequence"])

                if out_sequence not in (in_sequence, in_sequence + 1):
                    errors.append(
                        f"Line {line_number}: sequence must stay the same for a remint "
                        "or increment by one"
                    )
            except (TypeError, ValueError):
                pass

        try:
            event_ts = _parse_timestamp(row.get("event_ts"))
            begin_ts = _parse_timestamp(row.get("begin_ts"))
            end_ts = _parse_timestamp(row.get("end_ts"))

            if begin_ts is None or end_ts is None:
                errors.append(
                    f"Line {line_number}: begin_ts and end_ts are required"
                )
            else:
                if end_ts < begin_ts:
                    errors.append(
                        f"Line {line_number}: end_ts is earlier than begin_ts"
                    )
                if event_ts is not None and event_ts != begin_ts:
                    errors.append(
                        f"Line {line_number}: event_ts must equal begin_ts"
                    )
        except (ValueError, TypeError):
            errors.append(f"Line {line_number}: invalid event timestamp")

        if any(
            _empty(row.get(column))
            for column in ("segment_name", "segment_uuid", "operation_id")
        ):
            errors.append(
                f"Line {line_number}: segment_name, segment_uuid, "
                "and operation_id are required"
            )

        for column in JSON_COLUMNS:
            value = row.get(column)
            if not _empty(value):
                try:
                    json.loads(str(value))
                except (ValueError, TypeError):
                    errors.append(f"Line {line_number}: invalid JSON in {column}")

        for column in (
            "qty_in",
            "qty_out",
            "qty_net",
            "qty_available",
            "qty_scheduled",
        ):
            value = row.get(column)
            if not _empty(value):
                try:
                    if not math.isfinite(float(value)):
                        raise ValueError
                except (ValueError, TypeError):
                    errors.append(
                        f"Line {line_number}: invalid numeric value in {column}"
                    )

        event_key = (
            input_uuid,
            output_uuid,
            row.get("segment_uuid"),
            row.get("begin_ts"),
        )
        if event_key in event_keys:
            duplicate_event_count += 1
        else:
            event_keys.add(event_key)

    if duplicate_event_count:
        warnings.append(
            f"Found {duplicate_event_count} duplicate event rows; "
            "synthetic source duplicates are expected and should be "
            "deduplicated before loading"
        )

    if has_cycle(graph):
        errors.append("Genealogy contains a cycle")

    return errors, warnings


def validate_csv(csv_path: Path) -> tuple[list[str], list[str]]:
    """Validate a CSV file using the synthetic event schema."""
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        columns = set(reader.fieldnames or [])
        missing = EVENT_COLUMNS - columns

        if missing:
            return [
                "Missing event columns: " + ", ".join(sorted(missing))
            ], []

        return validate_event_rows(reader)


def _parquet_rows(paths: list[Path]) -> Iterable[dict[str, object]]:
    """Read Parquet files in batches."""
    import pyarrow.parquet as pq

    for path in paths:
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=65536):
            yield from batch.to_pylist()


def validate_path(path: Path) -> tuple[list[str], list[str]]:
    """Validate a synthetic event CSV, Parquet file, or dataset directory."""
    if path.is_file() and path.suffix.lower() == ".csv":
        return validate_csv(path)

    if path.is_file() and path.suffix.lower() == ".parquet":
        paths = [path]
    elif path.is_dir():
        base_dir = path / "base"
        stream_dir = path / "stream"

        # ignore root-level files such as churn_log.parquet.
        if base_dir.is_dir() or stream_dir.is_dir():
            event_dirs = [base_dir, stream_dir]
            paths = sorted(
                parquet_file
                for event_dir in event_dirs
                if event_dir.is_dir()
                for parquet_file in event_dir.rglob("*.parquet")
            )
        else:
            # allow passing a base/, stream/, or other event-only directory.
            paths = sorted(path.rglob("*.parquet"))
    else:
        return [f"Input does not exist or is unsupported: {path}"], []

    if not paths:
        return [f"No Parquet files found under {path}"], []

    try:
        import pyarrow.parquet as pq
    except ImportError:
        return [
            "Parquet validation requires pyarrow; install backend dependencies "
            "with `uv sync`."
        ], []

    try:
        for parquet_path in paths:
            missing = EVENT_COLUMNS - set(
                pq.ParquetFile(parquet_path).schema_arrow.names
            )
            if missing:
                return [
                    f"{parquet_path}: missing columns: "
                    + ", ".join(sorted(missing))
                ], []

        return validate_event_rows(_parquet_rows(paths))
    except Exception as error:
        return [f"Unable to validate Parquet input: {error}"], []

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "path",
        type=Path,
        help="CSV, Parquet file, or generated dataset directory",
    )

    args = parser.parse_args()

    errors, warnings = validate_path(args.path)

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
