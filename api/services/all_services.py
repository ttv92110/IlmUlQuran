# api/services/all_services.py
# Consolidated all services: AbjadEngine, AdminService, AuthService, AutoAnalysis,
# AyahService, BackgroundUpdater, LetterAnalyticsService, NoteService,
# QuranService, SearchEngine, WordOccurrenceService, WordService

import re
import json
import uuid
import random
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from collections import Counter
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext 

from api.config import settings
from api.core.common import get_cache, send_pin_email, save_base64_image 
from api.domain.models import (
    Ayah, WaqfMark, WaqfType, Word, WordOccurrence, Note, NoteStatus,
    Surah, User, UserRole
)
from api.repositories.interfaces_repository import (
    AbjadMappingRepository, AyahRepository, WordRepository, NoteRepository,
    SurahRepository, UserRepository
)
from api.repositories.sheets.sheets_repositories import ( 
    StatisticsSheetsRepository, WordOccurrenceSheetsRepository
)

logger = logging.getLogger(__name__)

# ==================== ABJAD ENGINE ====================

class AbjadEngine:
    def __init__(self, mapping_repo: AbjadMappingRepository):
        self.mapping_repo = mapping_repo
        self._cache: Dict[str, int] = {}

    async def _load_mapping(self, letter: str) -> int:
        if letter in self._cache:
            return self._cache[letter]
        mapping = await self.mapping_repo.get(letter)
        value = mapping.abjad_value if mapping else 0
        self._cache[letter] = value
        return value

    async def calculate_word_abjad(self, word: str) -> int:
        clean_word = re.sub(r'[^\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', '', word)
        total = 0
        for char in clean_word:
            total += await self._load_mapping(char)
        return total

    async def calculate_ayah_abjad(self, words: list[str]) -> int:
        total = 0
        for w in words:
            total += await self.calculate_word_abjad(w)
        return total

    async def recalculate_surah_abjad(self, surah_number: int, ayah_repo) -> int:
        ayahs = await ayah_repo.get_by_surah(surah_number)
        total = 0
        for ayah in ayahs:
            total += ayah.total_abjad
        return total

    async def get_letter_value(self, letter: str) -> int:
        return await self._load_mapping(letter)

    async def refresh_cache(self):
        mappings = await self.mapping_repo.get_all_mappings()
        self._cache = mappings

# ==================== ADMIN SERVICE ====================

class AdminService:
    def __init__(self, ayah_repo: AyahRepository, note_repo: NoteRepository,
                 user_repo: UserRepository, abjad_repo: AbjadMappingRepository,
                 abjad_engine: AbjadEngine, auto_analysis: 'AutoAnalysisService',
                 search_engine: 'SearchEngine', word_occurrence_service: 'WordOccurrenceService',
                 background_updater: 'BackgroundUpdater'):
        self.ayah_repo = ayah_repo
        self.note_repo = note_repo
        self.user_repo = user_repo
        self.abjad_repo = abjad_repo
        self.abjad_engine = abjad_engine
        self.auto_analysis = auto_analysis
        self.search_engine = search_engine
        self.word_occurrence_service = word_occurrence_service
        self.background_updater = background_updater

    async def create_ayah(self, ayah_data: dict) -> Ayah:
        ayah = Ayah(**ayah_data)
        result = await self.ayah_repo.add(ayah)
        await self.background_updater.schedule_recalculation(ayah.surah_number, ayah.ayah_number)
        return result

    async def on_ayah_words_updated(self, surah: int, ayah: int):
        await self.word_occurrence_service.rebuild_occurrences_for_ayah(surah, ayah)

    async def ayah_exists(self, surah: int, ayah_number: int) -> bool:
        return await self.ayah_repo.exists({"surah_number": surah, "ayah_number": ayah_number})

    async def verify_note(self, note_id: str, status: str, verified_by: str, rejection_reason: str = None) -> Optional[Note]:
        if status not in ["verified", "rejected"]:
            raise ValueError("Status must be 'verified' or 'rejected'")
        note_status = NoteStatus.VERIFIED if status == "verified" else NoteStatus.REJECTED
        return await self.note_repo.verify_note(note_id, note_status, verified_by, rejection_reason)

    async def update_user_role(self, user_id: str, new_role: UserRole) -> Optional[dict]:
        user = await self.user_repo.get(user_id)
        if not user:
            return None
        user.role = new_role
        await self.user_repo.update(user_id, user)
        return {"user_id": user_id, "role": new_role.value}

    async def ban_user(self, user_id: str) -> bool:
        user = await self.user_repo.get(user_id)
        if not user:
            return False
        user.is_active = False
        await self.user_repo.update(user_id, user)
        return True

    async def activate_user(self, user_id: str) -> bool:
        user = await self.user_repo.get(user_id)
        if not user:
            return False
        user.is_active = True
        await self.user_repo.update(user_id, user)
        return True

    async def update_abjad_mapping(self, letter: str, new_value: int, modified_by: str) -> bool:
        mapping = await self.abjad_repo.update_mapping(letter, new_value, modified_by)
        if mapping:
            await self.abjad_engine.refresh_cache()
            await self.search_engine.build_indexes()
            return True
        return False

    async def rebuild_search_indexes(self):
        await self.search_engine.build_indexes()

    async def recalculate_surah_statistics(self, surah_number: int):
        pass

