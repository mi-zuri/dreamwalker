# 🌙 DREAMWALKER

## Complete Design Document

---

## I. OVERVIEW

**Dreamwalker** is a systemic, generative narrative game where players navigate surreal dream sequences while maintaining psychological balance.

**Core Question:** _"How long can you keep dreaming?"_

Players may pursue maximum depth strategically or engage artistically without concern for longevity.

---

## GLOSSARY

- **Session**: Launch to wake (full play period)
- **Depth/Layer**: Distance from waking reality (starts at 1, increases on descent)
- **Step**: Single interaction cycle (context → decision → outcome)
- **Node**: Location on spatial map
- **POI**: Point of Interest — current directional goal
- **Wake**: Session ends, return to real world
- **Descent**: Move deeper into dream (depth +1)

---

## II. PSYCHOLOGICAL SYSTEM

### **Core Metrics**

All metrics range from **-100 to +100**.
**Stable zone: -50 to +50**

#### **Action**

External intensity (magnitude only — sign indicates direction, not quality).

- **Positive (+):** High urgency, danger, motion (e.g., warzone, chase)
- **Negative (-):** Low urgency, lethargy, stillness (e.g., sitting on couch)
- **Extreme (|Action| > 50 for 3 steps):** Wake (shock or stagnation)

#### **Emotion**

Internal intensity (magnitude only — sign indicates direction, not quality).

