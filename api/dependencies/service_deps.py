# api/dependencies/service_deps.py
from fastapi import Depends

# ---------- REPOSITORIES (imports) ----------
from api.repositories.base_repository import GrammarRepository
from api.repositories.sheets.sheets_repositories import SurahSheetsRepository, AyahSheetsRepository, WordSheetsRepository, AbjadSheetsRepository, NoteSheetsRepository, UserSheetsRepository 

# from api.main import background_updater
# ---------- SERVICES ----------
 
from api.services.all_services import QuranService, AyahService, AbjadEngine, SearchEngine, NoteService, AutoAnalysisService, AuthService,  LetterAnalyticsService


# ========== 1. REPOSITORY GETTERS (no dependencies) ==========
async def get_surah_repo():
    return SurahSheetsRepository()

async def get_ayah_repo():
    return AyahSheetsRepository()

async def get_word_repo():
    return WordSheetsRepository()

async def get_abjad_mapping_repo():
    return AbjadSheetsRepository()

async def get_note_repo():
    return NoteSheetsRepository()

async def get_user_repo():
    return UserSheetsRepository()

async def get_grammar_repo():
    # placeholder – implement later
    return GrammarRepository()

# ========== 2. SIMPLE SERVICES (only repositories) ==========
async def get_abjad_engine(
    mapping_repo=Depends(get_abjad_mapping_repo)
):
    return AbjadEngine(mapping_repo)

async def get_auto_analysis():
    return AutoAnalysisService()

async def get_note_service(
    note_repo=Depends(get_note_repo)
):
    return NoteService(note_repo)

async def get_auth_service(
    user_repo=Depends(get_user_repo)
):
    return AuthService(user_repo)

async def get_letter_analytics_service(
    ayah_repo=Depends(get_ayah_repo),
    word_repo=Depends(get_word_repo),
    surah_repo=Depends(get_surah_repo)
):
    return LetterAnalyticsService(ayah_repo, word_repo, surah_repo)

# ========== 3. COMPLEX SERVICES (depend on other services) ==========
async def get_quran_service(
    surah_repo=Depends(get_surah_repo),
    ayah_repo=Depends(get_ayah_repo)
):
    return QuranService(surah_repo, ayah_repo)

async def get_word_occurrence_repo():
    from api.repositories.sheets.sheets_repositories import WordOccurrenceSheetsRepository
    return WordOccurrenceSheetsRepository()

async def get_word_occurrence_service(
    occ_repo=Depends(get_word_occurrence_repo),
    ayah_repo=Depends(get_ayah_repo),
    word_repo=Depends(get_word_repo)
):
    from api.services.all_services import WordOccurrenceService
    return WordOccurrenceService(occ_repo, ayah_repo, word_repo)


async def get_background_updater():
    """Return the global background_updater instance from main app."""
    from api.main import background_updater
    return background_updater
 
async def get_word_service(
    word_repo=Depends(get_word_repo),
    grammar_repo=Depends(get_grammar_repo),
    abjad_engine=Depends(get_abjad_engine),
    occurrence_service=Depends(get_word_occurrence_service),
    background_updater=Depends(get_background_updater)   # add this
):
    from api.services.all_services import WordService
    return WordService(word_repo, grammar_repo, abjad_engine, occurrence_service, background_updater)


async def get_ayah_service(
    ayah_repo=Depends(get_ayah_repo),
    word_repo=Depends(get_word_repo),
    abjad_engine=Depends(get_abjad_engine),
    auto_analysis=Depends(get_auto_analysis)
):
    return AyahService(ayah_repo, word_repo, abjad_engine, auto_analysis)

async def get_search_engine(
    ayah_repo=Depends(get_ayah_repo),
    word_repo=Depends(get_word_repo),
    abjad_engine=Depends(get_abjad_engine)
):
    return SearchEngine(ayah_repo, word_repo, abjad_engine)
  