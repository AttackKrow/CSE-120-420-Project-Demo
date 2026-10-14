from app.adapters.adapter import Adapter
from sqlmodel.ext.asyncio.session import AsyncSession

class ExampleAdapter(Adapter):
    async def get_ancestors(self, lot_uuid: str, max_depth: int, session: AsyncSession | None = None) -> list[str]:
        return ["material-1", "process-1"]

    async def get_descendants(self, lot_uuid: str, max_depth: int, session: AsyncSession | None = None) -> list[str]:
        return ["material-1", "process-1"]
