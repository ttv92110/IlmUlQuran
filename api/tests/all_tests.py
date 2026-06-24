# api/tests/all_tests.py 
import pytest 
import time 
from unittest.mock import AsyncMock, MagicMock
from datetime import timedelta 

from api.domain.models import ( Ayah, User, UserRole, WaqfType, Note, NoteStatus, NoteType
)
from api.services.all_services import (
    AbjadEngine, AutoAnalysisService, SearchEngine, AyahService, NoteService
)
from api.repositories.interfaces_repository import (
    AbjadMappingRepository, AyahRepository, WordRepository
)

from api.repositories.sheets.sheets_repositories import AyahSheetsRepository
from api.core.common import (
    get_password_hash, verify_password, create_access_token, decode_token
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_abjad_repo():
    repo = AsyncMock(spec=AbjadMappingRepository)
    async def get_side_effect(letter):
        mapping = MagicMock()
        values = {'ا': 1, 'ل': 30, 'ه': 5, 'ب': 2, 'س': 60, 'م': 40}
        mapping.abjad_value = values.get(letter, 0)
        return mapping
    repo.get = get_side_effect
    return repo

@pytest.fixture
def abjad_engine(mock_abjad_repo):
    return AbjadEngine(mock_abjad_repo)

@pytest.fixture
def mock_ayah_repo():
    repo = AsyncMock(spec=AyahRepository)
    sample_ayah = Ayah(
        surah_number=1,
        ayah_number=1,
        global_ayah_number=1,
        arabic_text="بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
        translations={"ur": "اللہ کے نام سے"},
        juz_number=1,
        hizb_number=1,
        manzil_number=1,
        ruku_number=1,
        position_in_ruku=1,
        total_abjad=786
    )
    repo.get_by_global_number = AsyncMock(return_value=sample_ayah)
    repo.get_all = AsyncMock(return_value=[sample_ayah])
    return repo

@pytest.fixture
def mock_word_repo():
    repo = AsyncMock(spec=WordRepository)
    return repo

@pytest.fixture
def search_engine(mock_ayah_repo, mock_word_repo, abjad_engine):
    engine = SearchEngine(mock_ayah_repo, mock_word_repo, abjad_engine)
    engine._index_built = True  # skip building indexes in tests
    return engine

@pytest.fixture
def auto_analysis():
    return AutoAnalysisService()

@pytest.fixture
def sample_user():
    return User(
        user_id="test_user_123",
        name="Test User",
        email="test@example.com",
        role=UserRole.USER,
        hashed_password="hashed",
        is_active=True,
        mobile="1234567890",
        cnic="1234567890123"
    )

@pytest.fixture
def admin_user():
    return User(
        user_id="admin_123",
        name="Admin",
        email="admin@example.com",
        role=UserRole.ADMIN,
        hashed_password="hashed",
        is_active=True,
        mobile="0987654321",
        cnic="0987654321098"
    )

@pytest.fixture
def access_token(sample_user):
    return create_access_token({"sub": sample_user.user_id, "role": sample_user.role.value})

# ==================== ABJAD ENGINE TESTS ====================

@pytest.mark.asyncio
async def test_calculate_word_abjad(abjad_engine: AbjadEngine):
    # Test "Allah" word: ا ل ل ه -> 1+30+30+5 = 66
    result = await abjad_engine.calculate_word_abjad("الله")
    assert result == 66

@pytest.mark.asyncio
async def test_calculate_word_abjad_with_diacritics(abjad_engine: AbjadEngine):
    # Diacritics should be ignored
    result = await abjad_engine.calculate_word_abjad("بِسْمِ")
    # ب = 2, س = 60, م = 40, total = 102
    assert result == 102

@pytest.mark.asyncio
async def test_calculate_ayah_abjad(abjad_engine: AbjadEngine):
    words = ["بِسْمِ", "الله"]
    total = await abjad_engine.calculate_ayah_abjad(words)
    assert total == 102 + 66  # 168

@pytest.mark.asyncio
async def test_get_letter_value(abjad_engine: AbjadEngine):
    value = await abjad_engine.get_letter_value("ا")
    assert value == 1

@pytest.mark.asyncio
async def test_get_letter_value_not_found(abjad_engine: AbjadEngine):
    value = await abjad_engine.get_letter_value("x")  # non-Arabic
    assert value == 0

# ==================== AUTO ANALYSIS TESTS ====================

@pytest.mark.asyncio
async def test_auto_detect_position(auto_analysis: AutoAnalysisService):
    # Ayat-ul-Kursi: Surah 2, Ayah 255
    result = await auto_analysis.auto_detect_position(2, 255)
    assert result["global_ayah_number"] == 255  # assuming global starts at 1
    assert result["juz_number"] == 3
    assert result["hizb_number"] == 5

@pytest.mark.asyncio
async def test_analyze_text_stats(auto_analysis: AutoAnalysisService):
    text = "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ"
    stats = await auto_analysis.analyze_text_stats(text)
    assert stats["total_words"] == 4
    assert stats["total_letters"] > 0
    assert len(stats["words_list"]) == 4

@pytest.mark.asyncio
async def test_detect_waqf_marks(auto_analysis: AutoAnalysisService):
    text = "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ ۚ لا"
    marks = await auto_analysis.detect_waqf_marks(text)
    # Should detect "لا"
    assert any(m.symbol == WaqfType.LA for m in marks)

@pytest.mark.asyncio
async def test_handle_ruku_logic(auto_analysis: AutoAnalysisService):
    class MockAyah:
        def __init__(self, ruku_end):
            self.ruku_end = ruku_end
    
    ayah_end_true = MockAyah(ruku_end=True)
    ayah_end_false = MockAyah(ruku_end=False)
    
    ruku, pos = await auto_analysis.handle_ruku_logic(ayah_end_true, 5, 3)
    assert ruku == 6
    assert pos == 1
    
    ruku, pos = await auto_analysis.handle_ruku_logic(ayah_end_false, 5, 3)
    assert ruku == 5
    assert pos == 4

# ==================== REPOSITORY TESTS ====================

@pytest.mark.asyncio
async def test_ayah_record_conversion():
    repo = AyahSheetsRepository()
    record = {
        "surah_number": "1",
        "ayah_number": "1",
        "global_ayah_number": "1",
        "arabic_text": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
        "arabic_without_harakat": "بسم الله الرحمن الرحيم",
        "transliteration": "Bismillah",
        "translations": '{"ur": "اللہ کے نام سے"}',
        "waqf_marks": '[]',
        "sajdah_flag": "False",
        "ruku_end": "False",
        "juz_number": "1",
        "hizb_number": "1",
        "manzil_number": "1",
        "ruku_number": "1",
        "position_in_ruku": "1",
        "word_count": "4",
        "letter_count": "19",
        "total_abjad": "786"
    }
    ayah = repo._from_dict(record, Ayah)
    assert ayah.surah_number == 1
    assert ayah.ayah_number == 1
    assert ayah.translations["ur"] == "اللہ کے نام سے"

@pytest.mark.asyncio
async def test_ayah_to_row_conversion():
    repo = AyahSheetsRepository()
    ayah = Ayah(
        surah_number=1,
        ayah_number=1,
        global_ayah_number=1,
        arabic_text="بِسْمِ اللَّهِ",
        arabic_without_harakat="بسم الله",
        transliteration="Bismillah",
        translations={"ur": "اللہ کے نام سے"},
        waqf_marks=[],
        sajdah_flag=False,
        ruku_end=False,
        juz_number=1,
        hizb_number=1,
        manzil_number=1,
        ruku_number=1,
        position_in_ruku=1,
        word_count=2,
        letter_count=8,
        total_abjad=102
    )
    row = repo._to_dict(ayah)
    # Not a full row test, just check dict conversion
    assert row["surah_number"] == 1
    assert row["arabic_text"] == "بِسْمِ اللَّهِ"

# ==================== SEARCH ENGINE TESTS ====================

@pytest.mark.asyncio
async def test_search_by_word(search_engine: SearchEngine, mock_ayah_repo):
    # Pre-populate inverted index
    search_engine.inverted_index["اللَّهُ"] = [1]
    results = await search_engine.search_by_word("اللَّهُ")
    assert len(results) == 1
    assert results[0]["global_ayah_number"] == 1

@pytest.mark.asyncio
async def test_search_by_abjad(search_engine: SearchEngine, mock_ayah_repo):
    search_engine.abjad_index[786] = [1]
    results = await search_engine.search_by_abjad(786)
    assert len(results) == 1

@pytest.mark.asyncio
async def test_search_by_root(search_engine: SearchEngine, mock_word_repo):
    # Mock word_repo.get_by_root returns list of words
    mock_word = MagicMock()
    mock_word.global_ayah_number = 1
    mock_word_repo.get_by_root = AsyncMock(return_value=[mock_word])
    
    results = await search_engine.search_by_root("رحم")
    assert len(results) == 1

@pytest.mark.asyncio
async def test_full_text_search(search_engine: SearchEngine, mock_ayah_repo):
    results = await search_engine.full_text_search("اللَّهُ", language="arabic")
    assert len(results) == 1

# ==================== SECURITY TESTS ====================

def test_password_hashing():
    password = "secret123"
    hashed = get_password_hash(password)
    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)

