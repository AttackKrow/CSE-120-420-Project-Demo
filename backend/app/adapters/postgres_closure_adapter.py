import os

import psycopg
from app.adapters.adapter import Adapter

ANCESTORS_QUERY = """
    SELECT
        ancestor_uuid
    FROM genealogy_closure
    WHERE descendent_uuid = %s
      AND distance <= %s
    ORDER BY distance, ancestor_uuid;
"""


DESCENDANTS_QUERY = """
    SELECT
        descendent_uuid
    FROM genealogy_closure
    WHERE ancestor_uuid = %s
      AND distance <= %s
    ORDER BY distance, descendent_uuid;
"""


class PostgresClosureAdapter(Adapter):
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.environ["DATABASE_URL"]

    async def _run_query(
        self,
        query: str,
        lot_uuid: str,
        max_depth: int,
    ) -> list[str]:
        async with await psycopg.AsyncConnection.connect(
            self.database_url
        ) as connection, connection.cursor() as cursor:
            await cursor.execute(
                query,
                (lot_uuid, max_depth),
            )
            rows = await cursor.fetchall()

        return [row[0] for row in rows]

    async def get_ancestors(
        self,
        lot_uuid: str,
        max_depth: int = 20,
    ) -> list[str]:
        return await self._run_query(
            ANCESTORS_QUERY,
            lot_uuid,
            max_depth,
        )

    async def get_descendants(
        self,
        lot_uuid: str,
        max_depth: int = 20,
    ) -> list[str]:
        return await self._run_query(
            DESCENDANTS_QUERY,
            lot_uuid,
            max_depth,
        )
