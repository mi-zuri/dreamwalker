from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Vertex AI serves text and images; see docs/architecture.md.
    gcp_project: str = ""
    gcp_location: str = "global"  # Gemini on Vertex is served from the global endpoint
    text_model: str = "gemini-3.5-flash-lite"
    image_model: str = "gemini-3.1-flash-lite-image"

    # Lyria RealTime is Gemini-API-only, so the music proxy needs its own key.
    gemini_api_key: str = ""
    music_model: str = "models/lyria-realtime-exp"
    music_mode: Literal["realtime", "loops"] = "realtime"

    # "mock" replays recorded fixtures and spends nothing.
    llm_mode: Literal["live", "mock"] = "mock"
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
    assets_bucket: str = ""

    # Hard monthly spend cap, in USD, checked before every generation.
    monthly_budget_usd: float = 2.40

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]


settings = Settings()
