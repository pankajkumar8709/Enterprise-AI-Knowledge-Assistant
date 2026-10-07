import os
import shutil
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_phase1.db"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-at-least-thirty-two-characters"
os.environ["LLM_EXTERNAL_ALLOWED"] = "false"
os.environ["ADMIN_EMAIL"] = ""
os.environ["ADMIN_PASSWORD"] = ""
TEST_STORAGE_ROOT = Path(tempfile.mkdtemp(prefix="phase_backend_tests_"))
os.environ["DOCUMENT_UPLOAD_DIR"] = str((TEST_STORAGE_ROOT / "uploads").resolve())
os.environ["DOCUMENT_EXTRACTION_DIR"] = str((TEST_STORAGE_ROOT / "extractions").resolve())
os.environ["MAX_DOCUMENT_SIZE_BYTES"] = "1024"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db.session import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User, UserRole

# Spec §7.2 retries sleep 30s/120s/480s between attempts; the pipeline comment
# documents that tests monkeypatch the backoff to zeros so failed ingests
# (e.g. empty documents) settle instantly instead of blocking ~10 minutes.
from app.services import ingestion as _ingestion_module

_ingestion_module.INGEST_RETRY_BACKOFF_SECONDS = (0.0, 0.0, 0.0)

engine = create_engine("sqlite:///./test_phase1.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
seed_session = TestingSessionLocal()
seed_session.add(
    User(
        full_name="Admin User",
        email="admin@example.com",
        hashed_password=hash_password("StrongPass123"),
        role=UserRole.ADMIN,
    )
)
seed_session.commit()
seed_session.close()
upload_dir = Path(os.environ["DOCUMENT_UPLOAD_DIR"])
upload_dir.mkdir(parents=True, exist_ok=True)
shutil.rmtree(upload_dir, ignore_errors=True)
upload_dir.mkdir(parents=True, exist_ok=True)

extraction_dir = Path(os.environ["DOCUMENT_EXTRACTION_DIR"])
shutil.rmtree(extraction_dir, ignore_errors=True)
extraction_dir.mkdir(parents=True, exist_ok=True)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)
