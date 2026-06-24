# api/routers/all_routers.py
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Optional
from datetime import datetime

# Import consolidated dependencies
from api.dependencies.service_deps import (
    get_quran_service, get_ayah_service, get_word_service, get_background_updater,
    get_search_engine, get_word_occurrence_service, get_letter_analytics_service,
    get_auth_service, get_note_service
)
from api.services.all_services import QuranService, AyahService,  WordService, BackgroundUpdater, SearchEngine ,WordOccurrenceService, LetterAnalyticsService , AuthService, NoteService, AbjadEngine

# Import schemas from consolidated schemas
from api.schemas.schemas_models import (
    PaginatedResponse, PaginationParams, SurahResponse, AyahResponse,
    AyahUploadRequest, NoteVerifyRequest, NoteResponse, TranslationUpdate,
    LoginRequest, Token, AbjadMappingResponse, NoteCreate, NoteUpdate
)

# Import domain models
from api.domain.models import UserRole, NoteStatus, User, RegisterRequestExtended, VerifyEmailRequest, ResendPinRequest

# Import security
from api.core.common import get_current_user, get_current_user_optional, require_role

# Import repositories (for simple endpoints)
from api.repositories.sheets.sheets_repositories import AyahSheetsRepository, NoteSheetsRepository, AbjadSheetsRepository, SurahSheetsRepository, TranslationRepository

# Create main router
router = APIRouter()

# ==================== ABJAD ROUTES ====================
abjad_router = APIRouter(prefix="/abjad", tags=["Abjad"])

abjad_repo = AbjadSheetsRepository()
abjad_engine = AbjadEngine(abjad_repo)

@abjad_router.get("/letter/{letter}")
async def get_letter_value(letter: str):
    value = await abjad_engine.get_letter_value(letter)
    return {"letter": letter, "abjad_value": value}

@abjad_router.get("/word/{word}")
async def calculate_word_abjad(word: str):
    value = await abjad_engine.calculate_word_abjad(word)
    return {"word": word, "abjad_value": value}

@abjad_router.get("/mappings", response_model=list[AbjadMappingResponse])
async def get_mappings():
    mappings = await abjad_repo.get_all()
    return [AbjadMappingResponse(**m.dict()) for m in mappings]

# ==================== ADMIN ROUTES ====================
admin_router = APIRouter(prefix="/admin", tags=["Admin"])

ayah_repo = AyahSheetsRepository()
note_repo = NoteSheetsRepository()

@admin_router.get("/notes/pending")
async def get_pending_notes(moderator: User = Depends(require_role(UserRole.MODERATOR))):
    notes = await note_repo.get_pending_notes()
    return [NoteResponse(**n.dict()) for n in notes]

@admin_router.post("/ayah/upload")
async def upload_ayah(data: AyahUploadRequest, admin: User = Depends(require_role(UserRole.ADMIN))):
    ayah_dict = {
        "surah_number": data.surah,
        "ayah_number": data.ayah_number,
        "global_ayah_number": 0,
        "arabic_text": data.arabic_text,
        "arabic_without_harakat": "",
        "transliteration": "",
        "translations": "{}",
        "waqf_marks": "[]",
        "sajdah_flag": data.sajdah,
        "ruku_end": data.rukuEnd,
        "juz_number": 0,
        "hizb_number": 0,
        "manzil_number": 0,
        "ruku_number": 0,
        "position_in_ruku": 1,
        "word_count": 0,
        "letter_count": 0,
        "total_abjad": 0,
        "created_at": datetime.utcnow().isoformat()
    }
    ayah_repo.db.insert(ayah_dict)
    return {"message": "Ayah uploaded"}

@admin_router.post("/notes/verify/{note_id}")
async def verify_note(note_id: str, data: NoteVerifyRequest, moderator: User = Depends(require_role(UserRole.MODERATOR))):
    note = await note_repo.get(note_id)
    if not note:
        raise HTTPException(404, "Note not found")
    note.status = NoteStatus(data.status)
    note.verified_by = moderator.user_id
    note.verified_at = datetime.utcnow()
    note.rejection_reason = data.rejection_reason
    await note_repo.update(note_id, note)
    return {"message": f"Note {data.status}"}

