import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Sinhronizuj.me"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    RUNPOD_API_KEY: str = os.getenv("RUNPOD_API_KEY", "")
    
    # RunPod Serverless Endpoints
    RUNPOD_WHISPER_ID: str = os.getenv("RUNPOD_WHISPER_ID", "")
    RUNPOD_TRANSLATOR_ID: str = os.getenv("RUNPOD_TRANSLATOR_ID", "")
    RUNPOD_TTS_ID: str = os.getenv("RUNPOD_TTS_ID", "")
    
    # MinIO Storage
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "sinhronizuj_storage")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "sinhronizuj_pass_2026")
    MINIO_BUCKET: str = "uploads"
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "False").lower() == "true"
    
    TEMP_WORKSPACE: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../temp_workspace"))

settings = Settings()
