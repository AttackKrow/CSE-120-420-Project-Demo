from abc import ABC, abstractmethod


class Adapter(ABC):
    @abstractmethod
    async def get_ancestors(self, unit_id: str) -> list[str]:
        pass
