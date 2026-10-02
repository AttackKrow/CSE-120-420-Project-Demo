import os

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
