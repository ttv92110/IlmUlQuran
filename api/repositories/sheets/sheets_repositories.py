# api/repositories/sheets/sheets_repositories.py 
import json
import gspread
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Set
from oauth2client.service_account import ServiceAccountCredentials

from api.config import settings
from api.core.google_sheets_db import GoogleSheetsDB
from api.domain.models import (
    AbjadMapping, Ayah, Note, NoteStatus, Statistics,
    Surah, User, Word, WordOccurrence
)
from api.repositories.interfaces_repository import (
    AbjadMappingRepository, AyahRepository, NoteRepository,
    SurahRepository, UserRepository, WordRepository
)

logger = logging.getLogger(__name__)

# ==================== HELPER CONSTANTS ====================
DATETIME_FIELDS: Set[str] = {
    'modified_at', 'created_at', 'verified_at', 'last_login', 'updated_at'
}

# ==================== BASE SHEETS REPOSITORY ====================

class BaseSheetsRepository:
    """Base class for all Google Sheets repositories providing dict<->model conversion."""
    def __init__(self, worksheet_name: str):
        self.db = GoogleSheetsDB(settings.APP_NAME, worksheet_name)

    def _to_dict(self, obj: Any) -> Dict:
        data = obj.model_dump() if hasattr(obj, "model_dump") else (obj.dict() if hasattr(obj, "dict") else obj)
        for key, value in data.items():
            if isinstance(value, (list, dict)):
                data[key] = json.dumps(value, ensure_ascii=False)
        return data

    def _from_dict(self, data: Dict, model_class):
        if not data:
            return None
        cleaned = {}
        column_mapping = {'position': 'position_in_ayah'}
        
        # Define string fields that should become empty string if None
        string_fields = {
            'mobile', 'cnic', 'verification_pin', 'user_id', 'name', 'email',
            'role', 'hashed_password', 'profile_pic', 'cnic_pic',
            'root_word', 'root_meaning', 'arabic_word', 'urdu_meaning',
            'english_meaning', 'transliteration', 'word_text', 'occurrence_id',
            'urdu_name', 'arabic_name', 'english_name', 'meaning', 'makki_madani',
            'arabic_without_harakat', 'arabic_normalized', 'normalized_letters'
        }

        for k, v in data.items():
            mapped_key = column_mapping.get(k, k)

            # ---------- Handle None ----------
            if v is None:
                if mapped_key in string_fields:
                    cleaned[mapped_key] = ""
                elif mapped_key in DATETIME_FIELDS:
                    cleaned[mapped_key] = None
                else:
                    cleaned[mapped_key] = None
                continue

            # ---------- Handle empty string for numeric fields ----------
            if isinstance(v, str) and v.strip() == '':
                if mapped_key in ('position_in_ayah', 'surah_number', 'ayah_number',
                                'global_ayah_number', 'abjad_value', 'letter_count',
                                'word_count', 'total_abjad', 'unique_words_count',
                                'juz_number', 'hizb_number', 'manzil_number',
                                'ruku_number', 'position_in_ruku'):
                    cleaned[mapped_key] = 0
                elif mapped_key in DATETIME_FIELDS:
                    cleaned[mapped_key] = None
                else:
                    cleaned[mapped_key] = None
                continue

            # ---------- Role conversion ----------
            if mapped_key == 'role' and isinstance(v, str):
                if v.startswith('UserRole.'):
                    v = v.split('.')[-1].lower()
                else:
                    v = v.lower()

            # ---------- JSON fields ----------
            if mapped_key in ('juz_info', 'manzil_info', 'hizb_info', 'word_abjad_list',
                            'letter_frequency', 'translations', 'waqf_marks', 'letter_counts'):
                if isinstance(v, int):
                    cleaned[mapped_key] = [v]
                elif isinstance(v, str) and (v.startswith('[') or v.startswith('{')):
                    try:
                        cleaned[mapped_key] = json.loads(v)
                    except:
                        cleaned[mapped_key] = [] if mapped_key in ('juz_info', 'manzil_info', 'hizb_info', 'word_abjad_list') else {}
                elif isinstance(v, list):
                    cleaned[mapped_key] = v
                else:
                    cleaned[mapped_key] = [] if mapped_key in ('juz_info', 'manzil_info', 'hizb_info', 'word_abjad_list') else {}
            else:
                # Try to parse JSON for any string that looks like array/object
                if isinstance(v, str) and (v.startswith('[') or v.startswith('{')):
                    try:
                        cleaned[mapped_key] = json.loads(v)
                    except:
                        cleaned[mapped_key] = v
                else:
                    cleaned[mapped_key] = v

        # ---------- Convert integers to strings for string fields ----------
        for field in string_fields:
            if field in cleaned and isinstance(cleaned[field], int):
                cleaned[field] = str(cleaned[field])

        return model_class(**cleaned)

