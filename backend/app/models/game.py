"""Game domain models.

These are the source of truth for the API contract: `web/src/api/schema.d.ts`
is generated from the OpenAPI schema they produce, so the frontend's types
cannot drift from them.
"""

from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["idea", "news"]
Region = Literal["pl", "world"]
Language = Literal["pl", "en"]
SafetyClass = Literal["allowed", "safe_mode", "blocked"]
BeatStatus = Literal["pending", "matched", "diverged", "skipped"]

#: Travel shows the full map; scene shows the location's text and choices.
View = Literal["travel", "scene"]

#: Coarse progress enum. The UI only ever shows a vague label for these, so
#: adding a stage here does not leak pipeline detail to the player.
Stage = Literal["story", "map", "images", "music", "finishing"]


class StyleCard(BaseModel):
    genre: str
    narrative_voice: str
    tone: str
    protagonist_role: str
    visual_style: str
    music_mood: str
    pacing: str


class Pos(BaseModel):
    x: int
    y: int


class Destination(BaseModel):
    #: The character used for this destination in `GameMap.tiles`.
    key: str
    location_id: str
    name: str


class Door(BaseModel):
    key: str
    pos: Pos
    #: Destination that must be reached before this door opens.
    unlock_from: str


class GameMap(BaseModel):
    """Tile grid. `#` wall, `.` floor, `+` locked door, `@` start, `A`-`E` destinations."""

    width: int
    height: int
    tiles: list[str]
    destinations: list[Destination]
    doors: list[Door] = Field(default_factory=list)


class ImageCredit(BaseModel):
    source_url: str
    credit: str


class Scene(BaseModel):
    id: str
    location_id: str
    #: May contain `[POI:..]`, `[LOC:..]` and `[KEY:..]` highlight markers.
    text: str
    image_url: str | None = None
    image_credit: ImageCredit | None = None


class Choice(BaseModel):
    id: str
    text: str


class OpenQuestion(BaseModel):
    id: str
    prompt: str


class BeatProgress(BaseModel):
    beat_id: str
    status: BeatStatus


class GameState(BaseModel):
    game_id: str
    mode: Mode
    view: View = "scene"
    region: Region | None = None
    story_language: Language
    ui_language: Language
    safety_class: SafetyClass = "allowed"
    #: Shown before play starts when `safety_class` is `safe_mode`.
    content_note: str | None = None
    #: "Based on real events, dramatized" - news mode only.
    source_note: str | None = None
    style_card: StyleCard
    map: GameMap
    player_pos: Pos
    #: Destinations the player has stepped on.
    visited: list[str] = Field(default_factory=list)
    #: Destinations where the player has actually made a choice.
    resolved: list[str] = Field(default_factory=list)
    #: Destinations whose doors are now open.
    unlocked: list[str] = Field(default_factory=list)
    current_scene: Scene
    choices: list[Choice] = Field(default_factory=list)
    open_question: OpenQuestion | None = None
    beat_progress: list[BeatProgress] = Field(default_factory=list)
    divergence: float = 0.0
    turn: int = 0
    finished: bool = False


class CanonBeat(BaseModel):
    id: str
    title: str
    summary: str
    sources: list[str] = Field(default_factory=list)


class PlayerBeat(BaseModel):
    beat_id: str
    status: BeatStatus
    what_you_did: str


class SourceLink(BaseModel):
    url: str
    title: str


class EndingComparison(BaseModel):
    game_id: str
    mode: Mode
    #: News mode only - idea mode has no canon to score against.
    match_score: float | None = None
    title: str
    summary: str
    canon: list[CanonBeat] = Field(default_factory=list)
    player: list[PlayerBeat] = Field(default_factory=list)
    style_card: StyleCard
    sources: list[SourceLink] = Field(default_factory=list)


class SavedGame(BaseModel):
    game_id: str
    mode: Mode
    region: Region | None = None
    title: str
    played_at: str
    story_language: Language
    match_score: float | None = None
    image_url: str | None = None


class ReplayTurn(BaseModel):
    turn: int
    scene: Scene
    player_pos: Pos
    chosen: str | None = None
    answer: str | None = None


class Replay(BaseModel):
    game_id: str
    title: str
    turns: list[ReplayTurn] = Field(default_factory=list)


# ── Requests ────────────────────────────────────────────────────────────


class NewGameRequest(BaseModel):
    mode: Mode
    idea: str | None = None
    region: Region | None = None
    story_language: Language
    ui_language: Language


class NewGameResponse(BaseModel):
    game_id: str


class StageEvent(BaseModel):
    """One SSE frame from the loading stream: a stage, then finally `ready`."""

    stage: Stage | None = None
    ready: bool = False


class ApiError(BaseModel):
    """Every failure the UI can show. `kind` is what the client branches on."""

    kind: Literal[
        "network",
        "generation_failed",
        "pool_empty",
        "budget_exceeded",
        "blocked_event",
        "auth",
    ]
    detail: str


class MoveRequest(BaseModel):
    to: Pos


class ChooseRequest(BaseModel):
    choice_id: str


class AnswerRequest(BaseModel):
    text: str
