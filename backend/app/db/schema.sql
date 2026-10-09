CREATE TABLE IF NOT EXISTS genealogy_edges (
    id BIGINT PRIMARY KEY,
    event_ts TIMESTAMP(6) NOT NULL,
    begin_ts TIMESTAMP(6) NOT NULL,
    end_ts TIMESTAMP(6) NOT NULL,
    segment_name TEXT NOT NULL,
    segment_uuid TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    in_lot_name TEXT,
    in_lot_sequence INTEGER,
    in_lot_uuid TEXT,
    in_material TEXT,
    in_lot_status TEXT,
    in_prev_segment TEXT,
    out_lot_name TEXT,
    out_lot_sequence INTEGER,
    out_lot_uuid TEXT,
    out_material TEXT,
    out_lot_status TEXT,
    location TEXT NOT NULL,
    location_type TEXT NOT NULL,
    equipment_path TEXT NOT NULL,
    operator TEXT,
    work_order_id TEXT,
    disposition TEXT,
    disposition_codes JSONB,
    ext_system_ref TEXT,
    qty_in DOUBLE PRECISION,
    qty_out DOUBLE PRECISION,
    qty_net DOUBLE PRECISION,
    qty_available DOUBLE PRECISION,
    qty_scheduled DOUBLE PRECISION,
    unit TEXT,
    in_properties JSONB,
    out_properties JSONB,
    recipe_json JSONB,
    CHECK (in_lot_uuid IS NOT NULL OR out_lot_uuid IS NOT NULL)
);

-- Ancestor traversal joins on the output; descendant traversal joins on the input.
CREATE INDEX IF NOT EXISTS idx_genealogy_edges_out_lot
    ON genealogy_edges (out_lot_uuid)
    WHERE out_lot_uuid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_genealogy_edges_in_lot
    ON genealogy_edges (in_lot_uuid)
    WHERE in_lot_uuid IS NOT NULL;

-- Metadata and time-range filters used by the reference query workload.
CREATE INDEX IF NOT EXISTS idx_genealogy_edges_segment_time
    ON genealogy_edges (segment_name, begin_ts);

CREATE INDEX IF NOT EXISTS idx_genealogy_edges_equipment_time
    ON genealogy_edges (equipment_path, begin_ts);

CREATE INDEX IF NOT EXISTS idx_genealogy_edges_location_time
    ON genealogy_edges (location, begin_ts);

CREATE INDEX IF NOT EXISTS idx_genealogy_edges_in_lot_name
    ON genealogy_edges (in_lot_name)
    WHERE in_lot_name IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_genealogy_edges_out_lot_name
    ON genealogy_edges (out_lot_name)
    WHERE out_lot_name IS NOT NULL;

-- The source intentionally contains duplicates. PostgreSQL 15+ supports
-- NULLS NOT DISTINCT, which makes this key work for creation/disposal rows too.
CREATE UNIQUE INDEX IF NOT EXISTS uq_genealogy_edge_identity
    ON genealogy_edges (
        in_lot_uuid,
        out_lot_uuid,
        segment_uuid,
        begin_ts
    ) NULLS NOT DISTINCT;
