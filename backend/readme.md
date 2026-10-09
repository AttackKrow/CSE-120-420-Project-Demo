# Backend Demo
## FastAPI

### Setup

Install [uv](https://docs.astral.sh/uv/), then install the project dependencies:

```bash
uv sync
```

### Run

```bash
uv run fastapi dev
```

The API documentation is available at `http://127.0.0.1:8000/docs`.

### Test

```bash
uv run pytest
```

## PostgreSQL Setup

1. Install PostgreSQL and create a database named `genealogy` using pgAdmin.

2. Clone the [MES genealogy synthetic-data generator](https://github.com/jbenf3/mes-genealogy-synth) in a separate directory:

   ```powershell
   git clone https://github.com/jbenf3/mes-genealogy-synth.git
   cd mes-genealogy-synth
   uv sync
   ```

3. Generate data into the backend's `out` directory. Replace the example path with the path to your backend:

   ```powershell
   $backend = "C:\path\to\project\backend"

   # Small smoke dataset
   uv run mesgen generate --scenario smoke --out "$backend/out/smoke"
   ```

   To generate the full official dataset instead:

   ```powershell
   uv run mesgen generate --scenario official_1x --out "$backend/out/official"
   ```

   The output directory must be new or empty. See the generator repository for additional generation and verification instructions.

4. Return to the backend directory and set the PostgreSQL connection URL:

   ```powershell
   $env:DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/genealogy"
   ```

5. Load the generated base data into PostgreSQL:

   ```powershell
   # Loads out/smoke/base by default
   uv run python -m loaders.load_edges
   ```

   To load the official dataset:

   ```powershell
   uv run python -m loaders.load_edges --dataset official
   ```

The loader creates the required table, deduplicates the generated events, and loads the selected dataset's `base` files. The `genealogy_edges` table must be empty before running a base load.