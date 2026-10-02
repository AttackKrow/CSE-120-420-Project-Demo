from pydantic import BaseModel, Field


class GenealogyResponseBase(BaseModel):
    lot_uuid: str = Field(min_length=1)
    max_depth: int = Field(ge=1)


class AncestorsResponse(GenealogyResponseBase):
    ancestors: list[str]


class DescendantsResponse(GenealogyResponseBase):
    descendants: list[str]