# ==================== AUTH SERVICE ====================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def create_refresh_token(self, data: dict) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
        data.update({"exp": expire, "type": "refresh"})
        return jwt.encode(data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async def register_user(self, name: str, email: str, password: str,
                            mobile: str, cnic: str, profile_pic_base64: str = "",
                            cnic_pic_base64: str = "", language: str = "ur") -> Dict[str, Any]:
        existing_email = await self.user_repo.get_by_email(email)
        if existing_email:
            raise ValueError("Email already registered")
        existing_mobile = await self.user_repo.get_by_mobile(mobile)
        if existing_mobile:
            raise ValueError("Mobile number already registered")
        existing_cnic = await self.user_repo.get_by_cnic(cnic)
        if existing_cnic:
            raise ValueError("CNIC already registered")
        profile_pic_path = save_base64_image(profile_pic_base64, "profiles") if profile_pic_base64 else ""
        cnic_pic_path = save_base64_image(cnic_pic_base64, "cnic") if cnic_pic_base64 else ""
        pin = str(random.randint(100000, 999999))
        pin_expires = datetime.now(timezone.utc) + timedelta(minutes=15)

        user_dict = {
            "user_id": str(uuid.uuid4()),
            "name": name,
            "email": email,
            "role": UserRole.USER.value,
            "hashed_password": self.hash_password(password),
            "created_at": datetime.now(timezone.utc),  # datetime object
            "last_login": None,
            "is_active": True,
            "mobile": mobile,
            "cnic": cnic,
            "language": language,
            "profile_pic": profile_pic_path,
            "cnic_pic": cnic_pic_path,
            "email_verified": False,
            "verification_pin": pin,
            "pin_expires": pin_expires
        }
        user = User(**user_dict)
        await self.user_repo.add(user)
        send_pin_email(email, pin)
        return {"user_id": user.user_id, "email": email, "message": "Registration pending. Check email for PIN."}

    async def verify_email(self, email: str, pin: str) -> bool:
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise ValueError("User not found")
        if user.email_verified:
            raise ValueError("Email already verified")
        if user.verification_pin != pin:
            raise ValueError("Invalid PIN")
        if user.pin_expires and user.pin_expires < datetime.now(timezone.utc):
            raise ValueError("PIN expired. Request a new one.")
        user.email_verified = True
        user.verification_pin = None
        user.pin_expires = None  # Set to None after verification
        # Update user in repository
        await self.user_repo.update(user.user_id, user)
        return True
    
    async def resend_pin(self, email: str) -> None:
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise ValueError("User not found")
        if user.email_verified:
            raise ValueError("Email already verified")
        pin = str(random.randint(100000, 999999))
        user.verification_pin = pin
        user.pin_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        await self.user_repo.update(user.user_id, user)
        send_pin_email(email, pin)

    async def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        user = await self.user_repo.get_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            raise ValueError("Account is deactivated")
        if not user.email_verified:
            raise ValueError("Email not verified. Please verify using the PIN sent to your email.")
        user.last_login = datetime.now(timezone.utc)
        await self.user_repo.update(user.user_id, user)
        
        return {"user_id": user.user_id, "name": user.name, "email": user.email, "role": user.role.value, "language": user.language}
    
    async def update_user_language(self, user_id: str, language: str) -> Optional[User]:
        user = await self.user_repo.get(user_id)
        if user:
            user.language = language
            await self.user_repo.update(user_id, user)
            return user
        return None

# ==================== AUTO ANALYSIS SERVICE ====================

ARABIC_LETTERS = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
DIACRITICS_PATTERN = re.compile(r'[\u064B-\u065F\u0670]')

class AutoAnalysisService:
    def __init__(self):
        self.juz_boundaries = self._load_json("juz_boundaries.json")
        self.hizb_boundaries = self._load_json("hizb_boundaries.json")
        self.manzil_boundaries = self._load_json("manzil_boundaries.json")
        self.global_ayah_map = self._load_json("global_ayah_map.json")

    def _load_json(self, filename: str) -> dict:
        path = Path(__file__).parent.parent / "metadata" / filename
        if not path.exists():
            print(f"Warning: metadata file {filename} not found")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _extract_arabic_letters(self, text: str) -> str:
        return ''.join(ARABIC_LETTERS.findall(text))

    async def auto_detect_position(self, surah: int, ayah_num: int) -> dict:
        key = f"{surah}:{ayah_num}"
        global_ayah = self.global_ayah_map.get(key)
        if not global_ayah:
            global_ayah = self._calculate_global_ayah(surah, ayah_num)
        juz = self._find_juz(global_ayah)
        hizb = self._find_hizb(global_ayah)
        manzil = self._find_manzil(global_ayah)
        return {
            "global_ayah_number": global_ayah,
            "juz_number": juz,
            "hizb_number": hizb,
            "manzil_number": manzil
        }

    def _calculate_global_ayah(self, surah: int, ayah_num: int) -> int:
        surah_info = self._load_json("surah_info.json")
        total = 0
        for i in range(1, surah):
            total += surah_info.get(str(i), {}).get("total_ayat", 0)
        total += ayah_num
        return total

    def _find_juz(self, global_ayah: int) -> int:
        for juz, (start, end) in self.juz_boundaries.items():
            if start <= global_ayah <= end:
                return int(juz)
        return 1

    def _find_hizb(self, global_ayah: int) -> int:
        for hizb, (start, end) in self.hizb_boundaries.items():
            if start <= global_ayah <= end:
                return int(hizb)
        return 1

    def _find_manzil(self, global_ayah: int) -> int:
        for manzil, (start, end) in self.manzil_boundaries.items():
            if start <= global_ayah <= end:
                return int(manzil)
        return 1

    async def analyze_text_stats(self, arabic_text: str) -> dict:
        words = arabic_text.split()
        clean_text = self._extract_arabic_letters(arabic_text)
        return {
            "total_characters": len(arabic_text),
            "total_letters": len(clean_text),
            "total_words": len(words),
            "words_list": words
        }

    async def analyze_word_letter_breakdown(self, word: str) -> Dict[str, Any]:
        clean = self._extract_arabic_letters(word)
        return {
            "letter_count": len(clean),
            "letter_frequency": dict(Counter(clean))
        }

    async def analyze_ayah_letter_breakdown(self, ayah_text: str) -> Dict[str, int]:
        clean = self._extract_arabic_letters(ayah_text)
        return dict(Counter(clean))

    async def detect_waqf_marks(self, arabic_text: str) -> List[WaqfMark]:
        waqf_symbols = {
            "م": WaqfType.LAZIM,
            "ط": WaqfType.MURAKH_KHAS,
            "ج": WaqfType.JAAIZ,
            "لا": WaqfType.LA,
            "صلے": WaqfType.SILE,
            "قلے": WaqfType.QILE,
            "ز": WaqfType.ZAJR
        }
        marks = []
        for symbol, waqf_type in waqf_symbols.items():
            pattern = rf'(?:^|\s)({re.escape(symbol)})(?:\s|$)'
            for match in re.finditer(pattern, arabic_text):
                pos = match.start(1)
                marks.append(WaqfMark(
                    symbol=waqf_type,
                    meaning=f"Waqf {symbol}",
                    position_in_ayah=pos
                ))
        return marks

    async def handle_ruku_logic(self, ayah, prev_ruku_number: int, prev_position: int) -> Tuple[int, int]:
        if ayah.ruku_end:
            return prev_ruku_number + 1, 1
        return prev_ruku_number, prev_position + 1

    async def analyze_symbol_frequency(self, text: str) -> Dict[str, int]:
        diacritics = DIACRITICS_PATTERN.findall(text)
        return dict(Counter(diacritics))

# ==================== AYAH SERVICE ====================

class AyahService:
    def __init__(self, ayah_repo: AyahRepository, word_repo: WordRepository,
                 abjad_engine: AbjadEngine, auto_analysis: AutoAnalysisService):
        self.ayah_repo = ayah_repo
        self.word_repo = word_repo
        self.abjad_engine = abjad_engine
        self.auto_analysis = auto_analysis

    async def get_ayah(self, surah: int, ayah: int) -> Optional[Ayah]:
        return await self.ayah_repo.get_by_surah_ayah(surah, ayah)

    async def get_ayah_by_global(self, global_number: int) -> Optional[Ayah]:
        return await self.ayah_repo.get_by_global_number(global_number)

    async def get_ayah_with_words(self, surah: int, ayah: int) -> dict:
        ayah_obj = await self.get_ayah(surah, ayah)
        if not ayah_obj:
            return None
        words = await self.word_repo.get_by_ayah(surah, ayah)
        return {"ayah": ayah_obj, "words": words}

    async def calculate_ayah_abjad(self, ayah: Ayah) -> int:
        words = await self.word_repo.get_by_ayah(ayah.surah_number, ayah.ayah_number)
        return sum(w.abjad_value for w in words)

    async def refresh_ayah_statistics(self, ayah: Ayah) -> Ayah:
        stats = await self.auto_analysis.analyze_text_stats(ayah.arabic_text)
        ayah.word_count = stats["total_words"]
        ayah.letter_count = stats["total_letters"]
        ayah.total_abjad = await self.calculate_ayah_abjad(ayah)
        return await self.ayah_repo.update(f"{ayah.surah_number}_{ayah.ayah_number}", ayah)

    async def enrich_ayah_with_details(self, surah: int, ayah: int) -> Optional[dict]:
        ayah_obj = await self.get_ayah(surah, ayah)
        if not ayah_obj:
            return None
        words = await self.word_repo.get_by_ayah(surah, ayah)
        if not ayah_obj.word_abjad_list:
            ayah_obj.word_abjad_list = [w.abjad_value for w in words]
        if not ayah_obj.letter_counts:
            full_text = " ".join(w.arabic_word for w in words)
            ayah_obj.letter_counts = await self.auto_analysis.analyze_ayah_letter_breakdown(full_text)
        if ayah_obj.unique_words_count == 0:
            unique_arabic = set(w.arabic_word for w in words)
            ayah_obj.unique_words_count = len(unique_arabic)
        return {"ayah": ayah_obj, "words": words}

# ==================== BACKGROUND UPDATER ====================

class BackgroundUpdater:
    def __init__(self, search_engine: 'SearchEngine', abjad_engine: AbjadEngine,
                 occurrence_service: 'WordOccurrenceService', quran_service: 'QuranService'):
        self.search_engine = search_engine
        self.abjad_engine = abjad_engine
        self.occurrence_service = occurrence_service
        self.quran_service = quran_service
        self.running = False
        self._tasks = []

    async def periodic_reindex(self):
        while self.running:
            await asyncio.sleep(settings.BACKGROUND_UPDATE_INTERVAL)
            try:
                logger.info("Running background periodic tasks...")
                await self.search_engine.build_indexes()
                await self.abjad_engine.refresh_cache()
                logger.info("Background tasks completed.")
            except Exception as e:
                logger.error(f"Periodic task error: {e}")

    async def schedule_recalculation(self, surah: int, ayah: Optional[int] = None):
        async def recalc():
            logger.info(f"Recalculating statistics for surah {surah}" + (f", ayah {ayah}" if ayah else ""))
            try:
                await self.quran_service.invalidate_statistics(surah_number=surah)
                if ayah:
                    await self.occurrence_service.rebuild_occurrences_for_ayah(surah, ayah)
                else:
                    await self.occurrence_service.rebuild_for_surah(surah)
                self.search_engine._index_built = False
                logger.info(f"Recalculation completed for surah {surah}")
            except Exception as e:
                logger.error(f"Recalculation failed: {e}")
        asyncio.create_task(recalc())

    async def start(self):
        self.running = True
        self._tasks.append(asyncio.create_task(self.periodic_reindex()))
        logger.info("Background updater started")

    async def stop(self):
        self.running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Background updater stopped")

# ==================== LETTER ANALYTICS SERVICE ====================

class LetterAnalyticsService:
    def __init__(self, ayah_repo: AyahRepository, word_repo: WordRepository, surah_repo: SurahRepository):
        self.ayah_repo = ayah_repo
        self.word_repo = word_repo
        self.surah_repo = surah_repo

    def _extract_arabic_letters(self, text: str) -> str:
        pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
        return ''.join(pattern.findall(text))

    async def get_ayah_letter_frequency(self, surah: int, ayah: int) -> Dict[str, int]:
        ayah_obj = await self.ayah_repo.get_by_surah_ayah(surah, ayah)
        if not ayah_obj:
            return {}
        if ayah_obj.letter_counts:
            return ayah_obj.letter_counts
        clean_text = self._extract_arabic_letters(ayah_obj.arabic_text)
        return dict(Counter(clean_text))

    async def get_surah_letter_frequency(self, surah_number: int) -> Dict[str, int]:
        ayahs = await self.ayah_repo.get_by_surah(surah_number)
        total_counter = Counter()
        for ayah in ayahs:
            freq = await self.get_ayah_letter_frequency(surah_number, ayah.ayah_number)
            total_counter.update(freq)
        return dict(total_counter)

    async def get_quran_letter_frequency(self) -> Dict[str, int]:
        surahs = await self.surah_repo.get_all()
        total_counter = Counter()
        for surah in surahs:
            freq = await self.get_surah_letter_frequency(surah.surah_number)
            total_counter.update(freq)
        return dict(total_counter)

    async def compare_surah_letter_frequencies(self, surah1: int, surah2: int) -> Dict:
        freq1 = await self.get_surah_letter_frequency(surah1)
        freq2 = await self.get_surah_letter_frequency(surah2)
        all_letters = set(freq1.keys()) | set(freq2.keys())
        comparison = {}
        for letter in all_letters:
            comparison[letter] = {
                "surah1_count": freq1.get(letter, 0),
                "surah2_count": freq2.get(letter, 0),
                "difference": freq1.get(letter, 0) - freq2.get(letter, 0)
            }
        return {"surah1": surah1, "surah2": surah2, "comparison": comparison}

    async def get_ayah_letter_stats(self, surah: int, ayah: int) -> Dict:
        freq = await self.get_ayah_letter_frequency(surah, ayah)
        if not freq:
            return {}
        total_letters = sum(freq.values())
        most_common = max(freq.items(), key=lambda x: x[1]) if freq else None
        least_common = min(freq.items(), key=lambda x: x[1]) if freq else None
        unique_letters = len(freq)
        diversity = unique_letters / total_letters if total_letters > 0 else 0
        return {
            "ayah": f"{surah}:{ayah}",
            "total_letters": total_letters,
            "unique_letters": unique_letters,
            "letter_frequency": freq,
            "most_common_letter": most_common,
            "least_common_letter": least_common,
            "diversity_score": round(diversity, 4)
        }

    async def get_surah_letter_stats(self, surah_number: int) -> Dict:
        freq = await self.get_surah_letter_frequency(surah_number)
        if not freq:
            return {}
        total_letters = sum(freq.values())
        most_common = max(freq.items(), key=lambda x: x[1]) if freq else None
        least_common = min(freq.items(), key=lambda x: x[1]) if freq else None
        unique_letters = len(freq)
        diversity = unique_letters / total_letters if total_letters > 0 else 0
        surah_obj = await self.surah_repo.get_by_number(surah_number)
        return {
            "surah_number": surah_number,
            "surah_name": surah_obj.arabic_name if surah_obj else "",
            "total_ayahs": surah_obj.total_ayat if surah_obj else 0,
            "total_letters": total_letters,
            "unique_letters": unique_letters,
            "letter_frequency": freq,
            "most_common_letter": most_common,
            "least_common_letter": least_common,
            "diversity_score": round(diversity, 4)
        }

    async def get_cached_quran_letter_frequency(self) -> Dict[str, int]:
        # For now, recompute each time
        return await self.get_quran_letter_frequency()

# ==================== NOTE SERVICE ====================

class NoteService:
    def __init__(self, note_repo: NoteRepository):
        self.note_repo = note_repo

    async def create_note(self, user_id: str, ayah_global_id: int, note_type, title, content) -> Note:
        note = Note(
            note_id=str(uuid.uuid4()),
            user_id=user_id,
            ayah_global_id=ayah_global_id,
            note_type=note_type,
            title=title,
            content=content,
            status=NoteStatus.PENDING
        )
        return await self.note_repo.add(note)

    async def get_notes_for_ayah(self, ayah_global_id: int, user_role: str = "guest") -> List[Note]:
        if user_role in ["admin", "moderator", "super_admin"]:
            return await self.note_repo.get_by_ayah(ayah_global_id)
        else:
            return await self.note_repo.get_by_ayah(ayah_global_id, status=NoteStatus.VERIFIED)

    async def get_my_notes(self, user_id: str) -> List[Note]:
        return await self.note_repo.get_by_user(user_id)

    async def update_note(self, note_id: str, user_id: str, title: str, content: str) -> Optional[Note]:
        note = await self.note_repo.get(note_id)
        if not note or note.user_id != user_id:
            return None
        note.title = title
        note.content = content
        if note.status != NoteStatus.PENDING:
            note.status = NoteStatus.PENDING
            note.verified_by = None
            note.verified_at = None
        return await self.note_repo.update(note_id, note)

    async def delete_note(self, note_id: str, user_id: str, is_admin: bool = False) -> bool:
        note = await self.note_repo.get(note_id)
        if not note:
            return False
        if note.user_id == user_id or is_admin:
            return await self.note_repo.delete(note_id)
        return False

# ==================== QURAN SERVICE ====================

class QuranService:
    def __init__(self, surah_repo: SurahRepository, ayah_repo: AyahRepository):
        self.surah_repo = surah_repo
        self.ayah_repo = ayah_repo
        self.stats_repo = StatisticsSheetsRepository()
        self.cache = get_cache()

    async def get_surah(self, surah_number: int) -> Optional[Surah]:
        return await self.surah_repo.get_by_number(surah_number)

    async def get_all_surahs(self, skip: int = 0, limit: int = 100) -> List[Surah]:
        return await self.surah_repo.get_all(skip=skip, limit=limit)

    async def get_ayahs_by_surah(self, surah_number: int, skip: int = 0, limit: int = 100) -> List[Ayah]:
        return await self.ayah_repo.get_by_surah(surah_number, skip=skip, limit=limit)

    async def get_surah_statistics(self, surah_number: int) -> dict:
        surah = await self.get_surah(surah_number)
        if not surah:
            return {}
        ayahs = await self.ayah_repo.get_by_surah(surah_number)
        total_abjad = sum(a.total_abjad for a in ayahs)
        total_words = sum(a.word_count for a in ayahs)
        total_letters = sum(a.letter_count for a in ayahs)
        return {
            "surah_number": surah_number,
            "total_ayat": len(ayahs),
            "total_words": total_words,
            "total_letters": total_letters,
            "total_abjad": total_abjad,
            "ruku_count": surah.ruku_count
        }

    async def _get_cached_or_compute(self, stat_id: str, compute_func) -> int:
        cached = await self.cache.get(stat_id)
        if cached is not None:
            return cached
        stored = await self.stats_repo.get(stat_id)
        if stored:
            await self.cache.set(stat_id, stored.abjad_total, ttl_seconds=3600)
            return stored.abjad_total
        value = await compute_func()
        await self.stats_repo.set(stat_id, value)
        await self.cache.set(stat_id, value, ttl_seconds=3600)
        return value

    async def get_surah_abjad(self, surah_number: int) -> int:
        async def compute():
            ayahs = await self.ayah_repo.get_by_surah(surah_number)
            return sum(a.total_abjad for a in ayahs)
        return await self._get_cached_or_compute(f"surah:{surah_number}", compute)

    async def get_ruku_abjad(self, surah_number: int, ruku_number: int) -> int:
        async def compute():
            ayahs = await self.ayah_repo.get_by_surah(surah_number)
            return sum(a.total_abjad for a in ayahs if a.ruku_number == ruku_number)
        return await self._get_cached_or_compute(f"ruku:{surah_number}:{ruku_number}", compute)

    async def get_juz_abjad(self, juz_number: int) -> int:
        async def compute():
            ayahs = await self.ayah_repo.get_all()
            return sum(a.total_abjad for a in ayahs if a.juz_number == juz_number)
        return await self._get_cached_or_compute(f"juz:{juz_number}", compute)

    async def get_manzil_abjad(self, manzil_number: int) -> int:
        async def compute():
            ayahs = await self.ayah_repo.get_all()
            return sum(a.total_abjad for a in ayahs if a.manzil_number == manzil_number)
        return await self._get_cached_or_compute(f"manzil:{manzil_number}", compute)

    async def get_hizb_abjad(self, hizb_number: int) -> int:
        async def compute():
            ayahs = await self.ayah_repo.get_all()
            return sum(a.total_abjad for a in ayahs if a.hizb_number == hizb_number)
        return await self._get_cached_or_compute(f"hizb:{hizb_number}", compute)

    async def get_total_quran_abjad(self) -> int:
        async def compute():
            ayahs = await self.ayah_repo.get_all()
            return sum(a.total_abjad for a in ayahs)
        return await self._get_cached_or_compute("quran:total", compute)

    async def invalidate_statistics(self, surah_number: Optional[int] = None, ruku_number: Optional[int] = None,
                                    juz_number: Optional[int] = None, manzil_number: Optional[int] = None,
                                    hizb_number: Optional[int] = None):
        keys_to_invalidate = ["quran:total"]
        if surah_number:
            keys_to_invalidate.append(f"surah:{surah_number}")
            surah = await self.get_surah(surah_number)
            if surah:
                for r in range(1, surah.ruku_count + 1):
                    keys_to_invalidate.append(f"ruku:{surah_number}:{r}")
        for key in keys_to_invalidate:
            await self.cache.delete(key)
            await self.stats_repo.db.delete(key, id_field="stat_id")
        await self._reset_all_statistics()

    async def _reset_all_statistics(self):
        all_stats = await self.stats_repo.get_all()
        for stat in all_stats:
            await self.cache.delete(stat.stat_id)
            await self.stats_repo.db.delete(stat.stat_id, id_field="stat_id")

# ==================== SEARCH ENGINE ====================

class SearchEngine:
    def __init__(self, ayah_repo: AyahRepository, word_repo: WordRepository, abjad_engine: AbjadEngine):
        self.ayah_repo = ayah_repo
        self.word_repo = word_repo
        self.abjad_engine = abjad_engine
        self.inverted_index: Dict[str, List[int]] = {}
        self.abjad_index: Dict[int, List[int]] = {}
        self._index_built = False

    async def build_indexes(self):
        ayahs = await self.ayah_repo.get_all(limit=10000)
        self.inverted_index.clear()
        self.abjad_index.clear()
        for ayah in ayahs:
            words = re.findall(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+', ayah.arabic_text)
            for word in words:
                if word not in self.inverted_index:
                    self.inverted_index[word] = []
                self.inverted_index[word].append(ayah.global_ayah_number)
            if ayah.total_abjad not in self.abjad_index:
                self.abjad_index[ayah.total_abjad] = []
            self.abjad_index[ayah.total_abjad].append(ayah.global_ayah_number)
        self._index_built = True

    async def ensure_index(self):
        if not self._index_built:
            await self.build_indexes()

    async def search_by_word(self, word: str) -> List[Dict]:
        await self.ensure_index()
        ayah_numbers = self.inverted_index.get(word, [])
        results = []
        for num in ayah_numbers[:100]:
            ayah = await self.ayah_repo.get_by_global_number(num)
            if ayah:
                results.append(ayah.dict())
        return results

    async def search_by_abjad(self, abjad_value: int) -> List[Dict]:
        await self.ensure_index()
        ayah_numbers = self.abjad_index.get(abjad_value, [])
        results = []
        for num in ayah_numbers[:100]:
            ayah = await self.ayah_repo.get_by_global_number(num)
            if ayah:
                results.append(ayah.dict())
        return results
    
    async def search_words_by_abjad(self, abjad_value: int) -> List[Dict]:
        await self.ensure_index()
        words = await self.word_repo.get_all(filters={"abjad_value": abjad_value}, limit=1000)
        results = []
        for word in words:
            ayah = await self.ayah_repo.get_by_surah_ayah(word.surah_number, word.ayah_number)
            if ayah:
                results.append({
                    "word": word.dict(),
                    "ayah": ayah.dict()
                })
        return results
    
    async def search_by_root(self, root: str) -> List[Dict]:
        words = await self.word_repo.get_by_root(root)
        ayah_ids = list(set(w.global_ayah_number for w in words))
        results = []
        for aid in ayah_ids[:100]:
            ayah = await self.ayah_repo.get_by_global_number(aid)
            if ayah:
                results.append(ayah.dict())
        return results

    async def full_text_search(self, query: str, language: str = "arabic") -> List[Dict]:
        await self.ensure_index()
        ayahs = await self.ayah_repo.get_all(limit=5000)
        results = []
        for ayah in ayahs:
            if language == "arabic" and query in ayah.arabic_text:
                results.append(ayah.dict())
            elif language in ayah.translations and query in ayah.translations[language]:
                results.append(ayah.dict())
        return results[:100]

# ==================== WORD OCCURRENCE SERVICE ====================

class WordOccurrenceService:
    def __init__(self, occurrence_repo: WordOccurrenceSheetsRepository,
                 ayah_repo: AyahRepository, word_repo: WordRepository):
        self.occ_repo = occurrence_repo
        self.ayah_repo = ayah_repo
        self.word_repo = word_repo

    async def rebuild_occurrences_for_ayah(self, surah: int, ayah: int) -> None:
        await self.occ_repo.delete_by_ayah(surah, ayah)
        words = await self.word_repo.get_by_ayah(surah, ayah)
        occurrences = []
        for w in words:
            occ = WordOccurrence(
                occurrence_id=w.word_id,
                word_text=w.arabic_word,
                surah_number=w.surah_number,
                ayah_number=w.ayah_number,
                position_in_ayah=w.position_in_ayah,
                global_ayah_number=w.global_ayah_number
            )
            occurrences.append(occ)
        if occurrences:
            await self.occ_repo.add_occurrences_batch(occurrences)

    async def rebuild_for_surah(self, surah: int) -> None:
        ayahs = await self.ayah_repo.get_by_surah(surah)
        for ayah in ayahs:
            await self.rebuild_occurrences_for_ayah(surah, ayah.ayah_number)

    async def get_occurrence_details(self, word_text: str) -> Dict:
        occurrences = await self.occ_repo.get_occurrences_by_word(word_text)
        if not occurrences:
            return {"word": word_text, "total": 0, "per_surah": {}, "per_ayah": []}
        total = len(occurrences)
        per_surah = {}
        per_ayah = []
        for occ in occurrences:
            per_surah[occ.surah_number] = per_surah.get(occ.surah_number, 0) + 1
            per_ayah.append(f"{occ.surah_number}:{occ.ayah_number}")
        return {
            "word": word_text,
            "total_occurrences": total,
            "occurrences_per_surah": per_surah,
            "occurrence_locations": per_ayah[:20]
        }

# ==================== WORD SERVICE ====================

class WordService:
    def __init__(self, word_repo: WordRepository, grammar_repo, abjad_engine: AbjadEngine,
                 occurrence_service: WordOccurrenceService, background_updater=None):
        self.word_repo = word_repo
        self.grammar_repo = grammar_repo
        self.abjad_engine = abjad_engine
        self.occurrence_service = occurrence_service
        self.background_updater = background_updater

    async def get_word(self, word_id: str) -> Optional[Word]:
        return await self.word_repo.get(word_id)

    async def get_words_by_ayah(self, surah: int, ayah: int) -> List[Word]:
        return await self.word_repo.get_by_ayah(surah, ayah)

    async def get_words_by_root(self, root: str) -> List[Word]:
        return await self.word_repo.get_by_root(root)

    async def add_word(self, word: Word) -> Word:
        result = await self.word_repo.add(word)
        if self.background_updater:
            await self.background_updater.schedule_recalculation(word.surah_number, word.ayah_number)
        return result

    async def batch_add_words(self, words: List[Word]) -> List[Word]:
        added = []
        for w in words:
            added.append(await self.add_word(w))
        return added
    