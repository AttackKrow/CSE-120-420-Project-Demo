from enum import Enum

from app.adapters.adapter import Adapter
from app.adapters.example_adapter import ExampleAdapter
from app.adapters.postgres_edge_adapter import PostgresEdgeAdapter
from fastapi import FastAPI

app = FastAPI(
    title="QuantumScape Genealogy API Demo",
    version="0.1.0",
)


class BackendName(str, Enum):
    RECURSIVE_SQL = "recursive-sql"
    CLOSURE_TABLE = "closure-table"
    NEO4J = "neo4j"


adapters: dict[BackendName, Adapter] = {
    BackendName.RECURSIVE_SQL: PostgresEdgeAdapter(),
    BackendName.CLOSURE_TABLE: ExampleAdapter(),
    BackendName.NEO4J: ExampleAdapter(),
}


@app.get("/")
async def root():
    return {"message": "QuantumScape genealogy API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/lots/{lot_uuid}/ancestors")
async def get_ancestors(
    lot_uuid: str,
    backend: BackendName = BackendName.RECURSIVE_SQL,
    max_depth: int = 20,
):
    adapter = adapters[backend]

    return {
        "lot_uuid": lot_uuid,
        "max_depth": max_depth,
        "ancestors": await adapter.get_ancestors(
            lot_uuid,
            max_depth,
        ),
    }


@app.get("/lots/{lot_uuid}/descendants")
async def get_descendants(
    lot_uuid: str,
    backend: BackendName = BackendName.RECURSIVE_SQL,
    max_depth: int = 20,
):
    adapter = adapters[backend]

    return {
        "lot_uuid": lot_uuid,
        "max_depth": max_depth,
        "descendants": await adapter.get_descendants(
            lot_uuid,
            max_depth,
        ),
    }
