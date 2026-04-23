import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Sinhronizuj.me"
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    RUNPOD_API_KEY: str = os.getenv("RUNPOD_API_KEY", "")
    RUNPOD_POD_ID: str = os.getenv("RUNPOD_POD_ID", "")
    TEMP_WORKSPACE: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../temp_workspace"))

settings = Settings()
