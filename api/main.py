# api/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from api.config import settings 
from api.routers import auth_router, quran_router, abjad_router, notes_router, admin_router, search_router

# api/main.py (add near the top after imports)
from api.services.all_services import BackgroundUpdater
from api.services.all_services import SearchEngine
from api.services.all_services import AbjadEngine
from api.services.all_services import WordOccurrenceService
from api.repositories.sheets.sheets_repositories import WordOccurrenceSheetsRepository
from api.dependencies.service_deps import get_ayah_repo, get_word_repo, get_abjad_mapping_repo, get_quran_service


app = FastAPI(title=settings.APP_NAME)
# Global variable
background_updater = None

@app.on_event("startup")
async def startup_event():
    global background_updater
    # Create dependencies
    ayah_repo = await get_ayah_repo()
    word_repo = await get_word_repo()
    abjad_repo = await get_abjad_mapping_repo()
    abjad_engine = AbjadEngine(abjad_repo)
    search_engine = SearchEngine(ayah_repo, word_repo, abjad_engine)
    occurrence_repo = WordOccurrenceSheetsRepository()
    # We need quran_service and occurrence_service
    quran_service = await get_quran_service()  # this already exists
    occurrence_service = WordOccurrenceService(occurrence_repo, ayah_repo, word_repo)
    
    background_updater = BackgroundUpdater(search_engine, abjad_engine, occurrence_service, quran_service)
    await background_updater.start()

@app.on_event("shutdown")
async def shutdown_event():
    global background_updater
    if background_updater:
        await background_updater.stop()
        

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(quran_router, prefix="/api/v1")
app.include_router(abjad_router, prefix="/api/v1")
app.include_router(notes_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")

# Static files
BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# HTML Routes
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/quran")
async def quran_page(request: Request):
    return templates.TemplateResponse("Al_Quran.html", {"request": request})

@app.get("/surah/{surah_number}", response_class=HTMLResponse)
async def surah_page(request: Request, surah_number: int):
    return templates.TemplateResponse("surah_ayat.html", {"request": request, "surah_number": surah_number})

@app.get("/ayah/{surah}/{ayah_number}")
async def ayah_detail_page(request: Request, surah: int, ayah_number: int):
    return templates.TemplateResponse("ayah_detail.html", {"request": request, "surah": surah, "ayah": ayah_number})

@app.get("/abjad")
async def abjad_page(request: Request):
    return templates.TemplateResponse("abjad_calculator.html", {"request": request})

@app.get("/search")
async def search_page(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})

@app.get("/notes")
async def notes_page(request: Request):
    return templates.TemplateResponse("notes.html", {"request": request})

@app.get("/analytics")
async def analytics_page(request: Request):
    return templates.TemplateResponse("letter_analytics.html", {"request": request})

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/admin")
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/health")
async def health():
    return {"status": "ok"}