import os
import csv
import pytest

from pathlib import Path
from tools.validate_edges import EVENT_COLUMNS, validate_event_rows, validate_path

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://unused:unused@localhost/unused",
)

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_ancestor_response_schema():
    response = client.get(
        "/lots/test-lot/ancestors",
        params={
            "backend": "neo4j",
            "max_depth": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["lot_uuid"] == "test-lot"
    assert data["max_depth"] == 5
    assert "ancestors" in data
    assert isinstance(data["ancestors"], list)


def test_descendant_response_schema():
    response = client.get(
        "/lots/test-lot/descendants",
        params={
            "backend": "neo4j",
            "max_depth": 5,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["lot_uuid"] == "test-lot"
    assert data["max_depth"] == 5
    assert "descendants" in data
    assert isinstance(data["descendants"], list)


def test_zero_depth_is_rejected():
    response = client.get(
        "/lots/test-lot/ancestors",
        params={
            "backend": "neo4j",
            "max_depth": 0,
        },
    )

    assert response.status_code == 422


def test_depth_over_limit_is_rejected():
    response = client.get(
        "/lots/test-lot/ancestors",
        params={
            "backend": "neo4j",
            "max_depth": 101,
        },
    )

    assert response.status_code == 422

def synthetic_event(**changes):
    """Create a valid synthetic event row for validator tests."""
    row = {column: None for column in EVENT_COLUMNS}
    row.update(
        {
            "id": 1,
            "event_ts": "2000-01-03T08:00:00",
            "begin_ts": "2000-01-03T08:00:00",
            "end_ts": "2000-01-03T08:00:00",
            "segment_name": "SEG_001",
            "segment_uuid": "segment-run-1",
            "operation_id": "operation-1",
            "out_lot_name": "LOT_001",
            "out_lot_sequence": 0,
            "out_lot_uuid": "uuid-1",
            "out_material": "MAT_01",
            "out_lot_status": "ST_1",
            "qty_out": 1.0,
        }
    )
    row.update(changes)
    return row


def test_synthetic_creation_event_passes_validation():
    errors, warnings = validate_event_rows([synthetic_event()])
    assert errors == []
    assert warnings == []


def test_synthetic_process_event_passes_validation():
    row = synthetic_event(
        in_lot_name="LOT_001",
        in_lot_sequence=0,
        in_lot_uuid="uuid-1",
        in_material="MAT_01",
        in_lot_status="ST_1",
        out_lot_name="LOT_001",
        out_lot_sequence=1,
        out_lot_uuid="uuid-2",
    )
    errors, warnings = validate_event_rows([row])
    assert errors == []
    assert warnings == []


def test_synthetic_disposal_event_passes_validation():
    row = synthetic_event(
        in_lot_name="LOT_001",
        in_lot_sequence=1,
        in_lot_uuid="uuid-1",
        in_material="MAT_01",
        in_lot_status="ST_2",
        out_lot_name=None,
        out_lot_sequence=None,
        out_lot_uuid=None,
    )
    errors, _ = validate_event_rows([row])
    assert errors == []


def test_duplicate_synthetic_event_is_warning():
    errors, warnings = validate_event_rows(
        [synthetic_event(), synthetic_event(id=2)]
    )
    assert errors == []
    assert any("duplicate event rows" in warning for warning in warnings)


def test_duplicate_synthetic_id_is_error():
    errors, _ = validate_event_rows(
        [
            synthetic_event(),
            synthetic_event(id=1, out_lot_uuid="uuid-2"),
        ]
    )
    assert any("duplicate ID 1" in error for error in errors)


def test_missing_synthetic_schema_column_is_error():
    row = synthetic_event()
    del row["equipment_path"]

    errors, _ = validate_event_rows([row])
    assert any("missing columns: equipment_path" in error for error in errors)


@pytest.mark.parametrize(
    ("changes", "expected_error"),
    [
        (
            {"event_ts": "2000-01-03T08:01:00"},
            "event_ts must equal begin_ts",
        ),
        (
            {"begin_ts": "not-a-date"},
            "invalid event timestamp",
        ),
        (
            {"end_ts": "2000-01-03T07:59:00"},
            "end_ts is earlier",
        ),
        (
            {"out_lot_name": "LOT_001", "out_lot_sequence": None},
            "invalid out lot sequence",
        ),
        (
            {"recipe_json": "{bad json"},
            "invalid JSON in recipe_json",
        ),
        (
            {"qty_out": "nan"},
            "invalid numeric value in qty_out",
        ),
    ],
)
def test_invalid_synthetic_event_values_are_errors(changes, expected_error):
    errors, _ = validate_event_rows([synthetic_event(**changes)])
    assert any(expected_error in error for error in errors)


def test_synthetic_sequence_jump_is_rejected():
    row = synthetic_event(
        in_lot_name="LOT_001",
        in_lot_sequence=2,
        in_lot_uuid="uuid-1",
        out_lot_name="LOT_001",
        out_lot_sequence=4,
        out_lot_uuid="uuid-2",
    )
    errors, _ = validate_event_rows([row])
    assert any("sequence must stay the same for a remint" in error for error in errors)


def test_synthetic_genealogy_cycle_is_error():
    first = synthetic_event(
        in_lot_name="A",
        in_lot_sequence=0,
        in_lot_uuid="a",
        out_lot_name="B",
        out_lot_sequence=0,
        out_lot_uuid="b",
    )
    second = synthetic_event(
        id=2,
        in_lot_name="B",
        in_lot_sequence=0,
        in_lot_uuid="b",
        out_lot_name="A",
        out_lot_sequence=1,
        out_lot_uuid="a",
        segment_uuid="segment-run-2",
        operation_id="operation-2",
    )
    errors, _ = validate_event_rows([first, second])
    assert any("contains a cycle" in error for error in errors)


def test_synthetic_csv_passes_validation(tmp_path: Path):
    path = tmp_path / "smoke.csv"
    row = synthetic_event()

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=sorted(EVENT_COLUMNS))
        writer.writeheader()
        writer.writerow(row)

    errors, warnings = validate_path(path)
    assert errors == []
    assert warnings == []


def test_csv_without_synthetic_schema_is_rejected(tmp_path: Path):
    path = tmp_path / "incomplete.csv"
    path.write_text(
        "id,in_lot_uuid,out_lot_uuid,segment_name\n1,a,b,SEG_001\n",
        encoding="utf-8",
    )

    errors, warnings = validate_path(path)
    assert any("Missing event columns" in error for error in errors)
    assert warnings == []


def test_synthetic_parquet_dataset_passes_validation(tmp_path: Path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    path = tmp_path / "base" / "day=0000" / "events.parquet"
    path.parent.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist([synthetic_event()]), path)

    errors, warnings = validate_path(tmp_path)
    assert errors == []
    assert warnings == []