# api/core/common.py
# Consolidated utilities: cache, exceptions, helpers, logging, security, email, image

import json
import uuid
import re
import smtplib
import base64
import logging
import sys
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict, List, Callable
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from api.config import settings
from api.domain.models import User, UserRole

# ==================== CACHE ====================

logger_cache = logging.getLogger(__name__)

class Cache:
    """Simple in-memory cache with TTL. Can be extended to use Redis."""
    
    _instance = None
    _store: Dict[str, dict] = {}  # key -> {"value": any, "expires_at": datetime}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._store = {}
        return cls._instance
    
    async def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            entry = self._store[key]
            if entry["expires_at"] > datetime.utcnow():
                return entry["value"]
            else:
                del self._store[key]
        return None
    
    async def set(self, key: str, value: Any, ttl_seconds: int = 300):
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        self._store[key] = {"value": value, "expires_at": expires_at}
    
    async def delete(self, key: str):
        if key in self._store:
            del self._store[key]
    
    async def clear(self):
        self._store.clear()
    
    async def exists(self, key: str) -> bool:
        entry = self._store.get(key)
        if entry and entry["expires_at"] > datetime.utcnow():
            return True
        return False

_cache_instance = None

def get_cache() -> Cache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = Cache()
    return _cache_instance

# ==================== EXCEPTIONS ====================

class QuranException(Exception):
    """Base exception for all Quran platform errors."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class DuplicateAyahError(QuranException):
    def __init__(self, message: str = "Ayah already exists"):
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)

class InvalidWaqfError(QuranException):
    def __init__(self, message: str = "Invalid waqf symbol"):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)

class InvalidAyahError(QuranException):
    def __init__(self, message: str = "Invalid ayah data"):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)

class UnauthorizedError(QuranException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)

class ForbiddenError(QuranException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)

class NotFoundError(QuranException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)

def register_exception_handlers(app: FastAPI):
    """Register exception handlers for custom exceptions."""
    
    @app.exception_handler(QuranException)
    async def quran_exception_handler(request: Request, exc: QuranException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.__class__.__name__, "detail": exc.message}
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": "ValidationError", "detail": str(exc)}
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger = logging.getLogger(__name__)
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "InternalServerError", "detail": "An unexpected error occurred"}
        )

# ==================== HELPERS ====================

def generate_id(prefix: str = "") -> str:
    unique_part = str(uuid.uuid4()).replace("-", "")
    if prefix:
        return f"{prefix}_{unique_part}"
    return unique_part

def safe_json_parse(json_str: str, default: Any = None) -> Any:
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default

def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def calculate_global_ayah_number(surah_info: dict, surah: int, ayah: int) -> int:
    total = 0
    for i in range(1, surah):
        total += surah_info.get(str(i), {}).get("total_ayat", 0)
    total += ayah
    return total

def get_current_time_utc() -> datetime:
    return datetime.now(timezone.utc)

def remove_diacritics(text: str) -> str:
    diacritics = re.compile(r'[\u064B-\u065F\u0670]')
    return diacritics.sub('', text)

def normalize_arabic(text: str) -> str:
    replacements = {
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا',
        'ة': 'ه', 'ى': 'ي'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def validate_surah_number(surah: int) -> bool:
    return 1 <= surah <= 114

def validate_ayah_number(surah: int, ayah: int, surah_ayah_counts: dict) -> bool:
    max_ayah = surah_ayah_counts.get(str(surah), 0)
    return 1 <= ayah <= max_ayah

# ==================== LOGGING ====================

def setup_logging(log_level: str = "INFO", log_file: str = "logs/app.log"):
    log_path = Path(log_file).parent
    log_path.mkdir(parents=True, exist_ok=True)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10_485_760, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("gspread").setLevel(logging.WARNING)
    
    return root_logger

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

# ==================== SECURITY (password, JWT, auth deps) ====================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

get_password_hash = hash_password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(days=7)
    data.update({"exp": expire, "type": "refresh"})
    return jwt.encode(data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}")

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = credentials.credentials
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    # Lazy import to avoid circular dependency
    from api.repositories.sheets.sheets_repositories import UserSheetsRepository
    repo = UserSheetsRepository()
    user = await repo.get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated")
    return user

async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

def require_role(required_role: UserRole) -> Callable:
    async def role_checker(user: User = Depends(get_current_user)):
        role_order = {
            UserRole.GUEST: 0,
            UserRole.USER: 1,
            UserRole.MODERATOR: 2,
            UserRole.ADMIN: 3,
            UserRole.SUPER_ADMIN: 4
        }
        if role_order[user.role] < role_order[required_role]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return role_checker

# ==================== EMAIL UTILS ====================

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = None
SMTP_PASSWORD = None
FROM_EMAIL = None

# Load from environment (could also use settings, but keep as is)
 
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)

def send_pin_email(to_email: str, pin: str):
    subject = "Ilm Ul Quran - Email Verification PIN"
    body = f"Your verification PIN is: {pin}\n\nEnter this PIN on the website to complete your registration.\n\nThe PIN expires in 15 minutes."
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")
        print(f"PIN for {to_email}: {pin}")

# ==================== IMAGE UTILS ====================

def save_base64_image(base64_str: str, subfolder: str = "profiles") -> str:
    if not base64_str:
        return ""
    if ',' in base64_str:
        base64_str = base64_str.split(',')[1]
    image_data = base64.b64decode(base64_str)
    ext = "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = settings.DATA_DIR / "uploads" / subfolder
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / filename
    with open(filepath, "wb") as f:
        f.write(image_data)
    return str(filepath)