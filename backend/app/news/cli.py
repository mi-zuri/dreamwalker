"""Manual ingest, for development and for filling a cold pool before a demo.

    uv run python -m app.news.cli refresh --region pl
    uv run python -m app.news.cli show --region world
    uv run python -m app.news.cli collect --region pl        # free, no model

`collect` exists so the sources can be exercised without spending anything,
which is how the feed list was chosen in the first place.
"""

import argparse
import asyncio
import logging

from app.llm import make_llm
from app.news import ingest, pool
from app.news.cluster import sources_in
from app.storage import get_store


async def _collect(region: str) -> None:
    articles = await ingest.collect(region)  # type: ignore[arg-type]
    print(f"{len(articles)} articles")
    for article in articles[:20]:
        print(f"  [{article.source:10s}] {article.title[:88]}")


async def _refresh(region: str) -> None:
    llm = make_llm()
    status = await ingest.refresh(llm, get_store(), region)  # type: ignore[arg-type]
    print(f"{status.region}: {status.playable} playable of {status.total}")
    print(f"cost: {llm.usage.summary()}")


async def _show(region: str) -> None:
    events = await get_store().get_pool(region)  # type: ignore[arg-type]
    print(pool.describe(events, region))  # type: ignore[arg-type]
    for event in pool.playable(events)[:25]:
        scores = event.scores
        print(
            f"  {scores.rank:.2f} [{scores.safety_class:9s}] "
            f"{len(event.articles)}a/{sources_in(event)}o {event.title[:74]}"
        )
        if scores.reason:
            print(f"        {scores.reason}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Dreamwalker news ingest")
    parser.add_argument("command", choices=["collect", "refresh", "show"])
    parser.add_argument("--region", choices=["pl", "world"], default="pl")
    args = parser.parse_args()

    runner = {"collect": _collect, "refresh": _refresh, "show": _show}[args.command]
    asyncio.run(runner(args.region))


if __name__ == "__main__":
    main()
