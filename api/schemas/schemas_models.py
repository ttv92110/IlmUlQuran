# api/schemas/models.py
# Consolidated schemas for Ilm Ul Quran

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Generic, TypeVar
from datetime import datetime
from fastapi import Query

from api.domain.models import WaqfType, NoteType, NoteStatus, UserRole

# ==================== COMMON / PAGINATION ====================

T = TypeVar('T')

class PaginationParams:
    """Dependency class for pagination query parameters."""
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=1000, description="Items per page")
    ):
        self.page = page
        self.page_size = page_size
        self.skip = (page - 1) * page_size
        self.limit = page_size

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=1000)
    total_pages: int

    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5
            }
        }

class MessageResponse(BaseModel):
    message: str
    success: bool = True

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int

# ==================== ABJAD ====================

class AbjadMappingResponse(BaseModel):
    letter: str
    abjad_value: int
    description: Optional[str]
    modified_by: Optional[str]
    modified_at: datetime

class AbjadMappingCreate(BaseModel):
    letter: str = Field(..., min_length=1, max_length=2)
    abjad_value: int = Field(..., ge=0, le=1000)
    description: Optional[str] = None

class AbjadMappingUpdate(BaseModel):
    abjad_value: Optional[int] = Field(None, ge=0, le=1000)
    description: Optional[str] = None

# ==================== AUTH ====================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    language: Optional[str] = 'ur'


class RegisterRequestExtended(BaseModel):
    name: str
    email: EmailStr
    password: str
    mobile: str
    cnic: str
    profile_pic: Optional[str] = ""
    cnic_pic: str
    language: Optional[str] = 'ur'

    @validator('password')
    def validate_password_length(cls, v):
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password must not exceed 72 bytes (approximately 72 characters)')
        return v


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)

    @validator('password')
    def validate_password_length(cls, v):
        # Check byte length (not character length) because bcrypt limit is 72 bytes
        if len(v.encode('utf-8')) > 72:
            raise ValueError('Password must not exceed 72 bytes (approximately 72 characters)')
        return v

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenRefresh(BaseModel):
    refresh_token: str

# ==================== AYAH ====================

class WaqfMarkSchema(BaseModel):
    symbol: WaqfType
    meaning: Optional[str] = None
    position_in_ayah: int = Field(..., ge=0)

class AyahUploadRequest(BaseModel):
    surah: int = Field(..., ge=1, le=114)
    ayah_number: int = Field(..., ge=1)
    arabic_text: str
    waqf: Optional[str] = None
    sajdah: bool = False
    rukuEnd: bool = False

    @validator('arabic_text')
    def text_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Arabic text cannot be empty')
        return v

    @validator('waqf')
    def validate_waqf_symbol(cls, v):
        if v and v not in [item.value for item in WaqfType]:
            raise ValueError(f'Invalid waqf symbol. Allowed: {[item.value for item in WaqfType]}')
        return v

class AyahResponse(BaseModel):
    surah_number: int
    ayah_number: int
    global_ayah_number: int
    arabic_text: str
    arabic_without_harakat: Optional[str] = ""
    transliteration: Optional[str] = ""
    translations: Dict[str, str]
    waqf_marks: List[WaqfMarkSchema]
    sajdah_flag: bool
    ruku_end: bool
    juz_number: int
    hizb_number: int
    manzil_number: int
    ruku_number: int
    position_in_ruku: int
    word_count: int
    letter_count: int
    total_abjad: int

class AyahUpdate(BaseModel):
    arabic_text: Optional[str] = None
    translations: Optional[Dict[str, str]] = None
    sajdah_flag: Optional[bool] = None
    ruku_end: Optional[bool] = None

# ==================== NOTE ====================

class NoteResponse(BaseModel):
    note_id: str
    user_id: str
    ayah_global_id: int
    note_type: NoteType
    title: Optional[str]
    content: str
    status: NoteStatus
    created_at: datetime
    verified_by: Optional[str]
    verified_at: Optional[datetime]

class NoteCreate(BaseModel):
    ayah_global_id: int = Field(..., ge=1)
    note_type: NoteType = NoteType.GENERAL
    title: Optional[str] = None
    content: str = Field(..., min_length=1)

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class NoteVerifyRequest(BaseModel):
    status: NoteStatus
    rejection_reason: Optional[str] = None

# ==================== SURAH ====================

class SurahResponse(BaseModel):
    surah_number: int
    arabic_name: str
    urdu_name: Optional[str] = ""   # was: urdu_name: str
    english_name: str
    meaning: str
    makki_madani: str
    total_ayat: int
    total_words: int
    total_letters: int
    total_abjad: int
    ruku_count: int
    juz_info: List[int]
    manzil_info: List[int]
    hizb_info: List[int]

class SurahCreate(BaseModel):
    surah_number: int = Field(..., ge=1, le=114)
    arabic_name: str
    urdu_name: str
    english_name: str
    meaning: str
    makki_madani: str
    total_ayat: int = Field(..., ge=1)
    ruku_count: int = Field(default=0, ge=0)

class SurahUpdate(BaseModel):
    arabic_name: Optional[str] = None
    urdu_name: Optional[str] = None
    english_name: Optional[str] = None
    meaning: Optional[str] = None
    makki_madani: Optional[str] = None
    total_ayat: Optional[int] = Field(None, ge=1)
    total_words: Optional[int] = Field(None, ge=0)
    total_letters: Optional[int] = Field(None, ge=0)
    total_abjad: Optional[int] = Field(None, ge=0)
    ruku_count: Optional[int] = Field(None, ge=0)

# ==================== TRANSLATION ====================

class TranslationUpdate(BaseModel):
    language_code: str
    translation_text: str

# ==================== USER ====================

class UserResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

class UserRoleUpdate(BaseModel):
    role: UserRole

# ==================== WORD ====================

class WordResponse(BaseModel):
    word_id: str
    surah_number: int
    ayah_number: int
    global_ayah_number: int
    position_in_ayah: int
    arabic_word: str
    root_word: Optional[str]
    root_meaning: Optional[str]
    urdu_meaning: Optional[str]
    english_meaning: Optional[str]
    transliteration: Optional[str]
    abjad_value: int

class WordCreate(BaseModel):
    surah_number: int
    ayah_number: int
    position_in_ayah: int
    arabic_word: str
    root_word: Optional[str] = None
    urdu_meaning: Optional[str] = None
    english_meaning: Optional[str] = None

class WordUpdate(BaseModel):
    root_word: Optional[str] = None
    root_meaning: Optional[str] = None
    urdu_meaning: Optional[str] = None
    english_meaning: Optional[str] = None
    transliteration: Optional[str] = None
    abjad_value: Optional[int] = Field(None, ge=0)