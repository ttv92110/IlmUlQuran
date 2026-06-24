# api/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME: str = "Ilm Ul Quran"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    API_V1_PREFIX: str = "/api/v1"
    
    # Google Sheets
    # Use environment variable for credentials JSON string (Vercel) or file locally
    GOOGLE_SHEETS_CREDENTIALS: str = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
    GOOGLE_SHEETS_CREDENTIALS_FILE: str = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "credentials.json")
    SPREADSHEET_ID: str = os.getenv("SPREADSHEET_ID", "")
    
    # JWT 
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Vercel: use /tmp for writable cache
    if os.getenv("VERCEL"):
        DATA_DIR = Path("/tmp/quran_data")
    else:
        BASE_DIR = Path(__file__).parent.parent
        DATA_DIR = BASE_DIR / "data"
    
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    
    # Background update interval (seconds)
    BACKGROUND_UPDATE_INTERVAL: int = 60

settings = Settings()