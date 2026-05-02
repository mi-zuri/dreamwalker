// index.ts (multiple agents - director, storyteller and brancher) orchestrator provides all key elements, run orchestrator every time from init, storyteller should be 1 constant, brancher should run from init every 5 steps
// Additionally idea generator at the start - him + story teller can have higher temperatures

# Dreamwalker Implementation Plan

## Tech Stack
- **Frontend:** React + Vite + Tailwind
- **Backend:** Node.js (Express)
- **AI Models:** Claude (narrative), DALL-E 3 (images), Lyria Realtime (audio)
- **Database:** SQLite (local file-based)
- **Deployment:** Local app only

## Architecture
```
┌─────────────────────────────────────────────────────┐
│                   React Frontend                     │
│  (Game UI, Zustand State, Media Display)             │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                   Node.js Backend                    │
│  (Game Logic, AI Orchestration, Caching, Seeds)      │
└────────────────────────┬────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌─────────┐    ┌───────────┐    ┌───────────┐
   │ Claude  │    │ DALL-E 3  │    │  Lyria    │
   │(narrative)   │ (images)  │    │ (audio)   │
   └─────────┘    └───────────┘    └───────────┘
```

---

## Phase 1: Core Foundation

**Scope:** Project scaffolding, state management, metrics engine, basic UI

1. Vite + React + Tailwind setup
2. Express backend with API routes
3. Metrics module: Action, Emotion, SelfConsciousness (-100 to +100)
4. Derived: Luck, Turbulence
5. Stability rules + wake detection
6. Basic UI: metric bars, step text, choice buttons

**Tests:**
- [ ] Drift toward 0 at 5pts/step
- [ ] Depth amplification: × (1 + depth×0.15)
- [ ] Luck = 50 + E/2 + SC/2 - Depth×5 - TensionMod
- [ ] Wake after 3 steps |A|>50 or |E|>50
- [ ] Wake immediately when |SC|>70
- [ ] Turbulence = |A| + |E|

---

## Phase 2: Narrative Engine

**Scope:** Claude integration, decisions, attempts, timed events

1. Claude API client + structured prompts
2. Step schema: context, decisions[], attempts[]
3. Precompute current + 1-forward
4. Attempt success: 50 + (Luck × 0.3)
5. Timed event component (10s countdown)
6. Imagined element → emotion bias

**Tests:**
- [ ] Claude returns valid step JSON
- [ ] Decisions affect metrics (hidden magnitude)
- [ ] Attempt success ~40-65%
- [ ] Timed correct: -15 A/E
- [ ] Timed wrong: +25 A/E
- [ ] Imagined biases ±5-15 E

---

## Phase 3: Dream Structure

**Scope:** Depth system, POI, locations, map

1. Depth state + descent triggers
2. POI types: Reach, Understand, Deliver, Escape, Witness
3. Location manager (max 5/layer, change every 3-8 steps)
4. Spatial map component
5. Backtrack penalty: +8 SC
6. 87 step limit

**Tests:**
- [ ] Descent on POI fulfilled
- [ ] Descent on context shift (15+ steps, stable, POI change)
- [ ] 20% momentum carryover
- [ ] Backtrack +8 SC
- [ ] Max 87 steps → descent/wake
- [ ] Max 5 locations

---

## Phase 4: Media Generation

**Scope:** DALL-E 3 images, Lyria audio, caching

1. Image service + disk cache
2. Audio streaming service
3. Preloader (next location ahead)
4. Style tags (writing, visual, audio)
5. Pre-game style preferences

**Tests:**
- [ ] Image on location change
- [ ] Audio streams, updates on location
- [ ] Cache hit skips generation
- [ ] Style tags in prompts
- [ ] Preloader runs in background

---

## Phase 5: Persistence & Polish

**Scope:** Seeds, logs, wake screen, instability, items

1. Seed storage: master, step, style
2. Dream log generator
3. Wake screen: cause, depth, steps, POIs
4. Inconsistency (turbulence>70 → 15%)
5. Hallucination on 2+ backtrack
6. Single-item inventory

**Tests:**
- [ ] Same seed → identical session
- [ ] Log saves on descent/wake
- [ ] Wake shows correct cause
- [ ] Inconsistency chance scales
- [ ] Hallucination triggers
- [ ] Item modifies interpretation

---

## Caching Strategy

| Asset | Location | TTL | Preload |
|-------|----------|-----|---------|
| Step text | Memory | Session | +1 forward |
| Images | Disk | 24h | Next location |
| Audio | Disk | 24h | Current location |
| Seeds | SQLite | Forever | — |

---

## Verification

Per phase:
1. `bun run test` — unit tests pass
2. Manual 1-layer playthrough
3. Metrics behave per formulas
4. AI returns valid JSON
5. Cache works (no re-fetch)