@admin_router.post("/admin/rebuild-abjad-stats")
async def rebuild_all_abjad_stats(
    background_tasks: BackgroundTasks,
    quran_service: QuranService = Depends(get_quran_service),
    _=Depends(require_role(UserRole.SUPER_ADMIN))
):
    async def rebuild():
        await quran_service._reset_all_statistics()
        await quran_service.get_total_quran_abjad()
    background_tasks.add_task(rebuild)
    return {"message": "Abjad statistics rebuild started in background"}

@admin_router.post("/ayah/{surah}/{ayah}/translation")
async def add_ayah_translation(
    surah: int, ayah: int, data: TranslationUpdate,
    ayah_service: AyahService = Depends(get_ayah_service),
    _=Depends(require_role(UserRole.ADMIN))
):
    ayah_obj = await ayah_service.get_ayah(surah, ayah)
    if not ayah_obj:
        raise HTTPException(404, "Ayah not found")
    ayah_obj.translations[data.language_code] = data.translation_text
    await ayah_service.ayah_repo.update(f"{surah}_{ayah}", ayah_obj)
    return {"message": "Translation added", "language": data.language_code}

@admin_router.post("/word/{word_id}/translation")
async def add_word_translation(
    word_id: str, data: TranslationUpdate,
    word_service: WordService = Depends(get_word_service),
    _=Depends(require_role(UserRole.ADMIN))
):
    word = await word_service.get_word(word_id)
    if not word:
        raise HTTPException(404, "Word not found")
    word.translations[data.language_code] = data.translation_text
    await word_service.word_repo.update(word_id, word)
    return {"message": "Translation added"}

@admin_router.post("/admin/rebuild-all")
async def manual_full_rebuild(
    background_tasks: BackgroundTasks,
    background_updater: BackgroundUpdater = Depends(get_background_updater),
    _=Depends(require_role(UserRole.SUPER_ADMIN))
):
    async def rebuild():
        await background_updater.quran_service._reset_all_statistics()
        await background_updater.search_engine.build_indexes()
        await background_updater.abjad_engine.refresh_cache()
        all_ayahs = await background_updater.occurrence_service.ayah_repo.get_all()
        for ayah in all_ayahs:
            await background_updater.occurrence_service.rebuild_occurrences_for_ayah(ayah.surah_number, ayah.ayah_number)
    background_tasks.add_task(rebuild)
    return {"message": "Full rebuild started in background"}

