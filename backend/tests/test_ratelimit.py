"""The image token bucket.

Worth testing properly because it is the thing standing between a two-per-
minute project quota and a game that wants six pictures: if it paces wrongly
the failure is not an exception, it is a game whose later rooms are blank.
"""

import asyncio
import time

from app.llm.ratelimit import TokenBucket


async def test_the_first_burst_goes_straight_through():
    bucket = TokenBucket(2.0)
    started = time.monotonic()
    assert await bucket.take()
    assert await bucket.take()
    assert time.monotonic() - started < 0.05


async def test_the_next_token_has_to_wait_for_the_refill():
    # 120/minute is two per second, so the third token is ~0.5s out.
    bucket = TokenBucket(120.0, burst=2)
    await bucket.take()
    await bucket.take()

    started = time.monotonic()
    assert await bucket.take()
    waited = time.monotonic() - started
    assert 0.3 < waited < 1.5


async def test_a_timeout_gives_up_rather_than_blocking_the_player():
    bucket = TokenBucket(1.0, burst=1)
    assert await bucket.take()
    assert await bucket.take(timeout=0.05) is False


async def test_draining_believes_the_server_over_our_accounting():
    bucket = TokenBucket(60.0, burst=5)
    bucket.drain()
    assert await bucket.take(timeout=0.01) is False


async def test_a_rate_of_zero_means_unlimited():
    """`IMAGE_RPM=0` turns the limiter off, for a project with a raised quota."""
    bucket = TokenBucket(0.0)
    assert all(await asyncio.gather(*(bucket.take() for _ in range(20))))


async def test_waiters_are_served_one_at_a_time():
    bucket = TokenBucket(120.0, burst=1)
    results = await asyncio.gather(*(bucket.take(timeout=2.0) for _ in range(3)))
    assert all(results)
