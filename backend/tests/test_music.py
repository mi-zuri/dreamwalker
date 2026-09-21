"""The music proxy, with Lyria replaced.

The parts worth testing are not the model: they are the prompt the mood and
the location build, the WAV wrapper the fallback depends on, the guard that
stops a steer being sent when nothing changed, and that a Lyria failure comes
out as a loop rather than as silence.
"""

import asyncio
import contextlib
import json
import struct

import pytest

from app.models.game import StyleCard
from app.models.plan import PlannedLocation
from app.music import loops
from app.music import session as session_module
from app.music.lyria import BYTES_PER_SECOND, MusicUnavailable, chunk_bytes
from app.music.prompts import RULES, bpm_for, location_prompt, opening_prompt
from app.storage.assets import MemoryAssets
from app.storage.memory import MemoryStore

STYLE = StyleCard(
    genre="noir",
    narrative_voice="second_present",
    tone="dry",
    protagonist_role="outsider",
    visual_style="ink_wash",
    music_mood="elegy",
    pacing="slow_burn",
)

PLACE = PlannedLocation(
    id="loc-a", name="Szopa", description="polski opis", visual="a wet shed at dusk"
)


# ── prompts ─────────────────────────────────────────────────────────────


def test_the_music_prompt_is_the_mood_and_the_place():
    text = location_prompt(STYLE, PLACE)
    assert "elegy" in text or "falling intervals" in text
    assert "a wet shed at dusk" in text
    assert RULES in text


def test_the_players_language_never_reaches_the_music_prompt():
    """`visual` is already English; `description` is not, and is not used."""
    assert "polski opis" not in location_prompt(STYLE, PLACE)


def test_no_location_yet_still_gives_a_prompt():
    assert opening_prompt(STYLE) == location_prompt(STYLE, None)


def test_pacing_sets_the_tempo_within_what_lyria_accepts():
    for pacing in ("slow_burn", "staccato", "escalating", "something_new"):
        bpm = bpm_for(STYLE.model_copy(update={"pacing": pacing}))
        assert 60 <= bpm <= 200
    assert bpm_for(STYLE.model_copy(update={"pacing": "staccato"})) > bpm_for(
        STYLE.model_copy(update={"pacing": "slow_burn"})
    )


# ── chunks and WAV ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "chunk",
    [b"abcd", bytearray(b"abcd"), memoryview(b"abcd")],
)
def test_pcm_is_found_whatever_shape_it_arrives_in(chunk):
    class Wrapped:
        data = chunk

    assert chunk_bytes(Wrapped()) == b"abcd"
    assert chunk_bytes(chunk) == b"abcd"


def test_base64_chunks_are_decoded():
    class Wrapped:
        data = "YWJjZA=="

    assert chunk_bytes(Wrapped()) == b"abcd"


def test_a_chunk_with_nothing_in_it_is_none():
    class Wrapped:
        data = 17

    assert chunk_bytes(Wrapped()) is None


def test_the_wav_header_describes_the_pcm_it_wraps():
    pcm = b"\x00\x01" * 4800
    wav = loops.to_wav(pcm)

    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert len(wav) == len(pcm) + 44
    channels, rate = struct.unpack("<HI", wav[22:28])
    assert (channels, rate) == (2, 48000)
    assert struct.unpack("<I", wav[40:44])[0] == len(pcm)


