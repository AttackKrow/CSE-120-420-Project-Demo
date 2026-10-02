from app.adapters.adapter import Adapter


class ExampleAdapter(Adapter):
    async def get_ancestors(self, lot_uuid: str, max_depth: int) -> list[str]:
        return ["material-1", "process-1"]

    async def get_descendants(self, lot_uuid: str, max_depth: int) -> list[str]:
        return ["material-1", "process-1"]
