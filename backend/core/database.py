from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import settings

# Inicijalizacija SQLAlchemy konekcije sa PostgreSQL bazom
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# FastAPI Dependency za dobijanje DB sesije po zahtevu
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
