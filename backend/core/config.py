import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Sinhronizuj.me"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    
    # Modal Serverless Endpoints
    MODAL_STT_URL: str = os.getenv("MODAL_STT_URL", "")
    MODAL_SENSEVOICE_URL: str = os.getenv("MODAL_SENSEVOICE_URL", "")
    MODAL_TRANSLATOR_URL: str = os.getenv("MODAL_TRANSLATOR_URL", "")
    MODAL_LEKTOR_URL: str = os.getenv("MODAL_LEKTOR_URL", "")
    MODAL_JUDGE_URL: str = os.getenv("MODAL_JUDGE_URL", "")
    MODAL_TTS_URL: str = os.getenv("MODAL_TTS_URL", "")
    MODAL_DEMUCS_URL: str = os.getenv("MODAL_DEMUCS_URL", "")
    MODAL_DIARIZATION_URL: str = os.getenv("MODAL_DIARIZATION_URL", "")
    MODAL_WAV2LIP_URL: str = os.getenv("MODAL_WAV2LIP_URL", "")
    MODAL_API_KEY: str = os.getenv("MODAL_API_KEY", "")
    
    # Storage Configuration (Supports MinIO, Hetzner S3, Cloudflare R2)
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "minio") # minio, hetzner, r2, s3
    
    # Generičke S3 konfiguracije
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "")
    S3_PUBLIC_ENDPOINT: str = os.getenv("S3_PUBLIC_ENDPOINT", "")
    S3_SECURE: bool = os.getenv("S3_SECURE", "False").lower() == "true"
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    
    # MinIO Storage (fallback / default)
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    
    _minio_secret: str = os.getenv("MINIO_SECRET_KEY", "")
    if not _minio_secret:
        if os.getenv("ENVIRONMENT") == "production":
            raise ValueError("MINIO_SECRET_KEY mora biti definisan u produkcionom okruženju!")
        _minio_secret = "minioadmin"
    MINIO_SECRET_KEY: str = _minio_secret
    MINIO_BUCKET: str = "uploads"
    MINIO_PUBLIC_ENDPOINT: str = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() == "true"
    
    DISABLE_OPENVOICE: bool = os.getenv("DISABLE_OPENVOICE", "False").lower() == "true"
    DISABLE_ENHANCE: bool = os.getenv("DISABLE_ENHANCE", "False").lower() == "true"
    
    ENHANCE_TAU: float = float(os.getenv("ENHANCE_TAU", "0.2"))
    ENHANCE_LAMBD: float = float(os.getenv("ENHANCE_LAMBD", "0.9"))
    
    TEMP_WORKSPACE: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../temp_workspace"))
    BACKEND_URL: str = os.getenv("BACKEND_URL", "https://api.sinhronizuj.me")

    # Kvote i limiti (Zadatak 4)
    MAX_SINGLE_FILE_SIZE_MB: int = int(os.getenv("MAX_SINGLE_FILE_SIZE_MB", "250"))
    MAX_DAILY_UPLOAD_MB: int = int(os.getenv("MAX_DAILY_UPLOAD_MB", "1000"))
    MAX_DAILY_DURATION_SEC: int = int(os.getenv("MAX_DAILY_DURATION_SEC", "3600")) # 60 minuta po defaultu

    # JWT Security
    _jwt_secret: str = os.getenv("JWT_SECRET", "")
    if not _jwt_secret:
        if os.getenv("ENVIRONMENT") == "production":
            raise ValueError("JWT_SECRET mora biti definisan u produkcionom okruženju!")
        _jwt_secret = "insecure_default_secret_key_change_in_production"
    JWT_SECRET: str = _jwt_secret
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # Database Configuration
    _db_url: str = os.getenv("DATABASE_URL", "")
    if not _db_url:
        if os.getenv("ENVIRONMENT") == "production":
            raise ValueError("DATABASE_URL mora biti definisan u produkcionom okruženju!")
        _db_url = "sqlite:///./sinhronizuj_local.db"
    DATABASE_URL: str = _db_url

    # Security & CORS
    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://sinhronizuj.me,https://api.sinhronizuj.me").split(",")

    # Monitoring
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")

    def __init__(self):
        # Ako je izabran drugi provajder (Hetzner, R2, AWS S3), prepisujemo MINIO_* parametre radi kompatibilnosti
        if self.STORAGE_PROVIDER in ["hetzner", "r2", "s3"]:
            print(f"[STORAGE] Aktiviran provajder: {self.STORAGE_PROVIDER}")
            if self.S3_ENDPOINT:
                self.MINIO_ENDPOINT = self.S3_ENDPOINT
            if self.S3_ACCESS_KEY:
                self.MINIO_ACCESS_KEY = self.S3_ACCESS_KEY
            if self.S3_SECRET_KEY:
                self.MINIO_SECRET_KEY = self.S3_SECRET_KEY
            if self.S3_BUCKET:
                self.MINIO_BUCKET = self.S3_BUCKET
            if self.S3_PUBLIC_ENDPOINT:
                self.MINIO_PUBLIC_ENDPOINT = self.S3_PUBLIC_ENDPOINT
            self.MINIO_SECURE = self.S3_SECURE

settings = Settings()
