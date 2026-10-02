from abc import ABC, abstractmethod


class Adapter(ABC):
    @abstractmethod
    async def get_ancestors(
        self,
        lot_uuid: str,
        max_depth: int,
    ) -> list[str]:
        pass

    @abstractmethod
    async def get_descendants(
        self,
        lot_uuid: str,
        max_depth: int,
    ) -> list[str]:
        pass