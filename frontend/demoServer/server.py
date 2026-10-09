import duckdb
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow your React app (e.g., Vite on port 5173) to fetch data
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust to your frontend URL in production (e.g., "http://localhost:5173")
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Point this to your actual parquet file or directory (e.g., 'stream/*.parquet')
PARQUET_PATHS = [
    "data/*.parquet"
]

@app.get("/api/history/{lot_name}")
def get_lot_history(lot_name: str):
    query = f"""
    WITH RECURSIVE deduped_events AS (
        SELECT *
        -- Inject the Python list directly; DuckDB parses it as an array of paths
        FROM read_parquet({PARQUET_PATHS})
        QUALIFY row_number() OVER (
            PARTITION BY in_lot_uuid, out_lot_uuid, segment_uuid, begin_ts
            ORDER BY in_prev_segment IS NULL, id
        ) = 1
    ),
    ancestry AS (
        SELECT *
        FROM deduped_events
        WHERE in_lot_name = '{lot_name}' OR out_lot_name = '{lot_name}'

        UNION ALL

        SELECT e.*
        FROM deduped_events e
        INNER JOIN ancestry a ON e.out_lot_uuid = a.in_lot_uuid
    )
    SELECT DISTINCT *
    FROM ancestry
    ORDER BY event_ts ASC
    """

    with duckdb.connect() as con:
        df = con.execute(query).df()

    if df.empty:
        return []

    # Convert datetime columns to strings for JSON serialization
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)

    # Cast dataframe to object to prevent Pandas from coercing None back to NaN
    df = df.astype(object).where(pd.notnull(df), None)

    return df.to_dict(orient="records")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
