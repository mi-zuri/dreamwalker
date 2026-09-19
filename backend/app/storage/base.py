"""Storage interface.

Two implementations: an in-process one for local runs and tests, and
Firestore for anything real. The pipeline only ever sees this protocol.
"""

from typing import Protocol

from app.models.game import EndingComparison, GameState, Replay, SavedGame
from app.models.script import GameScript


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

    async def add_spend(self, usd: float) -> float:
        """Adds to the month-to-date total and returns the new value."""
        ...

    async def month_spend(self) -> float: ...
