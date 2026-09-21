"""Deterministic placeholder scene images.

Ported from the Phase 1 mock (`web/src/mocks/placeholder.ts`) so fixture games
look identical against the real backend. Real scenes are Cloud Storage URLs;
these are generated on the fly, cost nothing and need no assets on disk.
"""

PALETTES: dict[str, tuple[str, str, str]] = {
    "cold": ("#0b1020", "#1b2b4a", "#3d5a8a"),
    "rust": ("#160d0a", "#3a1f14", "#7a4a2a"),
    "moss": ("#0a1410", "#153026", "#2f5c46"),
    "dusk": ("#120c1a", "#2a1a3a", "#57407a"),
    "ash": ("#0d0d12", "#232330", "#4a4a5e"),
}

COLS, ROWS = 16, 12
_MASK = 0xFFFFFFFF


def _hash(seed: str) -> int:
    """FNV-1a, truncated to 32 bits to match the JavaScript original."""
    h = 2166136261
    for char in seed:
        h = (h ^ ord(char)) & _MASK
        h = (h * 16777619) & _MASK
    return h


def placeholder_svg(seed: str, palette: str = "cold") -> str:
    """A 16x12 block mosaic, upscaled by the browser with pixelation on."""
    bg, mid, hi = PALETTES.get(palette, PALETTES["cold"])
    rng = _hash(seed)

    cells: list[str] = []
    for y in range(ROWS):
        for x in range(COLS):
            rng = (rng * 1664525 + 1013904223) & _MASK
            # Horizon-ish weighting: sky up top, denser mass toward the bottom.
            weight = rng / 4294967296 + (y / ROWS) * 0.5
            fill = hi if weight > 1.05 else mid if weight > 0.6 else bg
            if fill != bg:
                cells.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{fill}"/>')

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 12" '
        'shape-rendering="crispEdges">'
        f'<rect width="16" height="12" fill="{bg}"/>{"".join(cells)}</svg>'
    )
