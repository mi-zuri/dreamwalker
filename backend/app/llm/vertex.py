"""Vertex AI, wrapped so the rest of the backend never imports `google.genai`.

Three things live here and nowhere else: the retry policy, the
structured-output contract, and token accounting.

One gotcha worth stating plainly, because it cost an afternoon: `genai.Client`
closes its transport when it is garbage-collected, so calling
`genai.Client(...).models.generate_content(...)` on a temporary works exactly
once and then fails with "the client has been closed". The client is cached at
module scope for that reason.
"""

import asyncio
import json
import logging
import math
import random
from functools import lru_cache
from typing import Any, TypeVar

from google.genai import Client, types
from pydantic import BaseModel, ValidationError

from app.llm.base import LLM, GenerationError, Usage
from app.llm.ratelimit import TokenBucket
from app.settings import settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

#: One initial attempt plus this many retries, per call.
MAX_RETRIES = 2
BASE_BACKOFF_SECONDS = 0.8
#: Image calls are rate-limited far more tightly than they are priced, so a
#: retry is usually a wait rather than a second attempt at a broken request.
MAX_IMAGE_RETRIES = 2
#: Inputs per embedding request. The API accepts more; this keeps one failure
#: from costing a whole region's worth of vectors.
EMBED_BATCH = 100
#: What to wait after a 429 on the image model, in seconds. The quota window
#: is a minute, so anything shorter just burns another attempt.
QUOTA_BACKOFF_SECONDS = 32.0


@lru_cache(maxsize=1)
def image_budget() -> TokenBucket:
    """Shared by every game in this process, because the quota is per project."""
    return TokenBucket(settings.image_rpm)


def _is_quota(error: Exception) -> bool:
    text = str(error)
    return "429" in text or "RESOURCE_EXHAUSTED" in text


@lru_cache(maxsize=1)
def vertex_client() -> Client:
    if not settings.gcp_project:
        raise GenerationError("GCP_PROJECT is unset; live generation needs a Vertex project")
    return Client(
        vertexai=True,
        project=settings.gcp_project,
        location=settings.gcp_location,
    )


def _is_missing_model(error: Exception) -> bool:
    """Vertex answers an un-allowlisted model with 404, not with a clear error."""
    text = str(error).lower()
    return "404" in text or "not_found" in text or "was not found" in text


def _text_of(response: Any) -> str:
    if getattr(response, "text", None):
        return response.text
    for candidate in getattr(response, "candidates", None) or []:
        parts = getattr(candidate.content, "parts", None) or []
        joined = "".join(getattr(p, "text", "") or "" for p in parts)
        if joined:
            return joined
    return ""


def _image_of(response: Any) -> bytes | None:
    for candidate in getattr(response, "candidates", None) or []:
        parts = getattr(getattr(candidate, "content", None), "parts", None) or []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline is not None and inline.data:
                return inline.data
    return None


