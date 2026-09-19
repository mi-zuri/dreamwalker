"""In-process store. Lost on restart; fine for local runs and tests."""

from collections import defaultdict
from datetime import UTC, datetime

from app.models.game import EndingComparison, GameState, Replay, SavedGame
from app.models.script import GameScript


class MemoryStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], GameState] = {}
        self._scripts: dict[tuple[str, str], GameScript] = {}
        self._saved: dict[str, list[SavedGame]] = defaultdict(list)
        self._endings: dict[tuple[str, str], EndingComparison] = {}
        self._replays: dict[tuple[str, str], Replay] = {}
        self._spend: dict[str, float] = defaultdict(float)

    async def put_state(self, uid: str, state: GameState) -> None:
        self._states[(uid, state.game_id)] = state

    async def get_state(self, uid: str, game_id: str) -> GameState | None:
        return self._states.get((uid, game_id))

    async def put_script(self, uid: str, script: GameScript) -> None:
        self._scripts[(uid, script.game_id)] = script

    async def get_script(self, uid: str, game_id: str) -> GameScript | None:
        return self._scripts.get((uid, game_id))

    async def save_finished(
        self, uid: str, saved: SavedGame, ending: EndingComparison, replay: Replay
    ) -> None:
        games = self._saved[uid]
        if not any(g.game_id == saved.game_id for g in games):
            games.insert(0, saved)
        self._endings[(uid, saved.game_id)] = ending
        self._replays[(uid, saved.game_id)] = replay

    async def list_saved(self, uid: str) -> list[SavedGame]:
        return list(self._saved[uid])

    async def get_ending(self, uid: str, game_id: str) -> EndingComparison | None:
        return self._endings.get((uid, game_id))

    async def get_replay(self, uid: str, game_id: str) -> Replay | None:
        return self._replays.get((uid, game_id))

    def _month(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m")

    async def add_spend(self, usd: float) -> float:
        self._spend[self._month()] += usd
        return self._spend[self._month()]

    async def month_spend(self) -> float:
        return self._spend[self._month()]