async def test_a_captured_loop_is_stored_once_and_reused(monkeypatch):
    assets = MemoryAssets()
    calls = []

    async def fake_capture(prompt, bpm, seconds):
        calls.append(prompt)
        return b"\x00\x01" * int(BYTES_PER_SECOND * seconds // 2)

    monkeypatch.setattr(loops, "capture", fake_capture)

    first = await loops.loop_url(assets, "elegy")
    second = await loops.loop_url(assets, "elegy")
    assert first == second
    assert len(calls) == 1, "the second request must not capture again"
    assert RULES in calls[0]

    stored = await assets.get(loops.loop_key("elegy"))
    assert stored is not None
    assert stored[1] == "audio/wav"
    assert stored[0][:4] == b"RIFF"


async def test_a_capture_that_comes_back_empty_is_not_stored(monkeypatch):
    async def empty(prompt, bpm, seconds):
        return b""

    monkeypatch.setattr(loops, "capture", empty)
    assert await loops.loop_url(MemoryAssets(), "drone") is None


async def test_loops_are_never_built_when_the_caller_says_not_to(monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("should not capture")

    monkeypatch.setattr(loops, "capture", boom)
    assert await loops.loop_url(MemoryAssets(), "drone", build=False) is None


# ── the session ─────────────────────────────────────────────────────────


class FakeSocket:
    """Just enough WebSocket for the session to talk to."""

    def __init__(self, inbound: list[str] | None = None) -> None:
        self.sent: list[bytes] = []
        self.said: list[dict] = []
        self.closed = False
        self._inbound = list(inbound or [])

    async def close(self) -> None:
        self.closed = True

    async def send_bytes(self, data: bytes) -> None:
        self.sent.append(data)

    async def send_text(self, text: str) -> None:
        self.said.append(json.loads(text))

    async def receive_text(self) -> str:
        if self._inbound:
            return self._inbound.pop(0)
        await asyncio.sleep(3600)
        raise AssertionError("unreachable")


def make_session(ws):
    from app.models.game import GameState, Scene
    from app.models.plan import StoryPlan
    from app.models.script import GameScript

    plan = StoryPlan(title="t", premise="p", language="en", locations=[PLACE])
    state = GameState(
        game_id="g1",
        mode="idea",
        language="en",
        style_card=STYLE,
        map={"width": 3, "height": 3, "tiles": ["###", "#@#", "###"], "destinations": []},
        player_pos={"x": 1, "y": 1},
        current_scene=Scene(id="s", location_id="loc-a", text="t"),
    )
    script = GameScript(game_id="g1", plan=plan, ending=_placeholder(state))
    return session_module.MusicSession(
        ws, state, script, store=MemoryStore(), assets=MemoryAssets(), uid="u1"
    )


def _placeholder(state):
    from app.models.game import EndingComparison

    return EndingComparison(
        game_id=state.game_id, mode="idea", title="t", summary="s", style_card=STYLE
    )


async def test_a_failed_lyria_session_becomes_a_loop_not_a_silence(monkeypatch):
    async def refuse(self):
        raise MusicUnavailable("lyria said no")

    monkeypatch.setattr("app.music.lyria.LyriaStream.open", refuse)

    async def fake_capture(prompt, bpm, seconds):
        return b"\x00\x01" * int(BYTES_PER_SECOND * seconds // 2)

    monkeypatch.setattr(loops, "capture", fake_capture)

    ws = FakeSocket()
    session = make_session(ws)
    await asyncio.wait_for(_run_until_said(session, ws), timeout=5)

    assert ws.said[-1]["mode"] == "loops"
    assert ws.said[-1]["url"]
    assert "lyria said no" in ws.said[-1]["reason"]


async def test_loops_mode_never_opens_a_live_session(monkeypatch):
    from app.settings import settings

    async def boom(self):
        raise AssertionError("should not have opened Lyria")

    monkeypatch.setattr("app.music.lyria.LyriaStream.open", boom)
    monkeypatch.setattr(settings, "music_mode", "loops")

    async def fake_capture(prompt, bpm, seconds):
        return b"\x00\x01" * int(BYTES_PER_SECOND * seconds // 2)

    monkeypatch.setattr(loops, "capture", fake_capture)

    ws = FakeSocket()
    session = make_session(ws)
    await asyncio.wait_for(_run_until_said(session, ws), timeout=5)
    assert ws.said[-1]["mode"] == "loops"


async def test_with_no_loop_available_the_client_is_told_plainly(monkeypatch):
    async def refuse(self):
        raise MusicUnavailable("no key")

    async def no_capture(prompt, bpm, seconds):
        return b""

    monkeypatch.setattr("app.music.lyria.LyriaStream.open", refuse)
    monkeypatch.setattr(loops, "capture", no_capture)

    ws = FakeSocket()
    session = make_session(ws)
    await asyncio.wait_for(_run_until_said(session, ws), timeout=5)
    assert ws.said[-1]["mode"] == "off"


async def _run_until_said(session, ws) -> None:
    task = asyncio.create_task(session.run())
    for _ in range(200):
        if ws.said:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_the_daily_music_cap_is_per_player_and_per_day():
    from app.settings import settings

    store = MemoryStore()
    assert await session_module.allowed_minutes(store, "u1")

    await store.add_music_minutes("u1", settings.music_daily_minutes + 1)
    assert not await session_module.allowed_minutes(store, "u1")
    assert await session_module.allowed_minutes(store, "u2"), "one player's use is their own"


async def test_a_second_session_for_one_game_replaces_the_first(monkeypatch):
    """A reconnect must not leave a second Lyria session running and billed."""
    from app.settings import settings

    monkeypatch.setattr(settings, "music_mode", "loops")

    async def fake_capture(prompt, bpm, seconds):
        return b"\x00\x01" * int(BYTES_PER_SECOND * seconds // 2)

    monkeypatch.setattr(loops, "capture", fake_capture)

    first_ws, second_ws = FakeSocket(), FakeSocket()
    first, second = make_session(first_ws), make_session(second_ws)

    task = asyncio.create_task(first.run())
    for _ in range(200):
        if first_ws.said:
            break
        await asyncio.sleep(0.01)
    assert session_module._live[first.state.game_id] is first

    second_task = asyncio.create_task(second.run())
    for _ in range(200):
        if second_ws.said:
            break
        await asyncio.sleep(0.01)

    assert session_module._live[first.state.game_id] is second
    assert first._stopped, "the earlier session was told to stand down"
    assert first_ws.closed, "and its socket was closed rather than left open"

    for pending in (task, second_task):
        pending.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pending
    session_module._live.clear()


async def test_a_closed_socket_ends_the_session_rather_than_raising(monkeypatch):
    """Starlette raises a plain RuntimeError once a close has been sent."""
    from app.settings import settings

    monkeypatch.setattr(settings, "music_mode", "loops")

    async def fake_capture(prompt, bpm, seconds):
        return b"\x00\x01" * int(BYTES_PER_SECOND * seconds // 2)

    monkeypatch.setattr(loops, "capture", fake_capture)

    class Closed(FakeSocket):
        async def receive_text(self) -> str:
            raise RuntimeError('Cannot call "receive" once a close message has been sent.')

    ws = Closed()
    session = make_session(ws)
    await asyncio.wait_for(session.run(), timeout=5)
    assert ws.said[-1]["mode"] == "loops"
    session_module._live.clear()
