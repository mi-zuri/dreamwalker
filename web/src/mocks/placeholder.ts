/**
 * Mock scene images. Blocky SVG data URIs in the project palette, so Phase 1
 * stays self-contained (no binary assets, no network) while still exercising
 * the `.pixel-img` treatment and the fixed-width image panel.
 */

const PALETTES: Record<string, [string, string, string]> = {
  cold: ['#0b1020', '#1b2b4a', '#3d5a8a'],
  rust: ['#160d0a', '#3a1f14', '#7a4a2a'],
  moss: ['#0a1410', '#153026', '#2f5c46'],
  dusk: ['#120c1a', '#2a1a3a', '#57407a'],
  ash: ['#0d0d12', '#232330', '#4a4a5e'],
};

function hash(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Deterministic 16x12 block mosaic, upscaled by the browser with pixelation on. */
export function placeholderImage(seed: string, palette: keyof typeof PALETTES = 'cold'): string {
  const [bg, mid, hi] = PALETTES[palette] ?? PALETTES.cold;
  let rng = hash(seed);
  const next = () => (rng = (rng * 1664525 + 1013904223) >>> 0) / 4294967296;

  const cells: string[] = [];
  for (let y = 0; y < 12; y++) {
    for (let x = 0; x < 16; x++) {
      const r = next();
      // Horizon-ish weighting: sky up top, denser mass toward the bottom.
      const weight = r + (y / 12) * 0.5;
      const fill = weight > 1.05 ? hi : weight > 0.6 ? mid : bg;
      if (fill !== bg) cells.push(`<rect x="${x}" y="${y}" width="1" height="1" fill="${fill}"/>`);
    }
  }

  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 12" shape-rendering="crispEdges">` +
    `<rect width="16" height="12" fill="${bg}"/>${cells.join('')}</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export type PaletteName = keyof typeof PALETTES;
