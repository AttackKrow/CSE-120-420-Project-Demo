from abc import ABC, abstractmethod


class Adapter(ABC):
    @abstractmethod
    async def get_ancestors(self, unit_id: str, max_depth: int) -> list[str]:
        pass

    @abstractmethod
    async def get_predecessors(self, unit_id: str, max_depth: int) -> list[str]:
        pass