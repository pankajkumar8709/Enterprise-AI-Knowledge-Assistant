import os
from pathlib import Path
import shutil
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///./test_phase1.db"
os.environ["SECRET_KEY"] = "test-secret"
TEST_STORAGE_ROOT = Path(tempfile.mkdtemp(prefix="phase_backend_tests_"))
os.environ["DOCUMENT_UPLOAD_DIR"] = str((TEST_STORAGE_ROOT / "uploads").resolve())
os.environ["DOCUMENT_EXTRACTION_DIR"] = str((TEST_STORAGE_ROOT / "extractions").resolve())
os.environ["MAX_DOCUMENT_SIZE_BYTES"] = "1024"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import get_db
from app.main import app
from app.models.base import Base

engine = create_engine("sqlite:///./test_phase1.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
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
