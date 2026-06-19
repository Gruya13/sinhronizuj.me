from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import settings

# Inicijalizacija SQLAlchemy konekcije sa PostgreSQL bazom
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=25,
        max_overflow=50,
        pool_recycle=3600,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# FastAPI Dependency za dobijanje DB sesije po zahtevu
def get_db():
    print("\n[ORIGINAL_GET_DB] Pozvan originalni get_db!", flush=True)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
