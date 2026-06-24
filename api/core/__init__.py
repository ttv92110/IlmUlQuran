# api/core/__init__.py
from .common import (
    QuranException, DuplicateAyahError, InvalidWaqfError,
    InvalidAyahError, UnauthorizedError, ForbiddenError,
    NotFoundError
) 
from .common import (setup_logging, get_logger, register_exception_handlers,
    generate_id, safe_json_parse, chunk_list, get_cache,  calculate_global_ayah_number, get_current_time_utc
)
 
from .common import (
    hash_password,
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_current_user_optional,
    require_role,
)
from .google_sheets_db import GoogleSheetsDB

__all__ = [
    "hash_password",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "get_current_user",
    "get_current_user_optional",
    "require_role",
    "GoogleSheetsDB",
]