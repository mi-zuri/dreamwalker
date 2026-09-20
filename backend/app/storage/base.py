"""Storage interface.

Two implementations: an in-process one for local runs and tests, and
Firestore for anything real. The pipeline only ever sees this protocol.
"""

from typing import Protocol

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


class GameStore(Protocol):
    async def put_state(self, uid: str, state: GameState) -> None: ...

    async def get_state(self, uid: str, game_id: str) -> GameState | None: ...

    async def put_script(self, uid: str, script: GameScript) -> None: ...

    async def get_script(self, uid: str, game_id: str) -> GameScript | None: ...

    async def save_finished(
        self, uid: str, saved: SavedGame, ending: EndingComparison, replay: Replay
    ) -> None: ...

    async def list_saved(self, uid: str) -> list[SavedGame]: ...

    async def get_ending(self, uid: str, game_id: str) -> EndingComparison | None: ...

    async def get_replay(self, uid: str, game_id: str) -> Replay | None: ...

    async def put_style_card(self, uid: str, game_id: str, card: StyleCard) -> None:
        """Records what this player just played, for the anti-repetition check."""
        ...

    async def recent_style_cards(self, uid: str, limit: int) -> list[StyleCard]:
        """This player's most recent cards, newest first. Never anyone else's."""
        ...

    # ── news pool ───────────────────────────────────────────────────────

    async def get_pool(self, region: Region) -> list[Event]:
        """Every pooled event for a region, newest ingest first. Never raises."""
        ...

    async def put_pool(self, region: Region, events: list[Event]) -> None:
        """Replaces the stored pool with an already-merged list."""
        ...

    async def put_event(self, region: Region, event: Event) -> None:
        """Writes back one event - used after enrichment caches a dossier."""
        ...

    async def pool_status(self, region: Region) -> PoolStatus: ...

    async def mark_played(self, uid: str, played: PlayedEvent) -> None: ...

    async def played_events(self, uid: str, limit: int = 100) -> list[PlayedEvent]: ...

    async def add_spend(self, usd: float) -> float:
        """Adds to the month-to-date total and returns the new value."""
        ...

    async def month_spend(self) -> float: ...