def test_create_and_decode_token():
    data = {"sub": "user123", "role": "user"}
    token = create_access_token(data)
    decoded = decode_token(token)
    assert decoded["sub"] == "user123"
    assert decoded["role"] == "user"
    assert decoded["type"] == "access"

def test_token_expiration():
    # Test with short expiration (1 second)
    token = create_access_token({"sub": "test"}, expires_delta=timedelta(seconds=1))
    time.sleep(2)
    with pytest.raises(Exception):  # decode_token raises HTTPException
        decode_token(token)

# ==================== SERVICE TESTS ====================

@pytest.mark.asyncio
async def test_get_ayah_with_words(mock_ayah_repo, mock_word_repo, abjad_engine, auto_analysis):
    service = AyahService(mock_ayah_repo, mock_word_repo, abjad_engine, auto_analysis)
    result = await service.get_ayah_with_words(1, 1)
    assert result is not None
    assert "ayah" in result
    assert "words" in result

@pytest.mark.asyncio
async def test_create_note():
    mock_note_repo = AsyncMock()
    mock_note_repo.add = AsyncMock(return_value=Note(
        note_id="test_id",
        user_id="user1",
        ayah_global_id=1,
        note_type=NoteType.TAFSIR,
        content="Test content",
        status=NoteStatus.PENDING
    ))
    service = NoteService(mock_note_repo)
    note = await service.create_note("user1", 1, NoteType.TAFSIR, "Title", "Content")
    assert note.note_id == "test_id"
    assert note.status == NoteStatus.PENDING