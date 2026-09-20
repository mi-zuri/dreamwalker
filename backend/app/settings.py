from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Vertex AI serves text and images; see docs/architecture.md.
    gcp_project: str = ""
    gcp_location: str = "global"  # Gemini on Vertex is served from the global endpoint
    text_model: str = "gemini-3.5-flash-lite"
    # Used automatically when the primary model 404s, which is how Vertex
    # reports a model this project is not allowlisted for.
    text_model_fallback: str = "gemini-3.1-flash-lite"
    image_model: str = "gemini-3.1-flash-lite-image"
    embed_model: str = "gemini-embedding-001"
    # 768 rather than the default 3072: the vectors are stored per event and
    # compared by brute force, so smaller is cheaper to keep and just as good
    # at "is this the same story".
    embed_dimensions: int = 768
    # Vertex's default image-generation quota, project-wide. Raising it is a
    # quota request; until then this is the number that shapes the pipeline.
    image_rpm: float = 2.0
    # How long the opening image may hold up the loading screen. The plan call
    # ahead of it takes four to ten seconds on its own, so this is what bounds
    # the tail: past it the game opens without a picture rather than making
    # the player watch a loading screen for a decoration.
    prologue_image_timeout: float = 6.0
    # How long the background image pass may keep going. Past the long end of
    # a game, a picture nobody will see is not worth waiting on quota for.
    background_image_seconds: float = 600.0

    # Lyria RealTime is Gemini-API-only, so the music proxy needs its own key.
    gemini_api_key: str = ""
    music_model: str = "models/lyria-realtime-exp"
    music_mode: Literal["realtime", "loops"] = "realtime"
    # Music is the one line item with no natural ceiling - every other cost is
    # paid once per game. Metered per player per day, and capped here.
    music_daily_minutes: float = 90.0

    # "mock" replays recorded fixtures; "fake" runs the real pipeline against a
    # synthetic model. Both spend nothing; only "fake" exercises generation.
    llm_mode: Literal["live", "mock", "fake"] = "mock"
    # Scales the faked loading-stage delays; tests set it to 0.
    mock_stage_scale: float = 1.0
    # Mock games replay the fixture's recorded grid by default. "generated"
    # swaps in a freshly generated floor plan for the same locations, which is
    # how the Phase 3 map generator gets walked in a browser.
    mock_map_source: Literal["fixture", "generated"] = "fixture"

    # "dev" treats every caller as one local user; deployment uses "firebase".
    auth_mode: Literal["dev", "firebase"] = "dev"

    # Launch is invite-only, which is the strongest cost control we have.
    invite_only: bool = False
    allowed_emails: list[str] = []

    # Storage. "memory" keeps games in-process for local runs.
    storage_mode: Literal["memory", "firestore"] = "memory"
    # Generated images. "memory" serves them from this process, which is
    # fine locally and useless behind more than one Cloud Run instance.
    assets_mode: Literal["memory", "gcs"] = "memory"
    assets_bucket: str = ""

    # News ingest is lazy: a News game refreshes the pool first, but only when
    # it has to. These two numbers are what "has to" means, and they are the
    # reason an idle month costs nothing.
    # A kill switch. With ingest off, News mode serves whatever is already
    # pooled and refuses politely when that runs out - which is what a bad
    # feed day or a tight budget should look like, and what tests always want.
    news_ingest_enabled: bool = True
    pool_max_age_hours: float = 6.0
    pool_min_playable: int = 12
    # A player who has played everything in a healthy pool can trigger one
    # extra refresh, but not once per attempt - otherwise exhausting the pool
    # turns every retry into an ingest.
    pool_retry_minutes: float = 30.0

    # Hard monthly spend cap, in USD, checked before every generation.
    monthly_budget_usd: float = 2.40

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]


settings = Settings()
