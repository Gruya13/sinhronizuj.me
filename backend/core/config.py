import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Sinhronizuj.me"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "1GjlbjEfc1Z8Dus1lWEQsOegDK9iGYNP")
    
    # Modal Serverless Endpoints
    MODAL_STT_URL: str = os.getenv("MODAL_STT_URL", "")
    MODAL_SENSEVOICE_URL: str = os.getenv("MODAL_SENSEVOICE_URL", "")
    MODAL_TRANSLATOR_URL: str = os.getenv("MODAL_TRANSLATOR_URL", "")
    MODAL_LEKTOR_URL: str = os.getenv("MODAL_LEKTOR_URL", "")
    MODAL_TTS_URL: str = os.getenv("MODAL_TTS_URL", "")
    MODAL_DEMUCS_URL: str = os.getenv("MODAL_DEMUCS_URL", "")
    
    # MinIO Storage
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "sinhronizuj_storage")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "sinhronizuj_pass_2026")
    MINIO_BUCKET: str = "uploads"
    MINIO_PUBLIC_ENDPOINT: str = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://178.104.214.78:9000")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() == "true"
    
    DISABLE_OPENVOICE: bool = os.getenv("DISABLE_OPENVOICE", "False").lower() == "true"
    DISABLE_ENHANCE: bool = os.getenv("DISABLE_ENHANCE", "False").lower() == "true"
    
    ENHANCE_TAU: float = float(os.getenv("ENHANCE_TAU", "0.2"))
    ENHANCE_LAMBD: float = float(os.getenv("ENHANCE_LAMBD", "0.9"))
    
    TEMP_WORKSPACE: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../temp_workspace"))

    # JWT Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "4f7a3d9e8b7c6a5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://sinhronizuj_user:sinhronizuj_pass_2026@localhost:5432/sinhronizuj_db")

    # Monitoring
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")

settings = Settings()
