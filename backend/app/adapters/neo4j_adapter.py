
import os

from app.adapters.adapter import Adapter
from neo4j import AsyncGraphDatabase, RoutingControl

MAX_DEPTH_LIMIT = 100

ANCESTORS_QUERY = """
    MATCH path = (ancestor:Lot)-[:USED_IN*1..{depth}]->(:Lot {{lot_id: $lot_uuid}})
    WITH ancestor.lot_id AS lot_uuid, min(length(path)) AS minimum_depth
    RETURN lot_uuid
    ORDER BY minimum_depth, lot_uuid
"""

DESCENDANTS_QUERY = """
    MATCH path = (:Lot {{lot_id: $lot_uuid}})-[:USED_IN*1..{depth}]->(descendant:Lot)
    WITH descendant.lot_id AS lot_uuid, min(length(path)) AS minimum_depth
    RETURN lot_uuid
    ORDER BY minimum_depth, lot_uuid
"""


class Neo4jAdapter(Adapter):
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ):
        self.driver = AsyncGraphDatabase.driver(
            uri or os.environ["NEO4J_URI"],
            auth=(user or os.environ["NEO4J_USERNAME"], password or os.environ["NEO4J_PASSWORD"]),
        )
        self.database = database or os.environ.get("NEO4J_DATABASE", "neo4j")

    async def _run_traversal(
        self,
        query: str,
        lot_uuid: str,
        max_depth: int,
    ) -> list[str]:
        depth = max(1, min(int(max_depth), MAX_DEPTH_LIMIT))
        records, _, _ = await self.driver.execute_query(
            query.format(depth=depth),
            lot_uuid=lot_uuid,
            database_=self.database,
            routing_=RoutingControl.READ,
        )
        return [record["lot_uuid"] for record in records]

    async def get_ancestors(
        self,
        lot_uuid: str,
        max_depth: int = 20,
    ) -> list[str]:
        return await self._run_traversal(ANCESTORS_QUERY, lot_uuid, max_depth)

    async def get_descendants(
        self,
        lot_uuid: str,
        max_depth: int = 20,
    ) -> list[str]:
        return await self._run_traversal(DESCENDANTS_QUERY, lot_uuid, max_depth)

    async def close(self) -> None:
        await self.driver.close()
