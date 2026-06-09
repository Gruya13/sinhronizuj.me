import pytest
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

# Postavljamo testni DATABASE_URL na SQLite pre uvoza bilo kog backend modula
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "memory://"

# Dodajemo koren projekta u python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.core.database import Base, get_db
from unittest.mock import MagicMock


# --- KONFIGURACIJA TESTNE BAVE (SQLite in-memory) ---
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Override get_db u FastAPI aplikaciji
app.dependency_overrides[get_db] = override_get_db

# Deaktiviramo rate limiter za potrebe testova
app.state.limiter.enabled = False

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Kreira sve tabele pre testne sesije i brise ih na kraju.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(autouse=True)
def clean_db_tables():
    """
    Cisti podatke iz svih tabela pre svakog pojedinacnog testa.
    """
    db = TestingSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()

# --- MOCK-OVANJE SPOLJNIH ZAVISNOSTI ---

@pytest.fixture(scope="session", autouse=True)
def mock_redis(session_mocker):
    """
    Mock-uje Redis klijent da testovi ne bi zavisili od Redis servera.
    """
    mock_client = MagicMock()
    # Mock-ujemo get_redis_client iz main.py
    import backend.main as main_mod
    session_mocker.patch.object(main_mod, "get_redis_client", return_value=mock_client)
    
    # Mock-ujemo redis modul uopste
    import redis
    session_mocker.patch("redis.Redis", return_value=mock_client)
    return mock_client

@pytest.fixture(scope="session", autouse=True)
def mock_boto3(session_mocker):
    """
    Mock-uje boto3 S3 klijent da testovi ne bi stvarno slali podatke na MinIO/AWS.
    """
    mock_s3 = MagicMock()
    session_mocker.patch("boto3.client", return_value=mock_s3)
    return mock_s3

@pytest.fixture(scope="session", autouse=True)
def mock_celery_tasks(session_mocker):
    """
    Mock-uje Celery task .delay() pozive da se zadaci ne bi asinhrono pokretali tokom testiranja API-ja.
    """
    from backend.worker.tasks import analyze_video_task, render_video_task
    mock_analyze = MagicMock()
    mock_render = MagicMock()
    
    session_mocker.patch.object(analyze_video_task, "delay", mock_analyze)
    session_mocker.patch.object(render_video_task, "delay", mock_render)
    
    return {
        "analyze": mock_analyze,
        "render": mock_render
    }

@pytest.fixture
def client():
    """
    FastAPI TestClient za slanje HTTP zahteva.
    """
    from fastapi.testclient import TestClient
    with TestClient(app) as test_client:
        yield test_client
