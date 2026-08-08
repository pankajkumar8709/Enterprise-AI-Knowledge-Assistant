import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_phase1.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DOCUMENT_UPLOAD_DIR"] = str((Path.cwd() / "test_uploads").resolve())
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
for existing_file in upload_dir.iterdir():
    if existing_file.is_file():
        existing_file.unlink()


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)