- **Positive (+):** Intense feeling (e.g., love interest's touch, monster approaching)
- **Negative (-):** Calming feeling (e.g., routine situation, threat receding)
- **Extreme (|Emotion| > 50 for 3 steps):** Wake (overload or dissociation)

#### **Self-Consciousness**

Awareness of dreaming and sense of agency.

- **Positive (+):** Logic, control attempts, deliberate manipulation
- **Negative (-):** Flow state, surrendering agency, going with the dream
- **Most situations:** Neutral (near 0)
- **Extreme (|SC| > 70):** Immediate wake (lucidity break or dissolution)

### **Derived Metric: Luck**

**Luck = f(Emotion, Self-Consciousness, Depth, Tension)**

```
Luck = 50 + Emotion/2 + SelfConsciousness/2 - Depth×5 - TensionMod
TensionMod: Low=0, Medium=10, High=20
```

Influences attempt success probability. Positive emotion/agency and shallow depth = better luck.

### **Turbulence**

**Turbulence = |Action| + |Emotion|**

Represents overall dream instability. Effects:

- Increases inconsistency frequency
- Amplifies attempt outcome volatility

Visual indicator appears only when turbulence exceeds threshold (>60).

### **Stability Rules**

- **Metric Drift:** All metrics drift toward 0 at **5 points/step**
- **Extreme Duration:** Remaining outside stable zone for **3 consecutive steps** triggers wake
- **Depth Amplification:** All metric changes multiply by `1 + (depth × 0.15)`
    - Depth 1: 1.15× multiplier
    - Depth 5: 1.75× multiplier

### **Wake Conditions**

Wake occurs when:

1. **Action/Emotion extreme:** |Action| or |Emotion| > 50 for 3 consecutive steps
2. **Self-Consciousness extreme:** |SC| > 70 (immediate wake)
3. **Turbulence critical:** Turbulence > 150 for 2 consecutive steps

Wake screen displays **tags explaining cause** (e.g., "Emotional Overload," "Lucidity Break," "Dissolution").

---

## III. DREAM ARCHITECTURE

### **Session Structure**

- **Session** = Launch to wake
- Contains multiple **dream layers (depths)**
- On wake:
    - All mechanics reset
    - Dream logs and media saved
    - Session reproducible via stored seeds

### **Depth System**

**Depth** = Distance from waking reality (starts at 1).

Each deeper layer:

- Increases metric sensitivity (via amplification multiplier)
- Increases instability frequency (+15% per depth)
- Shortens stability margin (less forgiveness for extremes)

#### **Descent Triggers**

Descent occurs when:

1. **POI Fulfilled:** Player completes Point of Interest
2. **Context Shift:** All three conditions met:
   - POI changes (new POI emerges)
   - Minimum 15 steps elapsed in current layer
   - Action and Emotion both within -40 to +40 for 3 consecutive steps

#### **Descent Reset Rules**

On descent, **reset all except**:

- **Momentum carryover:** 20% of current metric values transfer to new depth
- **Emotional theme:** Subtle lingering tone (fear→unease, joy→warmth)
- **Narrative residue:** Minor thematic connection (not literal continuity)

**POI always changes** on descent.

### **Dream Structure**

Each dream layer has:

- **Maximum 87 steps** (at step 87: stable metrics → descent, unstable → wake)
- **Target duration:** ~10 minutes per layer
- **Maximum 5 locations**
- **Starts in action** (never static opening)
- **Atmosphere:** Calm/melancholic, neutral, or difficult
- **Tension level:** Low, medium, high
- **Style:** Auto-generated (writing, visual, audio)
- **Short context:** 1-2 sentence premise

### **State Flow**

```
Session Start → Depth 1 → Steps → [Descent → Depth N] or [Wake → Session End]
```

---

## IV. NAVIGATION & OBJECTIVES

### **Point of Interest (POI)**

Each dream contains **one clearly highlighted POI** providing direction (not mandatory objective).

**POI Types:**

- **Reach:** Arrive at location/person
- **Understand:** Comprehend situation/symbol
- **Deliver:** Transport object/message
- **Escape:** Exit dangerous situation
- **Witness:** Observe event

**Emerging POIs:** New POIs may appear if original becomes impossible/irrelevant.

**Presentation:** Text highly focused with strong visual highlights and stylistic emphasis (focus, substance, dreamlike magic).

### **Map System**

Small, dynamically generated **local spatial map** provides grounding.

**Properties:**

- Stable within nearby area only
- Abstract/symbolic representation
- Shows current position
- Shows where each choice leads
- Some choices keep player in same node (internal actions)

**Backtracking penalty:** Each return to previous node increases Self-Consciousness by **+8**. Attempting to backtrack 2+ steps triggers hallucinations (see Section VI).

### **Branch Visualization**

Displays beneath map:

- 1 step backward (taken path)
- Current position
- 1 step forward (all possibilities)
- Shows branching structure only, not outcomes

### **Location System**

**Locations** = Dream segments with consistent visuals and audio.

- Change every 3-8 steps
- Transitions marked by environmental shift
- Each location has distinct aesthetic, lighting, soundscape
- Maximum 5 locations per dream layer

---

## V. INTERACTION MECHANICS

### **Step Structure**

Each step contains:

1. **1-sentence context** (situation summary)
2. **POI visibility** (if relevant to current position)
3. **Decisions** (1-4 choices)
4. **Possible attempts** (uncertain actions)
5. **Media** (visual + audio)
6. **State effects** (metric changes preview)

**Generation rule:** Only current step, 1 back, and 1 forward (with outcomes) are fully real. Rest generated on-demand.

### **Decisions & Choices**

**Properties:**

- Meaningfully branch narrative
- Influence psychological metrics
- Must allow return to stability within **4-6 steps** (no death spirals)
- Labeled narratively only (no numbers)
- 1-4 options per step (average 2-3)

**Metric effects:**

- Displayed as directional indicators (↑↓) before selection
- Magnitude hidden to preserve uncertainty

### **Attempts**

Resolve uncertain actions (contested outcomes).

**Outcomes:** Success or Failure only. LLM interprets narrative flavor contextually (strange, beautiful, horrific, etc.).

**Success Calculation:**

```
Base Success Rate = 50%
Modified by Luck: Final Rate = 50 + (Luck × 0.3)
Range: ~40% to 65%
```

**Effects:**

- **Success:** Moderate Action +10 to +20
- **Failure:** Moderate Emotion +15 to +25

### **Timed Events**

Rare sequences (5-10% of steps) requiring quick correct actions.

**Properties:**

- 3-5 sequential choices
- **10-second countdown** per choice
- Simple, quick-to-read options
- Clear correct/incorrect distinction

**Consequences:**

- **Mistakes:** +25 to both Action and Emotion
- **Success:** -15 to both Action and Emotion, possible POI progress

### **Imagined Element**

Optional free-text internal thought player can add.

**Effect:**

- Subtly biases emotional direction (+/-5 to +/-15 Emotion)
- Interpreted by LLM for tonal influence
- Can introduce thematic elements to subsequent steps

---

## VI. INSTABILITY PHENOMENA

### **Inconsistencies**

Surreal contradictions in dream logic.

**Triggers:**

- Turbulence >70: 15% chance per step
- Depth 3+: +5% chance per depth level

**Effects:**

- Change state unpredictably
- Can cause beauty (stabilizing) or harm (destabilizing)
- Leave possibility to reach new equilibrium
- Examples: Time loops, identity shifts, physical impossibilities

### **Hallucinations**

Memory only holds current step, previous step, and next step possibilities.

**Trigger:** Player attempts to backtrack 2+ steps.

**Effect:** Memory of earlier steps is unreliable — details may have shifted, events remembered differently, or paths that existed may no longer be there.

**Self-Consciousness impact:** +10 when hallucination is recognized.

---

## VII. ITEM SYSTEM

### **Inventory**

Holds **1 symbolic item maximum**.

### **Properties**

- **Acquisition:** Optional choice when available (never forced). Rare opportunity (10-15% of dreams).
- **Loss conditions:**
    - Dream layer ends (descent or wake)
    - New item acquired (replaces old)
- **Effect:** Modifies interpretation of outcomes, not raw metric values

### **Interpretation Modification Example**

**Without item:**

- Choice: "Confront the figure"
- Outcome: Fear response, +20 Emotion

**With item: "A stranger's photograph"**

- Same choice: "Confront the figure"
- Outcome: Recognition instead of fear, +5 Emotion, +10 Action (investigation)

Items provide **narrative/contextual modifiers** that change how situations resolve naturally, not mathematical bonuses.

---

## VIII. PRESENTATION

### **Style Generation**

Each dream auto-generates three style dimensions. Descriptions should be evocative phrases, not single words.

**Writing Style:**

- Examples: "terse and clinical," "lush and poetic," "fragmented stream-of-consciousness," "detached observational"
- Influences narration tone and vocabulary

**Visual Style:**

- Examples: "washed-out polaroid nostalgia," "high-contrast noir shadows," "soft watercolor dreamscape," "hyperreal uncanny clarity"
- Determines image generation aesthetic

**Audio Style:**

- Examples: "distant ambient hum," "discordant industrial echoes," "gentle acoustic warmth," "oppressive silence with sparse tones"
- Shapes soundscape and music

**Pre-game prompt influence:** Player can specify preferences before session (e.g., "melancholic," "cosmic horror," "childhood nostalgia") to bias style generation.

### **User Interface**

**Always Visible:**

- Local spatial map
- POI highlight (when relevant)
- Current depth indicator
- Branch visualization

**Contextual Elements:**

- Turbulence indicator (only when >60)
- Sensation descriptions (physical/emotional feelings)
- Item slot (when item possessed)
- Metric direction previews (on choice hover)

**Media:**

- Generated image (primary visual)
- Adaptive audio (background + reactive)
- Both update every **3-5 steps** (tied to location changes)

### **Media Generation Timing**

- **Images:** Change with location transitions, not every step
- **Audio:** Persistent background per location + subtle reactive elements

---

## IX. GENERATION SYSTEM

### **LLM Responsibilities**

Generates:

1. **Steps:** Context, descriptions, situations
2. **Decisions:** Choice text and branching logic
3. **Outcomes:** Attempt results and consequences
4. **Summaries:** Dream logs and session recaps
5. **Style interpretation:** Converting style tags to concrete prose

### **Precomputation Rules**

**For current step:**

- All decision outcomes precomputed
- All attempt outcome possibilities defined
- Media generated

**1 step forward:**

- All possible steps from current decisions generated in short form
- Branching structure defined
- Outcomes sketched

**Generation philosophy:** Enough ahead to ensure coherence, not so much that branches become rigid.

### **Seed Storage**

Each session stores:

- **Master seed:** Session initialization
- **Step seeds:** Each decision point
- **Style seeds:** Generation parameters

Enables perfect reproducibility for analysis and replay.

---

## X. META & PERSISTENCE

### **Dream Logs**

After each dream layer (on descent or wake):

- Narrative summary generated
- Key moments highlighted
- Metric trajectory visualized
- Screenshots/audio clips saved

### **Session Replay**

Stored sessions can be:

- Rewatched (passive viewing)
- Replayed with same seeds (testing different choices)
- Analyzed (metric graphs, decision trees)

### **Wake Screen**

Displays on waking:

- **Primary cause tags** (e.g., "Lucidity Break," "Terror Spiral")
- **Depth reached**
- **Steps survived**
- **POIs completed**
- **Notable moments** (highest turbulence, closest calls)
- **Dream log access**

---

## XI. FUTURE FEATURES

### **Multiplayer**

- Sessions can intertwine
- Shared dream spaces
- Possible battle royale mode (competitive depth racing)
- Collaborative stabilization

### **Stable Mode**

- Players build persistent imagined worlds
- Others can visit and explore
- Reduced instability mechanics
- Focus on creativity over survival

---

## APPENDIX: CORE EXPERIENCE THEMES

- **Balance vs Immersion:** Engage deeply without losing control
- **Control vs Surrender:** Direct action vs flowing with dream logic
- **Meaning vs Safety:** Pursue POI vs maintain stability
- **Awareness vs Dissolution:** Recognize dream state vs natural dreaming

---

## EXAMPLE DREAM SEEDS

**Seed 1: The Rooftop Party**
Summer night, city lights below. Your friends are laughing, music playing. Someone suggests jumping to the next rooftop — it's closer than it looks. The wind feels perfect.
*Warm atmosphere, low tension. POI: Make it to the other side.*

**Seed 2: The Corridors**
Something is behind you. The corridors branch and loop impossibly. Doors lead to rooms you've already passed. The footsteps are getting closer.
*Difficult atmosphere, high tension. POI: Escape.*

**Seed 3: The Late Train**
You're running through a station, bag over shoulder. Your train is leaving in two minutes. People keep stepping into your path. You can see the platform number but not how to reach it.
*Urgent atmosphere, medium tension. POI: Catch the train.*

**Seed 4: The Reunion**
Old friends around a bonfire on the beach. Someone brought a guitar. The conversation keeps circling back to that one summer. You realize you're finally going to say what you never said.
*Nostalgic atmosphere, low tension. POI: Find the right moment.*

**Seed 5: The Chase**
You took something from them. Now you're sprinting through a night market, weaving between stalls. They're shouting behind you. Every turn opens a new alley.
*Thrilling atmosphere, high tension. POI: Lose them.*

**Seed 6: The Campus**
Following a half-remembered love interest through a sun-drenched school campus. Hallways stretch longer than they should. She keeps turning corners just ahead of you.
*Calm atmosphere, low tension. POI: Reach her.*