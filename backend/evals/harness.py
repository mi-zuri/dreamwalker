"""The scaffolding every eval dimension is written against.

An eval is not a test, and the difference is the whole reason this exists
beside `tests/`. A test asserts an invariant: it holds or the build is red.
An eval *measures* something that is allowed to be imperfect - how varied the
style cards are, how often a classification comes out right - over enough
samples that the number means something, and reports a rate against a
threshold.

So the unit here is a `Case`: one graded observation with a name. A dimension
produces many of them, the runner counts them, and the report is the artifact.
Nothing here imports a model directly; the dimensions ask the `Context` for
one, which is what lets the same suite run offline against `FakeLLM` for free
and against Vertex when someone explicitly asks for the live number.
"""

import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from random import Random

from app.llm.base import LLM


@dataclass(frozen=True)
class Case:
    """One graded observation. `detail` is only read when it failed."""

    name: str
    passed: bool
    detail: str = ""


def check(name: str, passed: bool, detail: str = "") -> Case:
    return Case(name=name, passed=bool(passed), detail=detail)


def equals(name: str, actual: object, expected: object) -> Case:
    """The common shape: a case that explains itself when it fails."""
    return Case(
        name=name,
        passed=actual == expected,
        detail=f"expected {expected!r}, got {actual!r}",
    )


@dataclass
class Context:
    """What a dimension is allowed to know about the run it is part of."""

    #: How many independent trials a dimension should take where it has the
    #: choice. Raising it makes every rate more trustworthy and slower.
    samples: int = 5
    seed: int = 20260920
    #: True when the caller asked for real models and accepted the bill.
    live: bool = False

    def rng(self, salt: str) -> Random:
        """A generator that is stable per dimension, not shared between them.

        Salting by name means adding a dimension does not shift the numbers of
        every dimension after it, which would make two reports incomparable
        for a reason that has nothing to do with the code under evaluation.
        """
        return Random(f"{self.seed}:{salt}")

    def model(self) -> LLM:
        if self.live:
            from app.llm.vertex import VertexLLM

            return VertexLLM()

        from app.llm.fake import FakeLLM

        return FakeLLM()


@dataclass(frozen=True)
class Dimension:
    """One thing being measured, and how good it has to be."""

    name: str
    #: What this dimension is for, printed by `--list`.
    about: str
    #: Fraction of cases that must pass. 1.0 means every one of them.
    threshold: float
    run: Callable[[Context], Awaitable[list[Case]]]
    #: False when every case inspects prompts or deterministic logic, and a
    #: real model would have nothing to add. Skipped under `--live`.
    live_capable: bool = False


@dataclass
class Result:
    dimension: Dimension
    cases: list[Case] = field(default_factory=list)
    seconds: float = 0.0
    error: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.passed)

    @property
    def rate(self) -> float:
        return self.passed / len(self.cases) if self.cases else 0.0

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.cases) and self.rate >= self.dimension.threshold

    @property
    def failures(self) -> list[Case]:
        return [c for c in self.cases if not c.passed]


async def run_all(dimensions: Iterable[Dimension], ctx: Context) -> list[Result]:
    results = []
    for dimension in dimensions:
        started = time.monotonic()
        result = Result(dimension=dimension)
        try:
            result.cases = await dimension.run(ctx)
        except Exception as exc:  # noqa: BLE001 - a broken dimension is a failed one
            result.error = f"{type(exc).__name__}: {exc}"
        result.seconds = time.monotonic() - started
        results.append(result)
    return results
