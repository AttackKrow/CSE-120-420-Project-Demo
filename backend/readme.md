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
2. Set the connection URL in PowerShell:
   ```powershell
   $env:DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/genealogy"
3. Load the sample edge data
    ```powershell
   uv run python -m loaders.load_edges