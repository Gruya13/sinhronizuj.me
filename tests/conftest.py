import pytest
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

# Proveravamo da li je u okruženju već postavljen DATABASE_URL za PostgreSQL test bazu
# Ako nije, podrazumevano koristimo SQLite test_temp.db za lokalne testove
database_url = os.environ.get("DATABASE_URL")
if not database_url or not (database_url.startswith("postgresql") or database_url.startswith("postgres")):
    database_url = "sqlite:///test_temp.db"

os.environ["DATABASE_URL"] = database_url
os.environ["REDIS_URL"] = "memory://"

# Dodajemo koren projekta u python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.core.database import Base, get_db
from backend.core.models import User, Project, Segment, Glossary, Waitlist
from unittest.mock import MagicMock


# --- KONFIGURACIJA TESTNE BAZE ---
SQLALCHEMY_DATABASE_URL = database_url

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # Za PostgreSQL koristimo standardni engine sa pool-om, bez StaticPool i check_same_thread
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True
    )

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Preglašavamo engine i SessionLocal u bazi podataka da svi koriste naš test engine
import backend.core.database as db_mod
db_mod.engine = engine
db_mod.SessionLocal = TestingSessionLocal

def override_get_db():
    print("\n[OVERRIDE_GET_DB] Pozvan override!", flush=True)
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
    # Zatvaramo konekcije engine-a kako bi se fajl otključao
    engine.dispose()
    # Brišemo privremeni fajl baze ukoliko se koristi SQLite
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite") and os.path.exists("test_temp.db"):
        try:
            os.remove("test_temp.db")
        except Exception:
            pass

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
    
    # Mock-ujemo get_redis_client iz auth.py
    import backend.core.auth as auth_mod
    session_mocker.patch.object(auth_mod, "get_redis_client", return_value=mock_client)
    
    # Mock-ujemo redis modul uopste
    import redis
    session_mocker.patch("redis.Redis", return_value=mock_client)
    session_mocker.patch("redis.Redis.from_url", return_value=mock_client)
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
