import logging
import os
from enum import Enum

from app.adapters.adapter import Adapter
from app.adapters.example_adapter import ExampleAdapter
from app.adapters.neo4j_adapter import Neo4jAdapter
from app.adapters.postgres_edge_adapter import PostgresEdgeAdapter
from app.models.genealogy import AncestorsResponse, DescendantsResponse
from typing import Annotated
from dotenv import load_dotenv
from fastapi import FastAPI, Query

load_dotenv()

app = FastAPI(
    title="QuantumScape Genealogy API Demo",
    version="0.1.0",
)


class BackendName(str, Enum):
    RECURSIVE_SQL = "recursive-sql"
    CLOSURE_TABLE = "closure-table"
    NEO4J = "neo4j"


def make_neo4j_adapter() -> Adapter:
    """Real Neo4j when NEO4J_URI is configured, otherwise the placeholder adapter."""
    if os.environ.get("NEO4J_URI"):
        return Neo4jAdapter()
    logging.getLogger(__name__).warning("NEO4J_URI not set: neo4j backend uses ExampleAdapter")
    return ExampleAdapter()


adapters: dict[BackendName, Adapter] = {
    BackendName.RECURSIVE_SQL: PostgresEdgeAdapter(),
    BackendName.CLOSURE_TABLE: ExampleAdapter(),
    BackendName.NEO4J: make_neo4j_adapter(),
}


@app.get("/")
async def root():
    return {"message": "QuantumScape genealogy API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get(
    "/lots/{lot_uuid}/ancestors",
    response_model=AncestorsResponse,
)

async def get_ancestors(
    lot_uuid: str,
    backend: BackendName = BackendName.RECURSIVE_SQL,
    max_depth: Annotated[int, Query(ge=1, le=100)] = 20,
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


@app.get(
    "/lots/{lot_uuid}/descendants",
    response_model=DescendantsResponse,
)
async def get_descendants(
    lot_uuid: str,
    backend: BackendName = BackendName.RECURSIVE_SQL,
    max_depth: Annotated[int, Query(ge=1, le=100)] = 20,
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
