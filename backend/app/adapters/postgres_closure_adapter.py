import os
from app.adapters.adapter import Adapter
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.genealogy import GenealogyClosure

class PostgresClosureAdapter(Adapter):
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.environ["DATABASE_URL"]

    async def _run_query(
        self,
        column: str,
        lot_uuid: str,
        max_depth: int,
        session: AsyncSession | None,
    ) -> list[str]:
        if session is None:
            raise ValueError("A database session is required for PostgreSQL queries")

        if column == "ancestor_uuid":
            selected_column = GenealogyClosure.ancestor_uuid
            lookup_column = GenealogyClosure.descendent_uuid
        else:
            selected_column = GenealogyClosure.descendent_uuid
            lookup_column = GenealogyClosure.ancestor_uuid

        statement = (
            select(selected_column)
            .where(lookup_column == lot_uuid)
            .where(GenealogyClosure.distance <= max_depth)
            .order_by(GenealogyClosure.distance, selected_column)
        )
        result = await session.exec(statement)
        return list(result.all())


    async def get_ancestors(
        self,
        lot_uuid: str,
        max_depth: int = 20,
        session: AsyncSession | None = None,
    ) -> list[str]:
        return await self._run_query("ancestor_uuid", lot_uuid, max_depth, session)


    async def get_descendants(
        self,
        lot_uuid: str,
        max_depth: int = 20,
        session: AsyncSession | None = None,
    ) -> list[str]:
        return await self._run_query("descendent_uuid", lot_uuid, max_depth, session)