class VertexLLM(LLM):
    """The live model. One instance per game, so `usage` is that game's bill."""

    def __init__(self) -> None:
        self.usage = Usage()
        self._text_model = settings.text_model

    async def json(
        self,
        stage: str,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 1.0,
    ) -> T:
        client = vertex_client()
        attempt_prompt = prompt
        last: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=self._text_model,
                    contents=attempt_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=temperature,
                        system_instruction=system,
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - the SDK raises a wide family
                if _is_missing_model(exc) and self._text_model != settings.text_model_fallback:
                    log.warning(
                        "%s not available on Vertex, falling back to %s",
                        self._text_model,
                        settings.text_model_fallback,
                    )
                    self._text_model = settings.text_model_fallback
                    continue
                last = exc
                await self._backoff(attempt)
                continue

            self._meter(stage, response)
            try:
                return self._parse(response, schema)
            except (ValidationError, json.JSONDecodeError) as exc:
                # Re-prompt with the validation error attached: a model that
                # got the shape wrong usually fixes it when shown how.
                last = exc
                attempt_prompt = (
                    f"{prompt}\n\nYour previous answer did not fit the schema:\n{exc}\n"
                    "Answer again, with valid JSON only."
                )
                await self._backoff(attempt)

        raise GenerationError(f"stage {stage!r} failed after {MAX_RETRIES + 1} attempts: {last}")

    async def image(self, stage: str, prompt: str, *, timeout: float | None = None) -> bytes | None:
        client = vertex_client()
        bucket = image_budget()

        for attempt in range(MAX_IMAGE_RETRIES + 1):
            if not await bucket.take(timeout=timeout):
                log.info("image stage %s gave up waiting for quota", stage)
                return None
            try:
                response = await client.aio.models.generate_content(
                    model=settings.image_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
                )
            except Exception as exc:  # noqa: BLE001
                if _is_quota(exc):
                    # Our bucket and the server's disagree. Believe the server.
                    bucket.drain()
                    log.info("image quota hit on stage %s; waiting it out", stage)
                    if timeout is not None:
                        return None
                    await asyncio.sleep(QUOTA_BACKOFF_SECONDS)
                    continue
                log.warning("image stage %s attempt %d failed: %s", stage, attempt + 1, exc)
                await self._backoff(attempt)
                continue

            data = _image_of(response)
            if data is not None:
                self.usage.add_image(stage)
                return data
            log.warning("image stage %s returned no image part", stage)

        # A scene without a picture is still a scene.
        return None

    def _meter(self, stage: str, response: Any) -> None:
        meta = getattr(response, "usage_metadata", None)
        self.usage.add_text(
            stage,
            int(getattr(meta, "prompt_token_count", 0) or 0),
            int(getattr(meta, "candidates_token_count", 0) or 0),
        )

    def _parse(self, response: Any, schema: type[T]) -> T:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        text = _text_of(response).strip()
        if not text:
            raise GenerationError("model returned an empty response")
        return schema.model_validate(json.loads(text))

    async def _backoff(self, attempt: int) -> None:
        await asyncio.sleep(BASE_BACKOFF_SECONDS * (2**attempt) * (0.7 + random.random() * 0.6))

    async def vision(
        self,
        stage: str,
        prompt: str,
        images: list[bytes],
        schema: type[T],
        *,
        system: str | None = None,
    ) -> T:
        """Reading images costs input tokens only - there is no image quota here.

        The two-per-minute limit applies to image *generation*; describing a
        picture is an ordinary text call that happens to carry attachments.
        """
        client = vertex_client()
        parts: list[types.Part] = [
            types.Part.from_bytes(data=data, mime_type=_guess_mime(data)) for data in images
        ]
        parts.append(types.Part.from_text(text=prompt))

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=self._text_model,
                    contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        system_instruction=system,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("vision stage %s attempt %d failed: %s", stage, attempt + 1, exc)
                await self._backoff(attempt)
                continue

            self._meter(stage, response)
            try:
                return self._parse(response, schema)
            except (ValidationError, json.JSONDecodeError) as exc:
                log.warning("vision stage %s returned unusable JSON: %s", stage, exc)
                await self._backoff(attempt)

        raise GenerationError(f"vision stage {stage!r} failed")

    async def embed(self, stage: str, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = vertex_client()
        vectors: list[list[float]] = []

        for start in range(0, len(texts), EMBED_BATCH):
            chunk = texts[start : start + EMBED_BATCH]
            response = await client.aio.models.embed_content(
                model=settings.embed_model,
                contents=chunk,
                config=types.EmbedContentConfig(
                    output_dimensionality=settings.embed_dimensions,
                    task_type="SEMANTIC_SIMILARITY",
                ),
            )
            vectors.extend(_unit(e.values or []) for e in (response.embeddings or []))
            meta = getattr(response, "metadata", None)
            self.usage.add_embeddings(
                stage,
                int(getattr(meta, "billable_character_count", 0) or 0) // 4
                or sum(len(t) for t in chunk) // 4,
            )

        if len(vectors) != len(texts):
            raise GenerationError(
                f"embedding returned {len(vectors)} vectors for {len(texts)} inputs"
            )
        return vectors


def _unit(values: list[float]) -> list[float]:
    """Normalized on arrival, so every later comparison is a plain dot product."""
    norm = math.sqrt(sum(v * v for v in values))
    return [v / norm for v in values] if norm else list(values)


def _guess_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
