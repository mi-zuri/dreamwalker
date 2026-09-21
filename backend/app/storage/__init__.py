from functools import lru_cache

from app.settings import settings
from app.storage.base import GameStore


@lru_cache(maxsize=1)
def get_store() -> GameStore:
    if settings.storage_mode == "firestore":
        from app.storage.firestore import FirestoreStore

        return FirestoreStore()

    from app.storage.memory import MemoryStore

    return MemoryStore()
