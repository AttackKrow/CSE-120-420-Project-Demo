CREATE TABLE IF NOT EXISTS genealogy_edges (
    id BIGINT PRIMARY KEY,
    in_lot_uuid TEXT NOT NULL,
    out_lot_uuid TEXT NOT NULL,
    segment_name TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_edges_input
    ON genealogy_edges(in_lot_uuid);

CREATE INDEX IF NOT EXISTS idx_edges_output
    ON genealogy_edges(out_lot_uuid);