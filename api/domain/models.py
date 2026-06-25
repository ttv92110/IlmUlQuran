# api/domain/models.py

from datetime import datetime, timezone
from typing import Optional, List, Dict
from enum import Enum
from pydantic import BaseModel, Field, EmailStr, field_validator
# ==================== ENUMS ====================

class UserRole(str, Enum):
    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class NoteStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class WaqfType(str, Enum):
    LAZIM = "م"
    JAAIZ = "ج"
    MURAKH_KHAS = "ط"
    SILE = "صلے"
    QILE = "قلے"
    LA = "لا"
    ZAJR = "ز"

class PartOfSpeech(str, Enum):
    NOUN = "noun"
    VERB = "verb"
    PARTICLE = "particle"

class VerbTense(str, Enum):
    PAST = "past"
    PRESENT = "present"
    COMMAND = "command"

class Gender(str, Enum):
    MASCULINE = "M"
    FEMININE = "F"

class Number(str, Enum):
    SINGULAR = "sg"
    DUAL = "du"
    PLURAL = "pl"

class NoteType(str, Enum):
    TAFSIR = "tafsir"
    LINGUISTIC = "linguistic"
    ABJAD = "abjad"
    HISTORICAL = "historical"
    RESEARCH = "research"
    GENERAL = "general"

# ==================== ABJAD ====================

class AbjadMapping(BaseModel):
    letter: str
    abjad_value: int = Field(..., ge=0, le=1000)
    description: Optional[str] = None
    modified_by: Optional[str] = None
    modified_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "letter": "ا",
                "abjad_value": 1,
                "description": "Alif",
                "modified_by": "admin",
                "modified_at": "2025-01-01T00:00:00Z"
            }
        }

# ==================== AUDIT ====================

class AuditLog(BaseModel):
    log_id: str
    user_id: str
    action: str
    entity_type: str
    entity_id: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    timestamp: datetime

# ==================== AYAH ====================

class WaqfMark(BaseModel):
    symbol: WaqfType
    meaning: str
    position_in_ayah: int

class Ayah(BaseModel):
    surah_number: int = Field(..., ge=1, le=114)
    ayah_number: int = Field(..., ge=1)
    global_ayah_number: int = Field(..., ge=1)
    arabic_text: str
    arabic_without_harakat: Optional[str] = ""
    arabic_normalized: Optional[str] = ""          # 🆕 from JSON
    transliteration: Optional[str] = ""
    translations: Dict[str, str] = Field(default_factory=dict)
    waqf_marks: List[WaqfMark] = Field(default_factory=list)
    sajdah_flag: bool = False
    ruku_end: bool = False
    juz_number: int
    hizb_number: int
    manzil_number: int
    ruku_number: int
    position_in_ruku: int = 1
    word_count: int = 0
    letter_count: int = 0
    letter_counts: Dict[str, int] = Field(default_factory=dict)
    symoble_count: int = 0
    symoble_counts: Dict[str, int] = Field(default_factory=dict)
    total_abjad: int = 0
    word_abjad_list: List[int] = Field(default_factory=list)
    unique_words_count: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "surah_number": 2,
                "ayah_number": 255,
                "global_ayah_number": 255,
                "arabic_text": "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ",
                "arabic_normalized": "الله لا اله الا هو الحي القيوم",
                "translations": {"ur": "اللہ کے سوا کوئی معبود نہیں"},
                "juz_number": 3,
                "hizb_number": 5,
                "manzil_number": 1,
                "ruku_number": 42,
                "position_in_ruku": 1,
                "sajdah_flag": False,
                "ruku_end": True,
                "word_abjad_list": [102, 66],
                "letter_counts": {"ا": 5, "ل": 8, "ه": 2},
                "symoble_counts": {"ْ":5, "ُ": 8, "َ": 3, "ِ": 1},
                "unique_words_count": 12
            }
        }

# ==================== GRAMMAR ====================

class GrammarInfo(BaseModel):
    word_id: str
    part_of_speech: PartOfSpeech
    gender: Optional[Gender] = None
    number: Optional[Number] = None
    is_definite: Optional[bool] = None
    case: Optional[str] = None
    verb_tense: Optional[VerbTense] = None
    verb_person: Optional[int] = None
    verb_gender: Optional[Gender] = None
    verb_number: Optional[Number] = None
    particle_type: Optional[str] = None
    syntax_role: Optional[str] = None
    morphology_notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "word_id": "1:1:1",
                "part_of_speech": "noun",
                "gender": "M",
                "number": "sg",
                "is_definite": False,
                "case": "genitive"
            }
        }

# ==================== NOTE ====================