# ==================== SINGLETON SHEETS CLIENT ====================

class SheetsClient:
    """Singleton wrapper for Google Sheets API."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        try:
            scope = ["https://spreadsheets.google.com/feeds", 
                     "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                settings.GOOGLE_SHEETS_CREDENTIALS_FILE, scope
            )
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(settings.GOOGLE_SHEETS_SPREADSHEET_ID)
            logger.info("Google Sheets client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
            raise
    
    def get_worksheet(self, name: str):
        try:
            return self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            logger.warning(f"Worksheet '{name}' not found, creating it...")
            return self.spreadsheet.add_worksheet(title=name, rows="1000", cols="20")
    
    def get_all_records(self, sheet_name: str) -> List[Dict[str, Any]]:
        ws = self.get_worksheet(sheet_name)
        return ws.get_all_records()
    
    def append_row(self, sheet_name: str, row: List[Any]) -> None:
        ws = self.get_worksheet(sheet_name)
        ws.append_row([str(cell) if cell is not None else "" for cell in row])
    
    def update_row(self, sheet_name: str, row_index: int, row: List[Any]) -> None:
        ws = self.get_worksheet(sheet_name)
        col_count = len(row)
        end_col = chr(64 + col_count) if col_count <= 26 else 'A'
        range_label = f"A{row_index}:{end_col}{row_index}"
        ws.update(range_label, [row])
    
    def find_row_by_column_value(self, sheet_name: str, column_name: str, value: Any) -> int:
        records = self.get_all_records(sheet_name)
        for idx, record in enumerate(records, start=2):
            if str(record.get(column_name)) == str(value):
                return idx
        return -1

# ==================== ABJAD SHEETS REPOSITORY ====================

class AbjadSheetsRepository(AbjadMappingRepository, BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "abjad_mappings")

    async def get(self, letter: str) -> Optional[AbjadMapping]:
        records = self.db.read_all()
        for rec in records:
            if rec.get("letter") == letter:
                return self._from_dict(rec, AbjadMapping)
        return None

    async def get_all(self, filters: Optional[Dict] = None, skip: int = 0, limit: int = 100) -> List[AbjadMapping]:
        records = self.db.read_all()
        if filters:
            records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
        records = records[skip:skip+limit]
        return [self._from_dict(r, AbjadMapping) for r in records]

    async def add(self, mapping: AbjadMapping) -> AbjadMapping:
        if await self.exists({"letter": mapping.letter}):
            raise ValueError(f"Mapping for {mapping.letter} already exists")
        self.db._ensure_connected()
        worksheet = self.db._worksheet
        if not worksheet:
            raise Exception("No worksheet connection")
        headers = worksheet.row_values(1)
        if not headers:
            headers = ["letter", "abjad_value", "description", "modified_by", "modified_at"]
            worksheet.append_row(headers)
        data = self._to_dict(mapping)
        row = [str(data.get(h, "")) for h in headers]
        worksheet.append_row(row)
        return mapping

    async def update(self, id: str, mapping: AbjadMapping) -> Optional[AbjadMapping]:
        rec = self.db.find_by_id(id, id_field="letter")
        if not rec:
            return None
        self.db.update(id, self._to_dict(mapping), id_field="letter")
        return mapping

    async def delete(self, id: str) -> bool:
        return self.db.delete(id, id_field="letter")

    async def exists(self, filters: Dict) -> bool:
        records = self.db.read_all()
        return any(all(rec.get(k) == v for k, v in filters.items()) for rec in records)

    async def get_value(self, letter: str) -> Optional[int]:
        mapping = await self.get(letter)
        return mapping.abjad_value if mapping else None

    async def get_all_mappings(self) -> Dict[str, int]:
        mappings = await self.get_all()
        return {m.letter: m.abjad_value for m in mappings}

    async def update_mapping(self, letter: str, new_value: int, modified_by: str) -> Optional[AbjadMapping]:
        mapping = await self.get(letter)
        if mapping:
            mapping.abjad_value = new_value
            mapping.modified_by = modified_by
            mapping.modified_at = datetime.utcnow()
            return await self.update(letter, mapping)
        return None

# ==================== AUDIT SHEETS REPOSITORY ====================

class AuditSheetsRepository(BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "audit_logs")

    async def add_log(self, user_id: str, action: str, entity_type: str, entity_id: str,
                      old_value: Any = None, new_value: Any = None) -> Dict:
        log = {
            "log_id": str(uuid.uuid4()),
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_value": old_value,
            "new_value": new_value,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.db.insert(log)
        return log

    async def get_logs_for_user(self, user_id: str, skip: int = 0, limit: int = 100) -> List[Dict]:
        records = self.db.read_all()
        filtered = [r for r in records if r.get("user_id") == user_id]
        return filtered[skip:skip+limit]

    async def get_all_logs(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        records = self.db.read_all()
        return records[skip:skip+limit]

# ==================== AYAH SHEETS REPOSITORY ====================

class AyahSheetsRepository(AyahRepository, BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "ayahs")

    async def get(self, id: str) -> Optional[Ayah]:
        records = self.db.read_all()
        for rec in records:
            if id.startswith("global_"):
                if str(rec.get("global_ayah_number")) == id.replace("global_", ""):
                    return self._from_dict(rec, Ayah)
            else:
                if f"{rec.get('surah_number')}_{rec.get('ayah_number')}" == id:
                    return self._from_dict(rec, Ayah)
        return None

    async def get_all(self, filters: Optional[Dict] = None, skip: int = 0, limit: int = 100) -> List[Ayah]:
        records = self.db.read_all()
        if filters:
            records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
        records = records[skip:skip+limit]
        return [self._from_dict(r, Ayah) for r in records]

    async def add(self, ayah: Ayah) -> Ayah:
        if await self.exists({"surah_number": ayah.surah_number, "ayah_number": ayah.ayah_number}):
            raise ValueError(f"Ayah {ayah.surah_number}:{ayah.ayah_number} already exists")
        data = self._to_dict(ayah)
        self.db.insert(data)
        return ayah

    async def update(self, id: str, ayah: Ayah) -> Optional[Ayah]:
        surah, ayah_num = map(int, id.split("_"))
        records = self.db.read_all()
        for idx, rec in enumerate(records):
            if rec.get("surah_number") == surah and rec.get("ayah_number") == ayah_num:
                new_data = self._to_dict(ayah)
                self.db.update(rec.get("id"), new_data, id_field="id")
                return ayah
        return None

    async def delete(self, id: str) -> bool:
        return False  # not implemented

    async def exists(self, filters: Dict) -> bool:
        records = self.db.read_all()
        return any(all(rec.get(k) == v for k, v in filters.items()) for rec in records)

    async def get_by_surah_ayah(self, surah: int, ayah: int) -> Optional[Ayah]:
        return await self.get(f"{surah}_{ayah}")

    async def get_by_global_number(self, global_number: int) -> Optional[Ayah]:
        return await self.get(f"global_{global_number}")

    async def get_by_surah(self, surah_number: int, skip: int = 0, limit: int = 100) -> List[Ayah]:
        return await self.get_all({"surah_number": surah_number}, skip, limit)

    async def get_by_juz(self, juz_number: int, skip: int = 0, limit: int = 100) -> List[Ayah]:
        return await self.get_all({"juz_number": juz_number}, skip, limit)

    async def get_by_ruku(self, ruku_number: int, skip: int = 0, limit: int = 100) -> List[Ayah]:
        return await self.get_all({"ruku_number": ruku_number}, skip, limit)

# ==================== NOTE SHEETS REPOSITORY ====================

class NoteSheetsRepository(NoteRepository, BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "notes")

    async def get(self, id: str) -> Optional[Note]:
        rec = self.db.find_by_id(id, id_field="note_id")
        return self._from_dict(rec, Note) if rec else None

    async def get_all(self, filters: Optional[Dict] = None, skip: int = 0, limit: int = 100) -> List[Note]:
        records = self.db.read_all()
        if filters:
            records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
        records = records[skip:skip+limit]
        return [self._from_dict(r, Note) for r in records]

    async def add(self, note: Note) -> Note:
        if await self.exists({"note_id": note.note_id}):
            raise ValueError(f"Note {note.note_id} exists")
        self.db.insert(self._to_dict(note))
        return note

    async def update(self, id: str, note: Note) -> Optional[Note]:
        rec = self.db.find_by_id(id, id_field="note_id")
        if not rec:
            return None
        self.db.update(id, self._to_dict(note), id_field="note_id")
        return note

    async def delete(self, id: str) -> bool:
        return self.db.delete(id, id_field="note_id")

    async def exists(self, filters: Dict) -> bool:
        records = self.db.read_all()
        return any(all(rec.get(k) == v for k, v in filters.items()) for rec in records)

    async def get_by_ayah(self, ayah_global_id: int, status: Optional[NoteStatus] = None) -> List[Note]:
        filters = {"ayah_global_id": ayah_global_id}
        if status:
            filters["status"] = status.value
        return await self.get_all(filters)

    async def get_by_user(self, user_id: str, status: Optional[NoteStatus] = None) -> List[Note]:
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status.value
        return await self.get_all(filters)

    async def get_pending_notes(self, skip: int = 0, limit: int = 100) -> List[Note]:
        return await self.get_all({"status": NoteStatus.PENDING.value}, skip, limit)

    async def verify_note(self, note_id: str, status: NoteStatus, verified_by: str, rejection_reason: Optional[str] = None) -> Optional[Note]:
        note = await self.get(note_id)
        if note:
            note.status = status
            note.verified_by = verified_by
            note.verified_at = datetime.utcnow()
            note.rejection_reason = rejection_reason
            return await self.update(note_id, note)
        return None

# ==================== STATISTICS SHEETS REPOSITORY ====================

class StatisticsSheetsRepository(BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "statistics")

    async def get(self, stat_id: str) -> Optional[Statistics]:
        rec = self.db.find_by_id(stat_id, id_field="stat_id")
        return self._from_dict(rec, Statistics) if rec else None

    async def set(self, stat_id: str, abjad_total: int) -> Statistics:
        existing = await self.get(stat_id)
        stat = Statistics(stat_id=stat_id, abjad_total=abjad_total)
        if existing:
            await self.update(stat_id, stat)
        else:
            await self.add(stat)
        return stat

    async def add(self, stat: Statistics) -> Statistics:
        if await self.exists({"stat_id": stat.stat_id}):
            raise ValueError(f"Statistic {stat.stat_id} already exists")
        self.db.insert(self._to_dict(stat))
        return stat

    async def update(self, id: str, stat: Statistics) -> Optional[Statistics]:
        rec = self.db.find_by_id(id, id_field="stat_id")
        if not rec:
            return None
        self.db.update(id, self._to_dict(stat), id_field="stat_id")
        return stat

    async def delete(self, id: str) -> bool:
        return self.db.delete(id, id_field="stat_id")

    async def exists(self, filters: Dict) -> bool:
        records = self.db.read_all()
        return any(all(rec.get(k) == v for k, v in filters.items()) for rec in records)

# ==================== SURAH SHEETS REPOSITORY ====================

class SurahSheetsRepository(SurahRepository, BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "surahs")

    async def get(self, id: str) -> Optional[Surah]:
        rec = self.db.find_by_id(id, id_field="surah_number")
        return self._from_dict(rec, Surah) if rec else None

    async def get_all(self, filters: Optional[Dict] = None, skip: int = 0, limit: int = 100) -> List[Surah]:
        records = self.db.read_all()
        if filters:
            records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
        records = records[skip:skip+limit]
        return [self._from_dict(r, Surah) for r in records]

    async def add(self, surah: Surah) -> Surah:
        if await self.exists({"surah_number": surah.surah_number}):
            raise ValueError(f"Surah {surah.surah_number} exists")
        self.db.insert(self._to_dict(surah))
        return surah

    async def update(self, id: str, surah: Surah) -> Optional[Surah]:
        rec = self.db.find_by_id(id, id_field="surah_number")
        if not rec:
            return None
        self.db.update(id, self._to_dict(surah), id_field="surah_number")
        return surah

    async def delete(self, id: str) -> bool:
        return self.db.delete(id, id_field="surah_number")

    async def exists(self, filters: Dict) -> bool:
        records = self.db.read_all()
        return any(all(rec.get(k) == v for k, v in filters.items()) for rec in records)

    async def get_by_number(self, surah_number: int) -> Optional[Surah]:
        return await self.get(str(surah_number))

    async def get_all_with_pagination(self, skip: int = 0, limit: int = 100) -> List[Surah]:
        return await self.get_all(skip=skip, limit=limit)

    async def update_statistics(self, surah_number: int, total_words: int, total_letters: int, total_abjad: int) -> Optional[Surah]:
        surah = await self.get_by_number(surah_number)
        if surah:
            surah.total_words = total_words
            surah.total_letters = total_letters
            surah.total_abjad = total_abjad
            return await self.update(str(surah_number), surah)
        return None

# ==================== TRANSLATION REPOSITORY ====================

class TranslationRepository(BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "translations")

    async def get_supported_languages(self) -> List[Dict]:
        records = self.db.read_all()
        return records

# ==================== USER SHEETS REPOSITORY ====================

class UserSheetsRepository(UserRepository, BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "users")

    async def get(self, id: str) -> Optional[User]:
        rec = self.db.find_by_id(id, id_field="user_id")
        return self._from_dict(rec, User) if rec else None

    async def get_all(self, filters: Optional[Dict] = None, skip: int = 0, limit: int = 100) -> List[User]:
        records = self.db.read_all()
        if filters:
            records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
        records = records[skip:skip+limit]
        return [self._from_dict(r, User) for r in records]

    async def add(self, user: User) -> User:
        if await self.exists({"email": user.email}):
            raise ValueError(f"User with email {user.email} exists")
        self.db.insert(self._to_dict(user))
        return user

    async def update(self, id: str, user: User) -> Optional[User]:
        rec = self.db.find_by_id(id, id_field="user_id")
        if not rec:
            return None
        self.db.update(id, self._to_dict(user), id_field="user_id")
        return user

    async def delete(self, id: str) -> bool:
        return self.db.delete(id, id_field="user_id")

    async def exists(self, filters: Dict) -> bool:
        records = self.db.read_all()
        return any(all(rec.get(k) == v for k, v in filters.items()) for rec in records)

    async def get_by_email(self, email: str) -> Optional[User]:
        users = await self.get_all({"email": email})
        return users[0] if users else None

    async def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        return await self.get_all({"is_active": True}, skip, limit)

    async def update_last_login(self, user_id: str) -> Optional[User]:
        user = await self.get(user_id)
        if user:
            user.last_login = datetime.utcnow()
            return await self.update(user_id, user)
        return None

    async def get_by_mobile(self, mobile: str) -> Optional[User]:
        users = await self.get_all({"mobile": mobile})
        return users[0] if users else None

    async def get_by_cnic(self, cnic: str) -> Optional[User]:
        users = await self.get_all({"cnic": cnic})
        return users[0] if users else None

# ==================== WORD OCCURRENCE SHEETS REPOSITORY ====================

class WordOccurrenceSheetsRepository(BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "word_occurrences")

    async def add_occurrence(self, occurrence: WordOccurrence) -> WordOccurrence:
        if await self.exists({"occurrence_id": occurrence.occurrence_id}):
            raise ValueError(f"Occurrence {occurrence.occurrence_id} already exists")
        self.db.insert(self._to_dict(occurrence))
        return occurrence

    async def add_occurrences_batch(self, occurrences: List[WordOccurrence]) -> List[WordOccurrence]:
        added = []
        for occ in occurrences:
            added.append(await self.add_occurrence(occ))
        return added

    async def exists(self, filters: Dict) -> bool:
        records = self.db.read_all()
        return any(all(rec.get(k) == v for k, v in filters.items()) for rec in records)

    async def get_occurrences_by_word(self, word_text: str) -> List[WordOccurrence]:
        records = self.db.read_all()
        filtered = [r for r in records if r.get("word_text") == word_text]
        return [self._from_dict(r, WordOccurrence) for r in filtered]

    async def get_occurrence_count_in_ayah(self, word_text: str, surah: int, ayah: int) -> int:
        occurrences = await self.get_occurrences_by_word(word_text)
        return sum(1 for o in occurrences if o.surah_number == surah and o.ayah_number == ayah)

    async def get_occurrence_count_in_surah(self, word_text: str, surah: int) -> int:
        occurrences = await self.get_occurrences_by_word(word_text)
        return sum(1 for o in occurrences if o.surah_number == surah)

    async def get_total_occurrence_count(self, word_text: str) -> int:
        occurrences = await self.get_occurrences_by_word(word_text)
        return len(occurrences)

    async def delete_by_ayah(self, surah: int, ayah: int) -> None:
        records = self.db.read_all()
        for idx, rec in enumerate(records, start=2):
            if rec.get("surah_number") == surah and rec.get("ayah_number") == ayah:
                self.db.delete(rec.get("occurrence_id"), id_field="occurrence_id")

# ==================== WORD SHEETS REPOSITORY ====================

class WordSheetsRepository(WordRepository, BaseSheetsRepository):
    def __init__(self):
        BaseSheetsRepository.__init__(self, "words")

    async def get(self, id: str) -> Optional[Word]:
        rec = self.db.find_by_id(id, id_field="word_id")
        return self._from_dict(rec, Word) if rec else None

    async def get_all(self, filters: Optional[Dict] = None, skip: int = 0, limit: int = 100) -> List[Word]:
        records = self.db.read_all()
        if filters:
            records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
        records = records[skip:skip+limit]
        return [self._from_dict(r, Word) for r in records]

    async def add(self, word: Word) -> Word:
        if await self.exists({"word_id": word.word_id}):
            raise ValueError(f"Word {word.word_id} already exists")
        self.db._ensure_connected()
        if not self.db._worksheet:
            raise Exception("No worksheet connection")
        row = [
            word.word_id, word.surah_number, word.ayah_number, word.global_ayah_number,
            word.position_in_ayah, word.arabic_word, word.root_word or "", word.root_meaning or "",
            word.urdu_meaning or "", word.english_meaning or "", word.transliteration or "",
            word.abjad_value, json.dumps(word.translations)
        ]
        self.db._worksheet.append_row([str(cell) for cell in row])
        return word

    async def update(self, id: str, word: Word) -> Optional[Word]:
        rec = self.db.find_by_id(id, id_field="word_id")
        if not rec:
            return None
        self.db.update(id, self._to_dict(word), id_field="word_id")
        return word

    async def delete(self, id: str) -> bool:
        return self.db.delete(id, id_field="word_id")

    async def exists(self, filters: Dict) -> bool:
        records = self.db.read_all()
        return any(all(rec.get(k) == v for k, v in filters.items()) for rec in records)

    async def get_by_ayah(self, surah: int, ayah: int) -> List[Word]:
        return await self.get_all({"surah_number": surah, "ayah_number": ayah})

    async def get_by_root(self, root_word: str) -> List[Word]:
        return await self.get_all({"root_word": root_word})

    async def update_abjad_for_ayah(self, surah: int, ayah: int, abjad_values: Dict[int, int]) -> None:
        words = await self.get_by_ayah(surah, ayah)
        for w in words:
            if w.position_in_ayah in abjad_values:
                w.abjad_value = abjad_values[w.position_in_ayah]
                await self.update(w.word_id, w)