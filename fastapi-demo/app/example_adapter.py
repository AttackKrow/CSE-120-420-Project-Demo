from app.adapter import Adapter


class ExampleAdapter(Adapter):
    async def get_ancestors(self, unit_id: str, max_depth: int) -> list[str]:
        return ["material-1", "process-1"]
