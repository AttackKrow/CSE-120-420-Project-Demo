# Steps to run the Synthetic Dataset Validator

Generate the smoke dataset by following the instructions in [`backend/readme.md`](../backend/readme.md).

## Validate the Dataset

From the project root, run:

```bash
cd backend
uv sync
uv run python tools/validate_edges.py out/smoke
```

## Run the Backend Tests
From the backend directory, run:
```bash
uv run pytest
```