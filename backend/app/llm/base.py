"""What the pipeline is allowed to know about a model.

Stages never touch `google.genai` directly: they ask an `LLM` for structured
JSON or for an image, and every call is metered. That is what lets the whole
pipeline run offline against `MockLLM` in tests, and what makes the monthly
spend cap enforceable rather than aspirational.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)

#: Vertex AI list price for `gemini-3.5-flash-lite`, USD per million tokens.
TEXT_INPUT_USD_PER_M = 0.30
TEXT_OUTPUT_USD_PER_M = 2.50
#: `gemini-embedding-001`, USD per million input tokens. Small enough that
#: embedding a whole region's articles costs a fraction of a cent.
EMBED_USD_PER_M = 0.15
#: `gemini-3.1-flash-lite-image` is flat per image, whatever the resolution -
#: which is why image *count* is the only lever, and we deliberately do not
#: pull it.
IMAGE_USD = 0.0336


class Usage(BaseModel):
    """Running total for one game. Converted to dollars at the list price."""

    input_tokens: int = 0
    output_tokens: int = 0
    embed_tokens: int = 0
    images: int = 0
    calls: int = 0
    #: Per-stage token totals, for the cost breakdown in the logs.
    by_stage: dict[str, int] = Field(default_factory=dict)

    @property
    def usd(self) -> float:
        return (
            self.input_tokens / 1_000_000 * TEXT_INPUT_USD_PER_M
            + self.output_tokens / 1_000_000 * TEXT_OUTPUT_USD_PER_M
            + self.embed_tokens / 1_000_000 * EMBED_USD_PER_M
            + self.images * IMAGE_USD
        )

    def add_text(self, stage: str, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1
        self.by_stage[stage] = self.by_stage.get(stage, 0) + input_tokens + output_tokens

    def add_embeddings(self, stage: str, tokens: int) -> None:
        self.embed_tokens += tokens
        self.calls += 1
        self.by_stage[stage] = self.by_stage.get(stage, 0) + tokens

    def add_image(self, stage: str) -> None:
        self.images += 1
        self.calls += 1
        self.by_stage[stage] = self.by_stage.get(stage, 0)

    def summary(self) -> str:
        return (
            f"{self.calls} calls, {self.input_tokens}in/{self.output_tokens}out tokens, "
            f"{self.embed_tokens} embedded, {self.images} images, ${self.usd:.4f}"
        )


class GenerationError(RuntimeError):
    """A stage could not produce usable output after its retries."""


class LLM(Protocol):
    usage: Usage

    async def json(
        self,
        stage: str,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 1.0,
    ) -> T: ...

    async def embed(self, stage: str, texts: list[str]) -> list[list[float]]:
        """One unit-length vector per input, in the same order.

        Used for clustering articles into events and for deciding whether a
        player has already played something very like this. Never for search.
        """
        ...

    async def vision(
        self,
        stage: str,
        prompt: str,
        images: list[bytes],
        schema: type[T],
        *,
        system: str | None = None,
    ) -> T:
        """Structured JSON about a set of images.

        Used to check that a press photo is safe to show and to work out which
        location it belongs to. Same contract as `json`, with pictures.
        """
        ...

    async def image(self, stage: str, prompt: str, *, timeout: float | None = None) -> bytes | None:
        """PNG bytes, or `None` when no image could be had in time.

        `timeout` bounds the wait for image quota, not the request. A caller
        that is holding the player up passes one; background work does not.
        A missing image is never fatal: the scene renders without it.
        """
        ...
