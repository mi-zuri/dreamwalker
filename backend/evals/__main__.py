"""`python -m evals` - the whole suite, or one dimension of it.

Exits non-zero when any dimension falls below its threshold, so this is
usable as a CI step rather than as something a person has to read.
"""

import argparse
import asyncio
import sys

from evals import DIMENSIONS
from evals.harness import Context, run_all
from evals.report import as_json, render


def _settings_for_offline() -> None:
    """No network, no ingest, no store: the suite builds its own worlds."""
    from app.settings import settings

    settings.llm_mode = "fake"
    settings.storage_mode = "memory"
    settings.assets_mode = "memory"
    settings.news_ingest_enabled = False
    settings.pool_min_playable = 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evals", description=__doc__)
    parser.add_argument("--only", action="append", default=[], metavar="NAME")
    parser.add_argument("--samples", type=int, default=5, help="trials per dimension")
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--verbose", action="store_true", help="print every case, not just failures"
    )
    parser.add_argument("--list", action="store_true", help="name the dimensions and stop")
    parser.add_argument(
        "--live",
        action="store_true",
        help="use Vertex for the dimensions a real model can be judged on. Costs money.",
    )
    args = parser.parse_args(argv)

    if args.list:
        for dimension in DIMENSIONS:
            mark = " (live-capable)" if dimension.live_capable else ""
            print(f"{dimension.name:<18} {dimension.about}{mark}")
        return 0

    chosen = [d for d in DIMENSIONS if not args.only or d.name in args.only]
    unknown = set(args.only) - {d.name for d in DIMENSIONS}
    if unknown:
        parser.error(f"no such dimension: {', '.join(sorted(unknown))}")

    if args.live:
        chosen = [d for d in chosen if d.live_capable]
        if not chosen:
            parser.error("none of the chosen dimensions can be evaluated against a live model")
    else:
        _settings_for_offline()

    ctx = Context(samples=args.samples, seed=args.seed, live=args.live)
    results = asyncio.run(run_all(chosen, ctx))

    print(as_json(results) if args.json else render(results, verbose=args.verbose))
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
