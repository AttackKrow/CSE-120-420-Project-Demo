from enum import Enum

from fastapi import FastAPI

from backend.app.adapters.adapter import Adapter
from backend.app.adapters.example_adapter import ExampleAdapter

app = FastAPI(
    title="QuantumScape Genealogy API Demo",
    version="0.1.0",
)


class BackendName(str, Enum):
    RECURSIVE_SQL = "recursive-sql"
    CLOSURE_TABLE = "closure-table"
    NEO4J = "neo4j"


adapters: dict[BackendName, Adapter] = {
    BackendName.RECURSIVE_SQL: ExampleAdapter(),
    BackendName.CLOSURE_TABLE: ExampleAdapter(),
    BackendName.NEO4J: ExampleAdapter(),
}


@app.get("/")
async def root():
    return {"message": "QuantumScape genealogy API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/units/{unit_id}/ancestors")
async def get_ancestors(
    unit_id: str,
    backend: BackendName = BackendName.RECURSIVE_SQL,
    max_depth: int = 20,
):
    adapter = adapters[backend]

    return {
        "unit_id": unit_id,
        "backend": backend.value,
        "max_depth": max_depth,
        "ancestors": await adapter.get_ancestors(unit_id, max_depth),
    }


@app.get("/units/{unit_id}/predecessors")
async def get_predecessors(
    unit_id: str,
    backend: BackendName = BackendName.RECURSIVE_SQL,
    max_depth: int = 20,
):
    adapter = adapters[backend]

    return {
        "unit_id": unit_id,
        "backend": backend.value,
        "max_depth": max_depth,
        "predecessors": await adapter.get_predecessors(unit_id, max_depth),
    }
