# Backend Setup & Environment Guidelines

> [!IMPORTANT]  
> **Python Environment Mismatch Warning**:  
> On Windows machines with multiple Python versions installed (e.g. Python 3.11 vs Python 3.14), running bare `uvicorn main:app --reload` or `pip install` may execute under different Python interpreters.

## Target Python Interpreter
This project requires Python 3.14+ (or the virtual environment located at `backend/.venv`).

### How to Install Dependencies & Run Server Correctly

1. **Virtual Environment Activation (Recommended)**:
   ```bash
   cd backend
   python -m venv .venv
   .\.venv\Scripts\activate
   python -m pip install -r requirements.txt
   python -m uvicorn main:app --reload --port 8000
   ```

2. **Explicit Python Interpreter (Without Venv Activation)**:
   ```bash
   python -m pip install -r backend/requirements.txt
   python -m uvicorn main:app --reload --port 8000
   ```

> **Note**: Always use `python -m uvicorn main:app` instead of bare `uvicorn main:app` to guarantee uvicorn runs under the exact Python environment where dependencies were installed.

## Semantic Search

Semantic search uses a local multilingual embedding model. It does not require
an LLM API key and does not change source records, CSV files, ingestion,
crawler behavior, or database synchronization.

After the database contains the records to search, build the separate local
index from `backend`:

```bash
python -m semantic_search
```

The first run downloads the model once and stores it in the local model cache.
The index is stored in `backend/.semantic_index.json` and is ignored by Git.
If the model or index is unavailable, existing exact and fuzzy search behavior
remains available.
