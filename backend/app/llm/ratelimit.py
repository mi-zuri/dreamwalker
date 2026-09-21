"""A token bucket for image generation.

Vertex allows this project **two image-generation requests per minute**
(`GenContentImageGenRequestsPerMinutePerProjectPerBaseModel...`, verified
live). That is a project-wide limit, not a per-game one, and it is the actual
constraint on images here - cost is not, at $0.0336 flat per image.

Two per minute sounds fatal for a game that wants six pictures, and it very
nearly is if they are all demanded at once. It is survivable because the
player does not need them at once: they read the opening, walk for fifteen
seconds, read a scene, choose. Generating in the order the player will arrive,
one token at a time, puts each image roughly where it is needed.

So the limiter does not exist to be polite to the API. It exists so that the
image *nobody has reached yet* is the one that waits.
"""

import asyncio
import time


class TokenBucket:
    """Refills continuously, so a burst of two is allowed and then it paces."""

    def __init__(self, rate_per_minute: float, burst: int | None = None) -> None:
        self.rate = max(rate_per_minute, 0.0) / 60.0
        self.capacity = float(burst if burst is not None else max(rate_per_minute, 1))
        self._tokens = self.capacity
        self._at = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        self._tokens = min(self.capacity, self._tokens + (now - self._at) * self.rate)
        self._at = now

    async def take(self, timeout: float | None = None) -> bool:
        """Wait for a token. Returns False if `timeout` passed first."""
        if self.rate <= 0:
            return True
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
                wait = (1.0 - self._tokens) / self.rate
            if deadline is not None:
                left = deadline - time.monotonic()
                if left <= 0:
                    return False
                wait = min(wait, left)
            await asyncio.sleep(min(wait, 5.0))

    def drain(self) -> None:
        """Called after a 429: the server disagrees with our accounting."""
        self._refill()
        self._tokens = 0.0
