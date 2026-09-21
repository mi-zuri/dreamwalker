"""Rendering a run. Plain text for a person, JSON for anything else."""

import json
from collections.abc import Iterable

from evals.harness import Result

_HEADER = f"{'DIMENSION':<18}{'CASES':>7}{'PASSED':>8}{'RATE':>9}{'NEED':>8}  "


def render(results: Iterable[Result], *, verbose: bool = False) -> str:
    results = list(results)
    lines = [_HEADER, "-" * (len(_HEADER) + 6)]

    for result in results:
        if result.error:
            lines.append(f"{result.dimension.name:<18}{'-':>7}{'-':>8}{'-':>9}{'-':>8}  ERROR")
            lines.append(f"    {result.error}")
            continue
        lines.append(
            f"{result.dimension.name:<18}"
            f"{len(result.cases):>7}"
            f"{result.passed:>8}"
            f"{result.rate * 100:>8.1f}%"
            f"{result.dimension.threshold * 100:>7.0f}%"
            f"  {'ok' if result.ok else 'FAIL'}"
            f"   {result.seconds:.1f}s"
        )

    total = sum(len(r.cases) for r in results)
    passed = sum(r.passed for r in results)
    rate = passed / total if total else 0.0
    ok = all(r.ok for r in results)
    lines += [
        "-" * (len(_HEADER) + 6),
        f"{'':<18}{total:>7}{passed:>8}{rate * 100:>8.1f}%{'':>8}  {'PASS' if ok else 'FAIL'}",
    ]

    for result in results:
        shown = result.cases if verbose else result.failures
        if not shown:
            continue
        lines += ["", f"-- {result.dimension.name} --"]
        for case in shown:
            mark = "ok  " if case.passed else "FAIL"
            lines.append(f"  {mark} {case.name}" + (f"  -- {case.detail}" if case.detail else ""))

    return "\n".join(lines)


def as_json(results: Iterable[Result]) -> str:
    results = list(results)
    return json.dumps(
        {
            "passed": all(r.ok for r in results),
            "dimensions": [
                {
                    "name": r.dimension.name,
                    "threshold": r.dimension.threshold,
                    "cases": len(r.cases),
                    "passed": r.passed,
                    "rate": round(r.rate, 4),
                    "ok": r.ok,
                    "seconds": round(r.seconds, 2),
                    "error": r.error,
                    "failures": [{"name": c.name, "detail": c.detail} for c in r.failures],
                }
                for r in results
            ],
        },
        indent=2,
    )
