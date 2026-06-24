# api/repositories/repository_interfaces.py
# Consolidated abstract repository interfaces (extending BaseRepository)

from typing import Optional, List, Dict
from datetime import datetime

from api.domain.models import (
    AbjadMapping, Ayah, Note, Surah, User, Word,
    NoteStatus
)
from api.repositories.base_repository import BaseRepository

# ==================== ABJAD MAPPING REPOSITORY ====================

class AbjadMappingRepository(BaseRepository[AbjadMapping]):
    """Interface for Abjad letter mapping operations."""
    
    async def get_value(self, letter: str) -> Optional[int]:
        """Get abjad value for a specific Arabic letter."""
        mapping = await self.get(letter)
        return mapping.abjad_value if mapping else None
    
    async def get_all_mappings(self) -> Dict[str, int]:
        """Get all letter->value mappings as dictionary."""
        mappings = await self.get_all()
        return {m.letter: m.abjad_value for m in mappings}
    
    async def update_mapping(self, letter: str, new_value: int, modified_by: str) -> Optional[AbjadMapping]:
        """Update abjad value for a letter."""
        mapping = await self.get(letter)
        if mapping:
            mapping.abjad_value = new_value
            mapping.modified_by = modified_by
            return await self.update(letter, mapping)
        return None

# ==================== AYAH REPOSITORY ====================

class AyahRepository(BaseRepository[Ayah]):
    """Interface for Ayah data operations."""
    
    async def get_by_surah_ayah(self, surah: int, ayah: int) -> Optional[Ayah]:
        """Get ayah by surah number and ayah number."""
        return await self.get(f"{surah}_{ayah}")
    
    async def get_by_global_number(self, global_number: int) -> Optional[Ayah]:
        """Get ayah by global ayah number."""
        return await self.get(f"global_{global_number}")
    
    async def get_by_surah(self, surah_number: int, skip: int = 0, limit: int = 100) -> List[Ayah]:
        """Get all ayahs of a specific surah with pagination."""
        return await self.get_all(filters={"surah_number": surah_number}, skip=skip, limit=limit)
    
    async def get_by_juz(self, juz_number: int, skip: int = 0, limit: int = 100) -> List[Ayah]:
        """Get all ayahs in a specific juz."""
        return await self.get_all(filters={"juz_number": juz_number}, skip=skip, limit=limit)
    
    async def get_by_ruku(self, ruku_number: int, skip: int = 0, limit: int = 100) -> List[Ayah]:
        """Get all ayahs in a specific ruku."""
        return await self.get_all(filters={"ruku_number": ruku_number}, skip=skip, limit=limit)

# ==================== NOTE REPOSITORY ====================

class NoteRepository(BaseRepository[Note]):
    """Interface for community notes operations."""
    
    async def get_by_ayah(self, ayah_global_id: int, status: Optional[NoteStatus] = None) -> List[Note]:
        """Get notes for a specific ayah, optionally filtered by status."""
        filters = {"ayah_global_id": ayah_global_id}
        if status:
            filters["status"] = status
        return await self.get_all(filters=filters)
    
    async def get_by_user(self, user_id: str, status: Optional[NoteStatus] = None) -> List[Note]:
        """Get notes by a specific user."""
        filters = {"user_id": user_id}
        if status:
            filters["status"] = status
        return await self.get_all(filters=filters)
    
    async def get_pending_notes(self, skip: int = 0, limit: int = 100) -> List[Note]:
        """Get all pending notes for moderation."""
        return await self.get_all(filters={"status": NoteStatus.PENDING}, skip=skip, limit=limit)
    
    async def verify_note(self, note_id: str, status: NoteStatus, verified_by: str, rejection_reason: Optional[str] = None) -> Optional[Note]:
        """Verify or reject a note."""
        note = await self.get(note_id)
        if note:
            note.status = status
            note.verified_by = verified_by
            note.verified_at = datetime.utcnow()
            note.rejection_reason = rejection_reason
            return await self.update(note_id, note)
        return None

# ==================== SURAH REPOSITORY ====================

class SurahRepository(BaseRepository[Surah]):
    """Interface for Surah data operations."""
    
    async def get_by_number(self, surah_number: int) -> Optional[Surah]:
        """Get surah by its number (1-114)."""
        return await self.get(str(surah_number))
    
    async def get_all_with_pagination(self, skip: int = 0, limit: int = 100) -> List[Surah]:
        """Get all surahs with pagination."""
        return await self.get_all(skip=skip, limit=limit)
    
    async def update_statistics(self, surah_number: int, 
                                total_words: int, total_letters: int, 
                                total_abjad: int) -> Optional[Surah]:
        """Update word/letter/abjad counts for a surah."""
        surah = await self.get_by_number(surah_number)
        if surah:
            surah.total_words = total_words
            surah.total_letters = total_letters
            surah.total_abjad = total_abjad
            return await self.update(str(surah_number), surah)
        return None

# ==================== USER REPOSITORY ====================

class UserRepository(BaseRepository[User]):
    """Interface for User data operations."""
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        users = await self.get_all(filters={"email": email})
        return users[0] if users else None
    
    async def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all active users."""
        return await self.get_all(filters={"is_active": True}, skip=skip, limit=limit)
    
    async def update_last_login(self, user_id: str) -> Optional[User]:
        """Update user's last login timestamp."""
        user = await self.get(user_id)
        if user:
            user.last_login = datetime.utcnow()
            return await self.update(user_id, user)
        return None
    
    async def get_by_mobile(self, mobile: str) -> Optional[User]:
        """Get user by mobile number."""
        users = await self.get_all(filters={"mobile": mobile})
        return users[0] if users else None

    async def get_by_cnic(self, cnic: str) -> Optional[User]:
        """Get user by CNIC number."""
        users = await self.get_all(filters={"cnic": cnic})
        return users[0] if users else None

# ==================== WORD REPOSITORY ====================

class WordRepository(BaseRepository[Word]):
    """Interface for Word data operations."""
    
    async def get_by_ayah(self, surah: int, ayah: int) -> List[Word]:
        """Get all words of a specific ayah."""
        return await self.get_all(filters={"surah_number": surah, "ayah_number": ayah})
    
    async def get_by_root(self, root_word: str) -> List[Word]:
        """Get all words with a specific root."""
        return await self.get_all(filters={"root_word": root_word})
    
    async def update_abjad_for_ayah(self, surah: int, ayah: int, abjad_values: Dict[int, int]) -> None:
        """Update abjad values for words in an ayah (batch update)."""
        words = await self.get_by_ayah(surah, ayah)
        for word in words:
            if word.position_in_ayah in abjad_values:
                word.abjad_value = abjad_values[word.position_in_ayah]
                await self.update(word.word_id, word)