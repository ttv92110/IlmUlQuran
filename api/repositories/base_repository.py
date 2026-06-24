# api/repositories/base_repository.py 
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Dict, Any
from pydantic import BaseModel
from api.domain.models import GrammarInfo


from api.core.google_sheets_db import GoogleSheetsDB

T = TypeVar('T', bound=BaseModel)


# ==================== Abstract Repository (interface) ====================

class BaseRepository(ABC, Generic[T]): 
    @abstractmethod
    async def get(self, id: str) -> Optional[T]:
        """Get single entity by its unique ID."""
        pass
    
    @abstractmethod
    async def get_all(self, filters: Optional[Dict[str, Any]] = None, 
                      skip: int = 0, limit: int = 100) -> List[T]:
        """Get list of entities with optional filtering and pagination."""
        pass
    
    @abstractmethod
    async def add(self, entity: T) -> T:
        """Add a new entity. Return the added entity (with generated ID if any)."""
        pass
    
    @abstractmethod
    async def update(self, id: str, entity: T) -> Optional[T]:
        """Update existing entity. Return updated entity or None if not found."""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete entity by ID. Return True if deleted, False if not found."""
        pass
    
    @abstractmethod
    async def exists(self, filters: Dict[str, Any]) -> bool:
        """Check if any entity matches the given filters."""
        pass

# ==================== Simple Google Sheets Repository (synchronous) ====================
# Used by legacy or simple CRUD operations (not used by sheet repositories currently)

class SimpleSheetsRepository:
    """Simple synchronous repository for direct dict operations on Google Sheets."""
    def __init__(self, sheet_name: str, worksheet_name: str):
        self.db = GoogleSheetsDB(sheet_name, worksheet_name)

    def get_all(self, filters: Optional[Dict] = None) -> List[Dict]:
        records = self.db.read_all()
        if filters:
            records = [r for r in records if all(r.get(k) == v for k, v in filters.items())]
        return records

    def get_by_id(self, id: str, id_field="id") -> Optional[Dict]:
        return self.db.find_by_id(id, id_field)

    def get_by_field(self, field: str, value: Any) -> List[Dict]:
        return self.db.find_by_field(field, str(value))

    def insert(self, data: Dict) -> Dict:
        return self.db.insert(data)

    def update(self, id: str, updates: Dict, id_field="id") -> Optional[Dict]:
        return self.db.update(id, updates, id_field)

    def delete(self, id: str, id_field="id") -> bool:
        return self.db.delete(id, id_field)

# ==================== Grammar Repository (placeholder) ====================

class GrammarRepository(BaseRepository[GrammarInfo]):
    """Placeholder for future grammar repository."""
    
    async def get(self, id: str) -> Optional[GrammarInfo]:
        return None
    
    async def get_all(self, filters: Optional[Dict] = None, skip: int = 0, limit: int = 100) -> List[GrammarInfo]:
        return []
    
    async def add(self, entity: GrammarInfo) -> GrammarInfo:
        return entity
    
    async def update(self, id: str, entity: GrammarInfo) -> Optional[GrammarInfo]:
        return None
    
    async def delete(self, id: str) -> bool:
        return False
    
    async def exists(self, filters: Dict) -> bool:
        return False