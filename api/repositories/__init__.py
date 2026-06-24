# api/repositories/__init__.py
from .base_repository import BaseRepository
from .interfaces_repository import SurahRepository
from .interfaces_repository import AyahRepository
from .interfaces_repository import WordRepository
from .interfaces_repository import AbjadMappingRepository
from .interfaces_repository import NoteRepository
from .interfaces_repository import UserRepository

# api/repositories/__init__.py
from .sheets.sheets_repositories import AyahSheetsRepository, WordSheetsRepository, AbjadSheetsRepository, NoteSheetsRepository, UserSheetsRepository, SurahSheetsRepository, AuditSheetsRepository

__all__ = [
    "BaseRepository",
    "SurahRepository",
    "AyahRepository",
    "WordRepository",
    "AbjadMappingRepository",
    "NoteRepository",
    "UserRepository",
    "SurahSheetsRepository",
    "AyahSheetsRepository",
    "WordSheetsRepository",
    "AbjadSheetsRepository",
    "NoteSheetsRepository",
    "UserSheetsRepository",
    "AuditSheetsRepository",
]

async def get_ayah_repo():
    return AyahSheetsRepository()

async def get_word_repo():
    return WordSheetsRepository()

async def get_abjad_mapping_repo():
    return AbjadSheetsRepository()