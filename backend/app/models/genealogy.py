from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class GenealogyEdge(SQLModel, table=True):
    __tablename__ = "genealogy_edges"
    __table_args__ = (
        Index("idx_genealogy_edges_out_lot", "out_lot_uuid"),
        Index("idx_genealogy_edges_in_lot", "in_lot_uuid"),
        Index("idx_genealogy_edges_segment_time", "segment_name", "begin_ts"),
        Index(
            "uq_genealogy_edge_identity",
            "in_lot_uuid",
            "out_lot_uuid",
            "segment_uuid",
            "begin_ts",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: int = Field(
        sa_column=Column(BigInteger, primary_key=True, autoincrement=False)
    )
    event_ts: datetime = Field(sa_column=Column(DateTime(timezone=False)))
    begin_ts: datetime = Field(sa_column=Column(DateTime(timezone=False)))
    end_ts: datetime = Field(sa_column=Column(DateTime(timezone=False)))
    segment_name: str
    segment_uuid: str
    operation_id: str

    in_lot_name: str | None = None
    in_lot_sequence: int | None = None
    in_lot_uuid: str | None = None
    in_material: str | None = None
    in_lot_status: str | None = None
    in_prev_segment: str | None = None

    out_lot_name: str | None = None
    out_lot_sequence: int | None = None
    out_lot_uuid: str | None = None
    out_material: str | None = None
    out_lot_status: str | None = None

    location: str
    location_type: str
    equipment_path: str
    operator: str | None = None
    work_order_id: str | None = None
    disposition: str | None = None
    disposition_codes: Any | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    ext_system_ref: str | None = None
    qty_in: float | None = None
    qty_out: float | None = None
    qty_net: float | None = None
    qty_available: float | None = None
    qty_scheduled: float | None = None
    unit: str | None = None
    in_properties: Any | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    out_properties: Any | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    recipe_json: Any | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )


class GenealogyClosure(SQLModel, table=True):
    __tablename__ = "genealogy_closure"
    __table_args__ = (
        Index(
            "idx_genealogy_closure_descendent",
            "descendent_uuid",
            "distance",
            "ancestor_uuid",
        ),
        Index(
            "idx_genealogy_closure_ancestor_distance",
            "ancestor_uuid",
            "distance",
            "descendent_uuid",
        ),
    )

    ancestor_uuid: str = Field(primary_key=True)
    descendent_uuid: str = Field(primary_key=True)
    distance: int


class GenealogyResponseBase(SQLModel):
    lot_uuid: str = Field(min_length=1)
    max_depth: int = Field(ge=1)


class AncestorsResponse(GenealogyResponseBase):
    ancestors: list[str]


class DescendantsResponse(GenealogyResponseBase):
    descendants: list[str]