# Phase 1 Backend Foundation

This backend implements the Phase 1 foundation from the project plan:

- FastAPI project scaffold
- PostgreSQL-ready SQLAlchemy setup
- Alembic migration support
- JWT authentication APIs
- Role-based access foundation
- Base route groups for users, auth, documents, knowledge, and chat
- Logging, error handling, health checks, and Swagger docs

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Update `DATABASE_URL` in `.env` to point to your PostgreSQL instance.

## Run

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

Swagger UI will be available at `http://127.0.0.1:8000/docs`.

## Test

```powershell
pytest
```
# Enterprise-AI-Knowledge-Assistant
