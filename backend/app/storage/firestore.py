"""Firestore-backed store.

Layout, per the plan:
    users/{uid}/games/{game_id}            live + finished game state
    users/{uid}/scripts/{game_id}          pregenerated content + turn log
    users/{uid}/saved/{game_id}            library entries
    users/{uid}/endings/{game_id}
    users/{uid}/replays/{game_id}
    budget/{YYYY-MM}                       month-to-date spend

Documents are single-owner blobs read and written whole, which is what makes
the document model the right fit here rather than a relational one.
"""

import asyncio
from datetime import UTC, datetime

from google.cloud import firestore

from app.models.game import EndingComparison, GameState, Replay, SavedGame
from app.models.script import GameScript
from app.settings import settings


class FirestoreStore:
    def __init__(self) -> None:
        self._db = firestore.AsyncClient(project=settings.gcp_project)

    def _user(self, uid: str):
        return self._db.collection("users").document(uid)

    async def put_state(self, uid: str, state: GameState) -> None:
        await self._user(uid).collection("games").document(state.game_id).set(state.model_dump())

    async def get_state(self, uid: str, game_id: str) -> GameState | None:
        snap = await self._user(uid).collection("games").document(game_id).get()
        return GameState(**snap.to_dict()) if snap.exists else None

    async def put_script(self, uid: str, script: GameScript) -> None:
        await (
            self._user(uid).collection("scripts").document(script.game_id).set(script.model_dump())
        )

    async def get_script(self, uid: str, game_id: str) -> GameScript | None:
        snap = await self._user(uid).collection("scripts").document(game_id).get()
        return GameScript(**snap.to_dict()) if snap.exists else None

    async def save_finished(
        self, uid: str, saved: SavedGame, ending: EndingComparison, replay: Replay
    ) -> None:
        user = self._user(uid)
        await asyncio.gather(
            user.collection("saved").document(saved.game_id).set(saved.model_dump()),
            user.collection("endings").document(saved.game_id).set(ending.model_dump()),
            user.collection("replays").document(saved.game_id).set(replay.model_dump()),
        )

    async def list_saved(self, uid: str) -> list[SavedGame]:
        query = (
            self._user(uid)
            .collection("saved")
            .order_by("played_at", direction=firestore.Query.DESCENDING)
        )
        return [SavedGame(**doc.to_dict()) async for doc in query.stream()]

    async def get_ending(self, uid: str, game_id: str) -> EndingComparison | None:
        snap = await self._user(uid).collection("endings").document(game_id).get()
        return EndingComparison(**snap.to_dict()) if snap.exists else None

    async def get_replay(self, uid: str, game_id: str) -> Replay | None:
        snap = await self._user(uid).collection("replays").document(game_id).get()
        return Replay(**snap.to_dict()) if snap.exists else None

    def _budget_doc(self):
        month = datetime.now(UTC).strftime("%Y-%m")
        return self._db.collection("budget").document(month)

    async def add_spend(self, usd: float) -> float:
        """Atomic increment, so concurrent games cannot race past the cap."""
        doc = self._budget_doc()
        await doc.set({"usd": firestore.Increment(usd)}, merge=True)
        snap = await doc.get()
        return float((snap.to_dict() or {}).get("usd", 0.0))

    async def month_spend(self) -> float:
        snap = await self._budget_doc().get()
        return float((snap.to_dict() or {}).get("usd", 0.0)) if snap.exists else 0.0
