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

2. Clone and set up the [MES genealogy synthetic-data generator](https://github.com/jbenf3/mes-genealogy-synth):

   ```powershell
   git clone https://github.com/jbenf3/mes-genealogy-synth.git
   cd mes-genealogy-synth
   uv sync
   ```

3. Generate data into the backend's `out` directory:

   ```powershell
   $backend = "C:\path\to\project\backend"

   # Small smoke dataset
   uv run mesgen generate --scenario smoke --out "$backend/out/smoke"
   ```

   To generate the official dataset:

   ```powershell
   uv run mesgen generate --scenario official_1x --out "$backend/out/official"
   ```

   The output directory must be new or empty.

4. Return to the backend directory and set the PostgreSQL connection URL:

   ```powershell
   $env:DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/genealogy"
   ```

5. Load the generated base events into the edge table:

   ```powershell
   # Loads out/smoke/base by default
   uv run python -m loaders.load_edges
   ```

   To load the official dataset:

   ```powershell
   uv run python -m loaders.load_edges --dataset official
   ```

6. Build the closure table from the loaded edge table:

   ```powershell
   uv run python -m loaders.load_closure
   ```

The edge loader creates and populates `genealogy_edges`. The closure loader then derives all reachable ancestor–descendent relationships and stores their minimum distances in `genealogy_closure`.

Both tables must be empty before their respective base loaders are run. To intentionally rebuild only the closure table:

```sql
TRUNCATE TABLE genealogy_closure;
```

Then rerun:

```powershell
uv run python -m loaders.load_closure
```