import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Sinhronizuj.me"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "") # Prazan po defaultu za lokalni dev
    
    # Modal Serverless Endpoints
    MODAL_STT_URL: str = os.getenv("MODAL_STT_URL", "")
    MODAL_SENSEVOICE_URL: str = os.getenv("MODAL_SENSEVOICE_URL", "")
    MODAL_TRANSLATOR_URL: str = os.getenv("MODAL_TRANSLATOR_URL", "")
    MODAL_LEKTOR_URL: str = os.getenv("MODAL_LEKTOR_URL", "")
    MODAL_TTS_URL: str = os.getenv("MODAL_TTS_URL", "")
    MODAL_DEMUCS_URL: str = os.getenv("MODAL_DEMUCS_URL", "")
    MODAL_API_KEY: str = os.getenv("MODAL_API_KEY", "")
    
    # MinIO Storage
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin") # Koristi standardni minio default za dev
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = "uploads"
    MINIO_PUBLIC_ENDPOINT: str = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() == "true"
    
    DISABLE_OPENVOICE: bool = os.getenv("DISABLE_OPENVOICE", "False").lower() == "true"
    DISABLE_ENHANCE: bool = os.getenv("DISABLE_ENHANCE", "False").lower() == "true"
    
    ENHANCE_TAU: float = float(os.getenv("ENHANCE_TAU", "0.2"))
    ENHANCE_LAMBD: float = float(os.getenv("ENHANCE_LAMBD", "0.9"))
    
    TEMP_WORKSPACE: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../temp_workspace"))

    # JWT Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "insecure_default_secret_key_change_in_production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sinhronizuj_local.db") # Default na SQLite za dev

    # Security & CORS
    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

    # Monitoring
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")

settings = Settings()

