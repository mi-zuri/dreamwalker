"""The music WebSocket: one player, one game, one Lyria session behind it.

The connection is held open for the length of a game, which on Cloud Run is
billed for its whole duration - so it is capped at twelve minutes, which is
past the long end of a 2-10 minute game, and metered per player per day. Music
is the one line item with no natural ceiling; everything else in the system is
paid for once per game.

Three things the socket does:

* **streams PCM** from Lyria straight through to the browser;
* **steers** when the player arrives somewhere new. The client sends the
  location id it is looking at, and the prompt is rebuilt from the style card
  and that location. Nothing is re-sent when nothing changed;
* **falls back** to a captured loop if Lyria will not start or drops out. The
  browser is told which mode it is in over the same socket, so the failure is
  a change of message rather than a silence.
"""

import asyncio
import contextlib
import json
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

from app.models.game import GameState
from app.models.plan import PlannedLocation
from app.models.script import GameScript
from app.music import loops
from app.music.lyria import BYTES_PER_SECOND, LyriaStream, MusicUnavailable
from app.music.prompts import bpm_for, location_prompt
from app.settings import settings
from app.storage.assets import AssetStore
from app.storage.base import GameStore

log = logging.getLogger(__name__)

#: Cloud Run bills a WebSocket for as long as it is open, so it does not stay
#: open past the longest game anyone should be playing.
MAX_SESSION_SECONDS = 12 * 60
#: How long to wait for Lyria's first bytes before giving up on it.
FIRST_CHUNK_TIMEOUT = 20.0


def _location(script: GameScript, location_id: str | None) -> PlannedLocation | None:
    if script.plan is None or not location_id:
        return None
    return next((loc for loc in script.plan.locations if loc.id == location_id), None)


class MusicSession:
    def __init__(
        self,
        ws: WebSocket,
        state: GameState,
        script: GameScript,
        *,
        store: GameStore,
        assets: AssetStore,
        uid: str,
    ) -> None:
        self.ws = ws
        self.state = state
        self.script = script
        self.store = store
        self.assets = assets
        self.uid = uid
        self.style = state.style_card
        self._where: str | None = state.current_scene.location_id
        self._seconds = 0.0

    async def run(self) -> None:
        if settings.music_mode == "loops":
            await self._serve_loop("configured for loops")
            return
        try:
            await self._serve_live()
        except MusicUnavailable as exc:
            log.info("live music unavailable for %s: %s", self.state.game_id, exc)
            await self._serve_loop(str(exc))

    # ── live ────────────────────────────────────────────────────────────

    async def _serve_live(self) -> None:
        stream = LyriaStream(
            location_prompt(self.style, _location(self.script, self._where)),
            bpm_for(self.style),
        )
        await stream.open()
        await self._say({"mode": "realtime"})

        listener = asyncio.create_task(self._listen(stream))
        started = time.monotonic()
        first = True
        try:
            async with asyncio.timeout(MAX_SESSION_SECONDS):
                async for data in stream.chunks():
                    if first:
                        first = False
                        log.info("music started for %s", self.state.game_id)
                    await self.ws.send_bytes(data)
                    self._seconds += len(data) / BYTES_PER_SECOND
        except TimeoutError:
            log.info("music session for %s hit the 12 minute cap", self.state.game_id)
            await self._say({"mode": "off", "reason": "session_limit"})
        except WebSocketDisconnect:
            pass
        finally:
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener
            await stream.close()
            await self._meter(time.monotonic() - started)

        if first:
            # Connected, but never produced a note.
            raise MusicUnavailable("no audio arrived")

    async def _listen(self, stream: LyriaStream) -> None:
        """Steer the music as the player moves. Silence here is normal."""
        while True:
            try:
                raw = await self.ws.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                return
            try:
                where = json.loads(raw).get("location")
            except (ValueError, AttributeError):
                continue
            if not where or where == self._where:
                continue
            self._where = where
            moved = await stream.steer(
                location_prompt(self.style, _location(self.script, where)),
                bpm_for(self.style),
            )
            if moved:
                log.info("music followed %s to %s", self.state.game_id, where)

    # ── fallback ────────────────────────────────────────────────────────

    async def _serve_loop(self, reason: str) -> None:
        """Hand the browser a URL and let it loop the file itself.

        Streaming the loop back over the socket would be the same bytes over
        and over for twelve minutes; a URL the browser can cache is better in
        every way, and it keeps the connection idle rather than billed for
        traffic.
        """
        url = await loops.loop_url(self.assets, self.style.music_mood)
        if url is None:
            await self._say({"mode": "off", "reason": reason})
            return
        await self._say({"mode": "loops", "url": url, "reason": reason})
        # Stay open so the client can keep telling us where it is, and so a
        # close is a real close rather than a dropped connection.
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            while True:
                await self.ws.receive_text()

    # ── plumbing ────────────────────────────────────────────────────────

    async def _say(self, payload: dict) -> None:
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await self.ws.send_text(json.dumps(payload))

    async def _meter(self, wall_seconds: float) -> None:
        """Music minutes are metered per player per day and never billed.

        Lyria RealTime has no published price. Until it does, the honest thing
        is to count the minutes and cap them rather than invent a number and
        put it in the spend total.
        """
        minutes = max(self._seconds, wall_seconds) / 60
        total = await self.store.add_music_minutes(self.uid, minutes)
        log.info(
            "music for %s: %.1f minutes over %.0fs, %.1f today",
            self.state.game_id,
            minutes,
            wall_seconds,
            total,
        )


async def allowed_minutes(store: GameStore, uid: str) -> bool:
    """Whether this player has music left today."""
    used = await store.music_minutes(uid)
    return used < settings.music_daily_minutes
