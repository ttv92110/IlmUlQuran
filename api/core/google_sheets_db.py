# api/core/google_sheets_db.py
import gspread
from google.oauth2.service_account import Credentials
from typing import  Dict
from pathlib import Path
import json
import os
import uuid
from datetime import datetime
import time
import traceback

# Import settings from config
from api.config import settings

class GoogleSheetsDB:
    def __init__(self, sheet_name: str, worksheet_name: str, connect_eagerly=False):
        self.sheet_name = sheet_name
        self.worksheet_name = worksheet_name
        self._client = None
        self._worksheet = None
        self._cache = {}
        self._cache_expiry = 5
        if connect_eagerly:
            self._ensure_connected()
        
    _headers_cache = {} 

    def _ensure_connected(self):
        if self._worksheet is not None:
            return
        attempts = 0
        max_attempts = 3
        while attempts < max_attempts:
            attempts += 1
            try:
                scopes = [
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"
                ]
                creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
                if creds_json:
                    creds_dict = json.loads(creds_json)
                    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                    self._client = gspread.authorize(creds)
                    print("✅ Connected using GOOGLE_SHEETS_CREDENTIALS")
                else:
                    creds_file = Path(__file__).parent.parent.parent / settings.GOOGLE_SHEETS_CREDENTIALS_FILE
                    if not creds_file.exists():
                        print("❌ No credentials found.")
                        return
                    creds = Credentials.from_service_account_file(str(creds_file), scopes=scopes)
                    self._client = gspread.authorize(creds)
                    print(f"✅ Connected using credentials file: {creds_file}")

                spreadsheet = self._client.open(self.sheet_name)
                print(f"📊 Opened spreadsheet: {self.sheet_name}")

                # Try to get worksheet, create if not exists
                try:
                    self._worksheet = spreadsheet.worksheet(self.worksheet_name)
                    print(f"📋 Worksheet '{self.worksheet_name}' found")
                    return
                except gspread.exceptions.WorksheetNotFound:
                    print(f"📋 Worksheet '{self.worksheet_name}' not found – creating...")
                    try:
                        self._worksheet = spreadsheet.add_worksheet(
                            title=self.worksheet_name, rows="1000", cols="20"
                        )
                        headers = self._get_default_headers()
                        if headers:
                            self._worksheet.append_row(headers)
                            print(f"📋 Added headers to '{self.worksheet_name}'")
                        return
                    except gspread.exceptions.APIError as api_err:
                        # If "already exists", fetch it again
                        if 'already exists' in str(api_err):
                            self._worksheet = spreadsheet.worksheet(self.worksheet_name)
                            print(f"📋 Worksheet '{self.worksheet_name}' already exists, using it.")
                            return
                        else:
                            raise
            except Exception as e:
                err_str = str(e)
                if "429" in err_str:
                    wait = 2 ** attempts
                    print(f"⏳ Quota hit – retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"❌ Connection error: {traceback.format_exc()}")
                    self._worksheet = None
                    return
                
    def _get_default_headers(self):
        headers_map = {
            "users": ["user_id", "name", "email", "role", "hashed_password", "created_at", "last_login", "is_active"],
            "surahs": ["surah_number", "arabic_name", "urdu_name", "english_name", "meaning", "makki_madani", "total_ayat", "total_words", "total_letters", "total_abjad", "ruku_count", "juz_info", "manzil_info", "hizb_info"],
            "ayahs": ["surah_number", "ayah_number", "global_ayah_number", "arabic_text", "arabic_without_harakat", "transliteration", "translations", "waqf_marks", "sajdah_flag", "ruku_end", "juz_number", "hizb_number", "manzil_number", "ruku_number", "position_in_ruku", "word_count", "letter_count", "total_abjad"],
            "words": ["word_id", "surah_number", "ayah_number", "global_ayah_number", "position", "arabic_word", "root_word", "root_meaning", "urdu_meaning", "english_meaning", "transliteration", "abjad_value", "translations"],
            "abjad_mappings": ["letter", "abjad_value", "description", "modified_by", "modified_at"],
            "notes": ["note_id", "user_id", "ayah_global_id", "note_type", "title", "content", "status", "created_at", "verified_by", "verified_at", "rejection_reason"],
            "audit_logs": ["log_id", "user_id", "action", "entity_type", "entity_id", "old_value", "new_value", "timestamp"]
        }
        return headers_map.get(self.worksheet_name)

    def read_all(self, force_refresh=False):
        self._ensure_connected()
        if not self._worksheet:
            return []
        cache_key = f"{self.sheet_name}:{self.worksheet_name}:all"
        now = time.time()
        if not force_refresh and cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if now - timestamp < self._cache_expiry:
                return data
        try:
            records = self._worksheet.get_all_records()
            data = [dict(record) for record in records]
            self._cache[cache_key] = (data, now)
            return data
        except Exception as e:
            print(f"Error reading: {e}")
            if cache_key in self._cache:
                return self._cache[cache_key][0]
            return []

    def find_by_id(self, id: str, id_field="id"):
        for rec in self.read_all():
            if str(rec.get(id_field)) == str(id):
                return rec
        return None

    def find_by_field(self, field: str, value: str):
        return [r for r in self.read_all() if str(r.get(field)) == str(value)]
    
    def insert(self, record: Dict):
        self._ensure_connected()
        if not self._worksheet:
            return record

        if 'id' not in record and 'note_id' not in record and 'user_id' not in record:
            record['id'] = str(uuid.uuid4())
        if 'created_at' not in record:
            record['created_at'] = datetime.utcnow().isoformat()

        cache_key = f"{self.sheet_name}_{self.worksheet_name}"
        if cache_key not in self._headers_cache:
            headers = self._worksheet.row_values(1)
            if not headers:
                headers = list(record.keys())
                self._worksheet.append_row(headers)
            self._headers_cache[cache_key] = headers
        headers = self._headers_cache[cache_key]

        # Convert None to empty string
        row = [str(record.get(h, "")) if record.get(h) is not None else "" for h in headers]

        self._worksheet.append_row(row)
        self._cache.clear()
        return record

    def update(self, id: str, updates: Dict, id_field="id"):
        self._ensure_connected()
        if not self._worksheet:
            return None
        headers = self._worksheet.row_values(1)
        records = self.read_all()
        for idx, rec in enumerate(records, start=2):
            if str(rec.get(id_field)) == str(id):
                rec.update(updates)
                rec['updated_at'] = datetime.utcnow().isoformat()
                for col_idx, h in enumerate(headers, start=1):
                    value = rec.get(h)
                    # Convert None to empty string
                    cell_value = str(value) if value is not None else ""
                    self._worksheet.update_cell(idx, col_idx, cell_value)
                self._cache.clear()
                return rec
        return None

    def delete(self, id: str, id_field="id"):
        self._ensure_connected()
        if not self._worksheet:
            return False
        records = self.read_all()
        for idx, rec in enumerate(records, start=2):
            if str(rec.get(id_field)) == str(id):
                self._worksheet.delete_rows(idx)
                self._cache.clear()
                return True
        return False