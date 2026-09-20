"""In-process store. Lost on restart; fine for local runs and tests."""

from collections import defaultdict
from datetime import UTC, datetime

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


class MemoryStore:
    def __init__(self) -> None:
        self._states: dict[tuple[str, str], GameState] = {}
        self._scripts: dict[tuple[str, str], GameScript] = {}
        self._saved: dict[str, list[SavedGame]] = defaultdict(list)
        self._endings: dict[tuple[str, str], EndingComparison] = {}
        self._replays: dict[tuple[str, str], Replay] = {}
        self._spend: dict[str, float] = defaultdict(float)
        self._cards: dict[str, list[StyleCard]] = defaultdict(list)
        self._pool: dict[str, list[Event]] = defaultdict(list)
        self._refreshed: dict[str, datetime] = {}
        self._played: dict[str, list[PlayedEvent]] = defaultdict(list)

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

    async def put_style_card(self, uid: str, game_id: str, card: StyleCard) -> None:
        self._cards[uid].insert(0, card)
        del self._cards[uid][20:]

    async def recent_style_cards(self, uid: str, limit: int) -> list[StyleCard]:
        return self._cards[uid][:limit]

    async def get_pool(self, region: Region) -> list[Event]:
        return list(self._pool[region])

    async def put_pool(self, region: Region, events: list[Event]) -> None:
        self._pool[region] = list(events)
        self._refreshed[region] = datetime.now(UTC)

    async def put_event(self, region: Region, event: Event) -> None:
        pool = self._pool[region]
        for index, held in enumerate(pool):
            if held.id == event.id:
                pool[index] = event
                return
        pool.append(event)

    async def pool_status(self, region: Region) -> PoolStatus:
        from app.news.pool import playable

        events = self._pool[region]
        return PoolStatus(
            region=region,
            total=len(events),
            playable=len(playable(events)),
            refreshed_at=self._refreshed.get(region),
        )

    async def mark_played(self, uid: str, played: PlayedEvent) -> None:
        self._played[uid].insert(0, played)
        del self._played[uid][200:]

    async def played_events(self, uid: str, limit: int = 100) -> list[PlayedEvent]:
        return self._played[uid][:limit]

    def _month(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m")

    async def add_spend(self, usd: float) -> float:
        self._spend[self._month()] += usd
        return self._spend[self._month()]

    async def month_spend(self) -> float:
        return self._spend[self._month()]
