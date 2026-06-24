# علم القرآن (Ilm Ul Quran)

A comprehensive Quran knowledge platform with word-by-word meanings, Abjad calculations, advanced search, and community contributions.

## Features

- Complete Quran text with multiple translations (Urdu, English, etc.)
- Word-by-word breakdown with root words and grammar
- Abjad (numeric) value system for letters, words, and ayahs
- Auto-position detection: Juz, Hizb, Manzil, Ruku, Global Ayah
- Advanced search: by word, root, Abjad value, full text
- Community notes with verification workflow
- Admin panel for content moderation
- REST API with JWT authentication
- Repository pattern (Google Sheets ready, easy migration to PostgreSQL)

## Tech Stack

- **Backend**: FastAPI (Python 3.12)
- **Data Storage**: Google Sheets (migration-ready to PostgreSQL)
- **Auth**: JWT + bcrypt
- **Caching**: Redis (optional)
- **Frontend**: HTML/CSS/JS (minimal, but API-first)

## Quick Start

### Prerequisites

- Python 3.12+
- Google Cloud project with Sheets API enabled
- Service account JSON key

### Installation

1. Clone repository:
   ```bash
   git clone https://github.com/yourorg/ilm-ul-quran.git
   cd ilm-ul-quran