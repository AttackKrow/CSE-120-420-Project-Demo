import os

import psycopg
from app.adapters.adapter import Adapter
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import text

ANCESTORS_QUERY = text("""
    WITH RECURSIVE ancestors(lot_uuid, depth, path) AS (
        SELECT
            in_lot_uuid,
            1,
            ARRAY[out_lot_uuid, in_lot_uuid]
        FROM genealogy_edges
        WHERE out_lot_uuid = :lot_uuid

        UNION ALL

        SELECT
            edge.in_lot_uuid,
            ancestors.depth + 1,
            ancestors.path || edge.in_lot_uuid
        FROM genealogy_edges AS edge
        JOIN ancestors
            ON edge.out_lot_uuid = ancestors.lot_uuid
        WHERE ancestors.depth < :max_depth
          AND NOT edge.in_lot_uuid = ANY(ancestors.path)
    )
    SELECT
        lot_uuid,
        MIN(depth) AS minimum_depth
    FROM ancestors
    GROUP BY lot_uuid
    ORDER BY minimum_depth, lot_uuid;
""")


DESCENDANTS_QUERY = text("""
    WITH RECURSIVE descendants(lot_uuid, depth, path) AS (
        SELECT
            out_lot_uuid,
            1,
            ARRAY[in_lot_uuid, out_lot_uuid]
        FROM genealogy_edges
        WHERE in_lot_uuid = :lot_uuid

        UNION ALL

        SELECT
            edge.out_lot_uuid,
            descendants.depth + 1,
            descendants.path || edge.out_lot_uuid
        FROM genealogy_edges AS edge
        JOIN descendants
            ON edge.in_lot_uuid = descendants.lot_uuid
        WHERE descendants.depth < :max_depth
          AND NOT edge.out_lot_uuid = ANY(descendants.path)
    )
    SELECT
        lot_uuid,
        MIN(depth) AS minimum_depth
    FROM descendants
    GROUP BY lot_uuid
    ORDER BY minimum_depth, lot_uuid;
""")


class PostgresEdgeAdapter(Adapter):
    async def _run_traversal(
        self,
        query,
        lot_uuid: str,
        max_depth: int,
        session: AsyncSession | None,
    ) -> list[str]:
        if session is None:
            raise ValueError("A database session is required for PostgreSQL queries")

        result = await session.execute(
            query,
            {"lot_uuid": lot_uuid, "max_depth": max_depth},
        )
        return list(result.scalars().all())

    async def get_ancestors(
        self,
        lot_uuid: str,
        max_depth: int = 20,
        session: AsyncSession | None = None,
    ) -> list[str]:
        return await self._run_traversal(
            ANCESTORS_QUERY, lot_uuid, max_depth, session
        )

    async def get_descendants(
        self,
        lot_uuid: str,
        max_depth: int = 20,
        session: AsyncSession | None = None,
    ) -> list[str]:
        return await self._run_traversal(
            DESCENDANTS_QUERY, lot_uuid, max_depth, session
        )