"""Firestore-backed store.

Layout, per the plan:
    users/{uid}/games/{game_id}            live + finished game state
    users/{uid}/scripts/{game_id}          pregenerated content + turn log
    users/{uid}/saved/{game_id}            library entries
    users/{uid}/endings/{game_id}
    users/{uid}/replays/{game_id}
    users/{uid}/style_cards/{game_id}       per-player anti-repetition history
    users/{uid}/played_events/{event_id}    per-player news dedup
    users/{uid}/music/{YYYY-MM-DD}          music minutes, metered not billed
    events/{region}/pool/{event_id}         the regional event pool
    events/{region}                         pool metadata (last refresh)
    budget/{YYYY-MM}                       month-to-date spend

Documents are single-owner blobs read and written whole, which is what makes
the document model the right fit here rather than a relational one.
"""

import asyncio
from datetime import UTC, datetime

from google.cloud import firestore

from app.models.game import (
    EndingComparison,
    GameState,
    Region,
    Replay,
    SavedGame,
    StyleCard,
)
from app.models.script import GameScript
from app.news.models import Event, PlayedEvent, PoolStatus
from app.settings import settings


def _dump(model) -> dict:
    """Datetimes as ISO strings: Firestore would store them as timestamps and
    hand them back with a different tzinfo class than Pydantic wrote."""
    return model.model_dump(mode="json")


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

    async def put_style_card(self, uid: str, game_id: str, card: StyleCard) -> None:
        await (
            self._user(uid)
            .collection("style_cards")
            .document(game_id)
            .set({**card.model_dump(), "at": datetime.now(UTC).isoformat()})
        )

    async def recent_style_cards(self, uid: str, limit: int) -> list[StyleCard]:
        query = (
            self._user(uid)
            .collection("style_cards")
            .order_by("at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        cards: list[StyleCard] = []
        async for doc in query.stream():
            data = doc.to_dict() or {}
            data.pop("at", None)
            cards.append(StyleCard(**data))
        return cards

    # ── news pool ───────────────────────────────────────────────────────

    def _pool(self, region: Region):
        return self._db.collection("events").document(region).collection("pool")

    async def get_pool(self, region: Region) -> list[Event]:
        return [Event(**doc.to_dict()) async for doc in self._pool(region).stream()]

    async def put_pool(self, region: Region, events: list[Event]) -> None:
        """Writes the merged pool and prunes whatever is no longer in it.

        The caller has already merged, so anything missing here has expired.
        Firestore has no "replace collection", hence the explicit delete pass.
        """
        pool = self._pool(region)
        keep = {event.id for event in events}
        stale = [doc.id async for doc in pool.stream() if doc.id not in keep]

        await asyncio.gather(
            *(pool.document(e.id).set(_dump(e)) for e in events),
            *(pool.document(doc_id).delete() for doc_id in stale),
        )
        await (
            self._db.collection("events")
            .document(region)
            .set({"refreshed_at": datetime.now(UTC).isoformat()}, merge=True)
        )

    async def put_event(self, region: Region, event: Event) -> None:
        await self._pool(region).document(event.id).set(_dump(event))

    async def pool_status(self, region: Region) -> PoolStatus:
        from app.news.pool import playable

        events = await self.get_pool(region)
        snap = await self._db.collection("events").document(region).get()
        raw = (snap.to_dict() or {}).get("refreshed_at") if snap.exists else None
        return PoolStatus(
            region=region,
            total=len(events),
            playable=len(playable(events)),
            refreshed_at=datetime.fromisoformat(raw) if raw else None,
        )

    async def mark_played(self, uid: str, played: PlayedEvent) -> None:
        await (
            self._user(uid).collection("played_events").document(played.event_id).set(_dump(played))
        )

    async def played_events(self, uid: str, limit: int = 100) -> list[PlayedEvent]:
        query = (
            self._user(uid)
            .collection("played_events")
            .order_by("played_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [PlayedEvent(**doc.to_dict()) async for doc in query.stream()]

    def _music_doc(self, uid: str):
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        return self._user(uid).collection("music").document(day)

    async def add_music_minutes(self, uid: str, minutes: float) -> float:
        doc = self._music_doc(uid)
        await doc.set({"minutes": firestore.Increment(minutes)}, merge=True)
        snap = await doc.get()
        return float((snap.to_dict() or {}).get("minutes", 0.0))

    async def music_minutes(self, uid: str) -> float:
        snap = await self._music_doc(uid).get()
        return float((snap.to_dict() or {}).get("minutes", 0.0)) if snap.exists else 0.0

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