class Note(BaseModel):
    note_id: str
    user_id: str
    ayah_global_id: int
    note_type: NoteType
    title: Optional[str] = None
    content: str
    status: NoteStatus = NoteStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "note_id": "abc-123",
                "user_id": "user_001",
                "ayah_global_id": 255,
                "note_type": "tafsir",
                "title": "Tafsir of Ayat-ul-Kursi",
                "content": "This ayah speaks about Allah's sovereignty...",
                "status": "pending"
            }
        }

# ==================== STATISTICS ====================

class Statistics(BaseModel):
    stat_id: str
    abjad_total: int
    last_updated: datetime = datetime.utcnow()

    class Config:
        json_schema_extra = {
            "example": {
                "stat_id": "surah:2",
                "abjad_total": 12345,
                "last_updated": "2025-01-01T00:00:00Z"
            }
        }

# ==================== SURAH ====================

class Surah(BaseModel):
    surah_number: int = Field(..., ge=1, le=114)
    arabic_name: str
    urdu_name: Optional[str] = "" 
    english_name: str
    meaning: str
    makki_madani: str
    total_ayat: int = Field(..., ge=1)
    total_words: int = Field(default=0, ge=0)
    total_letters: int = Field(default=0, ge=0)
    total_abjad: int = Field(default=0, ge=0)
    ruku_count: int = Field(default=0, ge=0)
    juz_info: List[int] = Field(default_factory=list)
    manzil_info: List[int] = Field(default_factory=list)
    hizb_info: List[int] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "surah_number": 1,
                "arabic_name": "الفاتحة",
                "urdu_name": "فاتحہ",
                "english_name": "Al-Fatiha",
                "meaning": "The Opening",
                "makki_madani": "Makki",
                "total_ayat": 7,
                "total_words": 29,
                "total_letters": 139,
                "total_abjad": 0,
                "ruku_count": 1,
                "juz_info": [1],
                "manzil_info": [1],
                "hizb_info": [1]
            }
        }

# ==================== USER ====================

class RegisterRequestExtended(BaseModel):
    name: str
    email: EmailStr
    password: str
    mobile: str
    cnic: str
    profile_pic: Optional[str] = ""
    cnic_pic: str

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    pin: str

class ResendPinRequest(BaseModel):
    email: EmailStr

class User(BaseModel):
    user_id: str
    name: str
    email: str
    role: UserRole = UserRole.USER
    hashed_password: str
    is_active: bool = True
    mobile: str
    cnic: str
    profile_pic: Optional[str] = None
    cnic_pic: Optional[str] = None
    email_verified: bool = False
    verification_pin: Optional[str] = None
    pin_expires: Optional[datetime] = None
    language: str = 'ur'   # نیا فیلڈ
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    
    @field_validator('last_login', mode='before')
    @classmethod
    def validate_last_login(cls, v):
        if v == 'None' or v == '':
            return None
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "Admin_0001",
                "name": "Arshad Ali",
                "email": "ttv92110@gmail.com",
                "role": "admin",
                "is_active": True
            }
        }
        
# ==================== WORD ====================

class Word(BaseModel):
    word_id: str
    surah_number: int
    ayah_number: int
    global_ayah_number: int
    position_in_ayah: int
    arabic_word: str
    arabic_without_harakat: Optional[str] = ""   # 🆕 from JSON (with_out_arabic)
    arabic_normalized: Optional[str] = ""        # 🆕 from JSON
    normalized_letters: Optional[str] = ""       # 🆕 from JSON (space-separated letters)
    root_word: Optional[str] = None
    transliteration: Optional[str] = None
    abjad_value: int = 0
    letter_count: int = 0
    letter_frequency: Dict[str, int] = Field(default_factory=dict)
    symoble_count: int = 0
    symoble_frequency: Dict[str, int] = Field(default_factory=dict)
    translations: Dict[str, str] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "word_id": "1:1:1",
                "surah_number": 1,
                "ayah_number": 1,
                "global_ayah_number": 1,
                "position_in_ayah": 1,
                "arabic_word": "بِسْمِ",
                "arabic_without_harakat": "بسم",
                "arabic_normalized": "بسم",
                "normalized_letters": "ب س م",
                "root_word": "ب س م",
                "transliteration": "bis'mi",
                "abjad_value": 102,
                "letter_count": 3,
                "letter_frequency": {"ب": 1, "س": 1, "م": 1},
                "symoble_count": 2,
                "symoble_frequency": {"ِ": 2},
                "translations": {"ur": "نام سے", "en": "In the name"}
            }
        }

# ==================== WORD OCCURRENCE ====================

class WordOccurrence(BaseModel):
    occurrence_id: str
    word_text: str
    surah_number: int
    ayah_number: int
    position_in_ayah: int
    global_ayah_number: int

    class Config:
        json_schema_extra = {
            "example": {
                "occurrence_id": "2:255:1",
                "word_text": "اللَّهُ",
                "surah_number": 2,
                "ayah_number": 255,
                "position_in_ayah": 1,
                "global_ayah_number": 255
            }
        }