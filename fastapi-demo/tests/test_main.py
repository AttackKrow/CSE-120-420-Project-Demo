import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.parametrize(
    "backend",
    [
        "recursive-sql",
        "closure-table",
        "neo4j",
    ],
)
def test_get_ancestors(backend: str):
    response = client.get(
        "/units/UNIT-123/ancestors",
        params={
            "backend": backend,
            "max_depth": 50,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "unit_id": "UNIT-123",
        "backend": backend,
        "max_depth": 50,
        "ancestors": ["material-1", "process-1"],
    }