# ==================== AUTH ROUTES ====================
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.post("/register", response_model=dict)
async def register(data: RegisterRequestExtended, auth_service: AuthService = Depends(get_auth_service)):
    try:
        result = await auth_service.register_user(
            data.name, data.email, data.password,
            data.mobile, data.cnic, data.profile_pic, data.cnic_pic
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@auth_router.post("/verify-email")
async def verify_email(data: VerifyEmailRequest, auth_service: AuthService = Depends(get_auth_service)):
    try:
        await auth_service.verify_email(data.email, data.pin)
        return {"message": "Email verified successfully. You can now login."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@auth_router.post("/resend-pin")
async def resend_pin(data: ResendPinRequest, auth_service: AuthService = Depends(get_auth_service)):
    try:
        await auth_service.resend_pin(data.email)
        return {"message": "New PIN sent to your email."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@auth_router.post("/login", response_model=Token)
async def login(data: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    try:
        user = await auth_service.authenticate_user(data.email, data.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        access_token = auth_service.create_access_token({"sub": user["user_id"], "role": user["role"]})
        refresh_token = auth_service.create_refresh_token({"sub": user["user_id"]})
        return Token(access_token=access_token, refresh_token=refresh_token, token_type="bearer")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@auth_router.get("/me")
async def get_me(current_user = Depends(get_current_user)):
    return {"user_id": current_user.user_id, "name": current_user.name, "email": current_user.email}

# ==================== NOTES ROUTES ====================
notes_router = APIRouter(prefix="/notes", tags=["Notes"])

@notes_router.post("/", response_model=NoteResponse)
async def create_note(
    data: NoteCreate,
    current_user: User = Depends(get_current_user),
    note_service: NoteService = Depends(get_note_service)
):
    note = await note_service.create_note(
        user_id=current_user.user_id,
        ayah_global_id=data.ayah_global_id,
        note_type=data.note_type,
        title=data.title,
        content=data.content
    )
    return NoteResponse(**note.dict())

@notes_router.get("/ayah/{ayah_global_id}")
async def get_notes_for_ayah(
    ayah_global_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    note_service: NoteService = Depends(get_note_service)
):
    user_role = current_user.role if current_user else "guest"
    notes = await note_service.get_notes_for_ayah(ayah_global_id, user_role)
    return [NoteResponse(**n.dict()) for n in notes]

@notes_router.get("/my")
async def get_my_notes(
    current_user: User = Depends(get_current_user),
    note_service: NoteService = Depends(get_note_service)
):
    notes = await note_service.get_my_notes(current_user.user_id)
    return [NoteResponse(**n.dict()) for n in notes]

@notes_router.put("/{note_id}")
async def update_note(
    note_id: str,
    data: NoteUpdate,
    current_user: User = Depends(get_current_user),
    note_service: NoteService = Depends(get_note_service)
):
    updated = await note_service.update_note(note_id, current_user.user_id, data.title, data.content)
    if not updated:
        raise HTTPException(404, "Note not found or not yours")
    return NoteResponse(**updated.dict())

@notes_router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    note_service: NoteService = Depends(get_note_service)
):
    is_admin = current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]
    deleted = await note_service.delete_note(note_id, current_user.user_id, is_admin)
    if not deleted:
        raise HTTPException(404, "Note not found or not authorized")
    return {"message": "Note deleted"}

# ==================== QURAN ROUTES ====================
quran_router = APIRouter(prefix="/quran", tags=["Quran"])

surah_repo = SurahSheetsRepository()
ayah_repo_local = AyahSheetsRepository()

@quran_router.get("/surahs", response_model=PaginatedResponse[SurahResponse])
async def get_surahs(page: int = 1, page_size: int = 20):
    skip = (page - 1) * page_size
    surahs = await surah_repo.get_all(skip=skip, limit=page_size)
    total = len(await surah_repo.get_all())
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=[SurahResponse(**s.dict()) for s in surahs],
        total=total, page=page, page_size=page_size, total_pages=total_pages
    )

@quran_router.get("/surah/{surah_number}", response_model=SurahResponse)
async def get_surah(surah_number: int):
    surah = await surah_repo.get_by_number(surah_number)
    if not surah:
        raise HTTPException(404, "Surah not found")
    return SurahResponse(**surah.dict())

@quran_router.get("/surah/{surah_number}/ayahs", response_model=PaginatedResponse[AyahResponse])
async def get_surah_ayahs(
    surah_number: int,
    lang: Optional[str] = Query(None, description="Language code"),
    pagination: PaginationParams = Depends(),
    service: AyahService = Depends(get_ayah_service),
):
    ayahs = await service.ayah_repo.get_by_surah(surah_number, skip=pagination.skip, limit=pagination.limit)
    if lang:
        for ayah in ayahs:
            if lang in ayah.translations:
                ayah.translations = {lang: ayah.translations[lang]}
            else:
                ayah.translations = {}
    total = len(await service.ayah_repo.get_by_surah(surah_number))
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    return PaginatedResponse(
        items=[AyahResponse(**ayah.dict()) for ayah in ayahs],
        total=total, page=pagination.page, page_size=pagination.page_size, total_pages=total_pages
    )

# Abjad statistics endpoints
@quran_router.get("/statistics/abjad/surah/{surah_number}")
async def get_surah_abjad(surah_number: int, service: QuranService = Depends(get_quran_service)):
    total = await service.get_surah_abjad(surah_number)
    return {"surah_number": surah_number, "total_abjad": total}

@quran_router.get("/statistics/abjad/ruku/{surah_number}/{ruku_number}")
async def get_ruku_abjad(surah_number: int, ruku_number: int, service: QuranService = Depends(get_quran_service)):
    total = await service.get_ruku_abjad(surah_number, ruku_number)
    return {"surah_number": surah_number, "ruku_number": ruku_number, "total_abjad": total}

@quran_router.get("/statistics/abjad/juz/{juz_number}")
async def get_juz_abjad(juz_number: int, service: QuranService = Depends(get_quran_service)):
    total = await service.get_juz_abjad(juz_number)
    return {"juz_number": juz_number, "total_abjad": total}

@quran_router.get("/statistics/abjad/manzil/{manzil_number}")
async def get_manzil_abjad(manzil_number: int, service: QuranService = Depends(get_quran_service)):
    total = await service.get_manzil_abjad(manzil_number)
    return {"manzil_number": manzil_number, "total_abjad": total}

@quran_router.get("/statistics/abjad/hizb/{hizb_number}")
async def get_hizb_abjad(hizb_number: int, service: QuranService = Depends(get_quran_service)):
    total = await service.get_hizb_abjad(hizb_number)
    return {"hizb_number": hizb_number, "total_abjad": total}

@quran_router.get("/statistics/abjad/quran/total")
async def get_total_quran_abjad(service: QuranService = Depends(get_quran_service)):
    total = await service.get_total_quran_abjad()
    return {"total_abjad": total}

@quran_router.get("/translations/languages")
async def get_supported_languages():
    repo = TranslationRepository()
    return await repo.get_supported_languages()

@quran_router.get("/ayah/enriched/{surah}/{ayah_number}")
async def get_enriched_ayah(
    surah: int, ayah_number: int,
    lang: str = Query("ur", description="Translation language"),
    ayah_service: AyahService = Depends(get_ayah_service),
    word_service: WordService = Depends(get_word_service),
    occurrence_service: WordOccurrenceService = Depends(get_word_occurrence_service),
    quran_service: QuranService = Depends(get_quran_service),
):
    ayah = await ayah_service.get_ayah(surah, ayah_number)
    if not ayah:
        raise HTTPException(404, "Ayah not found")
    symbol_freq = await ayah_service.auto_analysis.analyze_symbol_frequency(ayah.arabic_text)
    symbol_count = sum(symbol_freq.values())
    
    words = await word_service.get_words_by_ayah(surah, ayah_number)
    words_enriched = []
    for w in words:
        occ_in_surah = await occurrence_service.occ_repo.get_occurrence_count_in_surah(w.arabic_word, surah)
        occ_total = await occurrence_service.occ_repo.get_total_occurrence_count(w.arabic_word)
        words_enriched.append({
            "position": w.position_in_ayah,
            "arabic": w.arabic_word,
            "transliteration": w.transliteration or "",
            "translation": w.translations.get(lang, w.translations.get("ur", "")),
            "urdu_meaning": w.translations.get("ur", ""),      # FIXED
            "english_meaning": w.translations.get("en", ""),   # FIXED
            "abjad": w.abjad_value,
            "letter_count": w.letter_count,
            "occurrence_in_surah": occ_in_surah,
            "occurrence_total": occ_total
        })
    
    surah_info = await quran_service.get_surah(surah)
    if not surah_info:
        raise HTTPException(404, "Surah not found")
    
    prev_surah, prev_ayah = surah, ayah_number - 1
    if prev_ayah < 1:
        prev_surah = surah - 1
        if prev_surah >= 1:
            prev_surah_info = await quran_service.get_surah(prev_surah)
            prev_ayah = prev_surah_info.total_ayat if prev_surah_info else 1
        else:
            prev_surah, prev_ayah = None, None
    
    next_surah, next_ayah = surah, ayah_number + 1
    if next_ayah > surah_info.total_ayat:
        next_surah = surah + 1
        next_ayah = 1
        if next_surah > 114:
            next_surah, next_ayah = None, None
    
    word_abjad_list = [w.abjad_value for w in words]
    
    return {
        "ayah": {
            "surah_number": ayah.surah_number,
            "ayah_number": ayah.ayah_number,
            "global_ayah_number": ayah.global_ayah_number,
            "arabic_text": ayah.arabic_text,
            "translation": ayah.translations.get(lang, ayah.translations.get("ur", "")),
            "juz": ayah.juz_number,
            "hizb": ayah.hizb_number,
            "manzil": ayah.manzil_number,
            "ruku": ayah.ruku_number,
            "position_in_ruku": ayah.position_in_ruku,
            "sajdah": ayah.sajdah_flag,
            "ruku_end": ayah.ruku_end,
            "total_abjad": ayah.total_abjad,
            "total_letters": ayah.letter_count,
            "total_words": ayah.word_count,
            "unique_words_count": ayah.unique_words_count,
            "letter_frequency": ayah.letter_counts,
            "word_abjad_list": word_abjad_list,
            "symbol_count": symbol_count,
            "symbol_frequency": symbol_freq,
            "surah_meaning": surah_info.meaning,
        },
        "words": words_enriched,
        "navigation": {
            "prev": {"surah": prev_surah, "ayah": prev_ayah} if prev_surah else None,
            "next": {"surah": next_surah, "ayah": next_ayah} if next_surah else None,
            "surah_name": surah_info.arabic_name,
            "surah_total_ayahs": surah_info.total_ayat
        }
    }

# Analytics endpoints
@quran_router.get("/analytics/ayah/{surah}/{ayah}/letters")
async def get_ayah_letter_frequency(
    surah: int, ayah: int,
    service: LetterAnalyticsService = Depends(get_letter_analytics_service)
):
    result = await service.get_ayah_letter_stats(surah, ayah)
    if not result:
        raise HTTPException(404, "Ayah not found")
    return result

@quran_router.get("/analytics/surah/{surah_number}/letters")
async def get_surah_letter_frequency(
    surah_number: int,
    service: LetterAnalyticsService = Depends(get_letter_analytics_service)
):
    result = await service.get_surah_letter_stats(surah_number)
    if not result:
        raise HTTPException(404, "Surah not found")
    return result

@quran_router.get("/analytics/quran/letters")
async def get_quran_letter_frequency(
    service: LetterAnalyticsService = Depends(get_letter_analytics_service)
):
    freq = await service.get_quran_letter_frequency()
    return {"total_letters": sum(freq.values()), "letter_frequency": freq}

@quran_router.get("/analytics/compare/surah/{surah1}/{surah2}")
async def compare_surah_letters(
    surah1: int, surah2: int,
    service: LetterAnalyticsService = Depends(get_letter_analytics_service)
):
    return await service.compare_surah_letter_frequencies(surah1, surah2)

# ==================== SEARCH ROUTES ====================
search_router = APIRouter(prefix="/search", tags=["Search"])

@search_router.get("/word")
async def search_by_word(
    q: str = Query(..., min_length=1),
    engine: SearchEngine = Depends(get_search_engine)
):
    results = await engine.search_by_word(q)
    return results

@search_router.get("/abjad")
async def search_by_abjad(
    value: int = Query(..., ge=1, le=1000000),
    engine: SearchEngine = Depends(get_search_engine)
):
    results = await engine.search_by_abjad(value)
    return results

@search_router.get("/root")
async def search_by_root(
    root: str = Query(..., min_length=2),
    engine: SearchEngine = Depends(get_search_engine)
):
    results = await engine.search_by_root(root)
    return results

@search_router.get("/fulltext")
async def full_text_search(
    q: str = Query(..., min_length=1),
    language: str = Query("arabic", regex="^(arabic|ur|en|hi|tr|id|fa)$"),
    engine: SearchEngine = Depends(get_search_engine)
):
    results = await engine.full_text_search(q, language)
    return results

@search_router.get("/word/{word_text}/occurrences")
async def get_word_occurrences(
    word_text: str,
    occurrence_service: WordOccurrenceService = Depends(get_word_occurrence_service)
):
    return await occurrence_service.get_occurrence_details(word_text)

@search_router.get("/word/{word_text}/count")
async def get_word_count(
    word_text: str,
    scope: str = "quran",
    surah: Optional[int] = None,
    ayah: Optional[int] = None,
    occurrence_service: WordOccurrenceService = Depends(get_word_occurrence_service)
):
    if scope == "quran":
        count = await occurrence_service.occ_repo.get_total_occurrence_count(word_text)
        return {"word": word_text, "scope": "quran", "count": count}
    elif scope == "surah":
        if not surah:
            raise HTTPException(400, "surah required")
        count = await occurrence_service.occ_repo.get_occurrence_count_in_surah(word_text, surah)
        return {"word": word_text, "surah": surah, "count": count}
    elif scope == "ayah":
        if not surah or not ayah:
            raise HTTPException(400, "surah and ayah required")
        count = await occurrence_service.occ_repo.get_occurrence_count_in_ayah(word_text, surah, ayah)
        return {"word": word_text, "surah": surah, "ayah": ayah, "count": count}
    else:
        raise HTTPException(400, "Invalid scope")

# ==================== Include all sub-routers ====================
router.include_router(abjad_router)
router.include_router(admin_router)
router.include_router(auth_router)
router.include_router(notes_router)
router.include_router(quran_router)
router.include_router(search_router)