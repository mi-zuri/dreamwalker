# 🌙 DREAMWALKER

## Complete Design Document

---

## I. OVERVIEW

**Dreamwalker** is a systemic, generative narrative game where players navigate surreal dream sequences while maintaining psychological balance. It functions as both:

- **Player Experience:** Controlled immersion in unstable dream environments
- **Evaluation Platform:** Closed-loop environment for testing human/AI long-horizon cognitive regulation

**Core Question:** _"How long can you keep dreaming?"_

Players may pursue maximum depth strategically or engage artistically without concern for longevity.

---

## II. PSYCHOLOGICAL SYSTEM

### **Core Metrics**

All metrics range from **-100 to +100**.  
**Stable zone: -40 to +40**

#### **Action**

External intensity: urgency, motion, danger, physical activity.

- **Too high (+40 to +100):** Shock wake
- **Too low (-40 to -100):** Stagnation wake

#### **Emotion**

Internal intensity: fear, awe, attachment, distress, joy.

- **Too high (+40 to +100):** Emotional overload wake
- **Too low (-40 to -100):** Dissociation wake

#### **Self-Consciousness**

Awareness of dreaming and deliberate control.

- Increases when player manipulates state directly, backtracks, or overanalyzes
- **High values (>60):** Increased wake risk
- No low-end penalty (low awareness is natural)

### **Derived Metric: Luck**

**Luck = f(Action, Emotion, Self-Consciousness)**

Calculation:

```
Luck = 50 - (|Action| + |Emotion|) / 4 - Self-Consciousness / 2
Range: -100 to +50
```

Influences attempt success probability. Balanced metrics = better luck.

### **Turbulence**

**Turbulence = |Action| + |Emotion|**

Represents overall dream instability. Effects:

- Increases inconsistency frequency
- Increases hallucination probability
- Amplifies attempt outcome volatility
- Intensifies media distortion

Visual indicator appears only when turbulence exceeds threshold (>60).

### **Stability Rules**

- **Metric Drift:** All metrics drift toward 0 at **5 points/step**
- **Extreme Duration:** Remaining outside stable zone for **3 consecutive steps** triggers wake
- **Depth Amplification:** All metric changes multiply by `1 + (depth × 0.15)`
    - Depth 1: 1.15× multiplier
    - Depth 5: 1.75× multiplier

### **Wake Conditions**

Wake occurs when:

1. Any core metric remains extreme (outside -40 to +40) for 3 steps
2. Turbulence exceeds **150** for 2 consecutive steps
3. Self-consciousness exceeds **80**

Wake screen displays **tags explaining cause** (e.g., "Emotional Overload," "Lucidity Break," "Existential Shock").

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
- Increases hallucination probability (+10% per depth)
- Intensifies visual/audio distortion
- Shortens stability margin (less forgiveness for extremes)

#### **Descent Triggers**

Descent occurs when:

1. **POI Fulfilled:** Player completes Point of Interest
2. **Context Shift:** Player significantly affects dream context while keeping metrics relatively stable (Action and Emotion both within -30 to +30 for 5+ steps)

#### **Descent Reset Rules**

On descent, **reset all except**:

- **Momentum carryover:** 20% of current metric values transfer to new depth
- **Emotional theme:** Subtle lingering tone (fear→unease, joy→warmth)
- **Narrative residue:** Minor thematic connection (not literal continuity)

**POI always changes** on descent.

### **Dream Structure**

Each dream layer has:

- **Maximum 87 steps**
- **Maximum 5 locations**
- **Starts in action** (never static opening)
- **Atmosphere:** Calm/melancholic, neutral, or difficult
- **Tension level:** Low, medium, high
- **Style:** Auto-generated (writing, visual, audio)
- **Short context:** 1-2 sentence premise

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

**Backtracking penalty:** Each return to previous node increases Self-Consciousness by **+8**.

**Hallucinated nodes:** Appear blurred/distorted when turbulence >80.

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

**Possible Outcomes:**

- **Success:** Desired result achieved
- **Failure:** Action fails, may destabilize
- **Strange:** Surreal twist, moderate metric shift
- **Beautiful:** Transcendent result, stabilizing
- **Horrific:** Disturbing result, destabilizing

**Success Calculation:**

```
Base Success Rate = 50%
Modified by Luck: Final Rate = 50 + (Luck × 0.3)
Range: 20% to 65%
```

**Effects:**

- Success: Moderate Action +10 to +20
- Failure: Moderate Emotion +15 to +25
- Strange: High turbulence spike (+30 combined)
- Beautiful: Strong stabilization (-20 to both metrics)
- Horrific: Strong destabilization (+35 to both metrics)

### **Timed Events**

Rare sequences (5-10% of steps) requiring quick correct actions.

**Properties:**

- 3-5 sequential choices
- Time pressure (implicit, not literal countdown)
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

Altered memories or false steps.

**Types:**

- **Memory alteration:** Past events remembered differently
- **False steps:** Player believes they took action they didn't
- **Phantom choices:** Options that weren't actually available

**Frequency:**

```
Base Rate = 0%
+ (Turbulence / 10)% 
+ (Depth × 2)%
Example: Depth 4, Turbulence 80 = 16% per step
```

**Effects:**

- Can reshape perceived reality
- May alter narrative continuity
- Increase Self-Consciousness when recognized (+10)

---

## VII. ITEM SYSTEM

### **Inventory**

Holds **1 symbolic item maximum**.

### **Properties**

- **Acquisition:** Rare (10-15% of dreams contain obtainable item)
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

Each dream auto-generates three style dimensions:

**Writing Style:**

- Poetic, clinical, fragmented, verbose, minimalist, etc.
- Influences narration tone and vocabulary

**Visual Style:**

- Photorealistic, painterly, noir, surreal, etc.
- Determines image generation aesthetic

**Audio Style:**

- Ambient, melodic, industrial, silent, etc.
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
- Both update each step

### **Media Generation Timing**

- **Images:** Generated for current step + precomputed for immediate forward steps
- **Audio:** Layered system with persistent background + reactive elements
- **Distortion:** Increases with turbulence and depth
    - Visual: Blur, color shift, fragmentation
    - Audio: Reverb, pitch shift, static

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

## XI. BENCHMARK CAPABILITIES

_Secondary application: cognitive evaluation platform_

### **Metrics Tracked**

**Performance:**

- Steps survived
- Maximum depth reached
- POIs completed
- Session count

**Stability:**

- Stability variance (how much metrics fluctuate)
- Time in extreme states
- Wake cause distribution

**Quality:**

- Narrative coherence ratings (human evaluation)
- Decision quality scores
- Hallucination resistance (how often agent is misled)

**Control:**

- Self-awareness control (maintaining low self-consciousness)
- Strategic balance (safety vs goal pursuit)
- Multi-modal alignment (text-image-audio consistency perception)

### **Evaluation Dimensions**

- **Long-horizon coherence:** Maintaining consistent strategy over 50+ steps
- **Emotional regulation:** Balancing engagement without overload
- **Strategic flexibility:** Adapting to changing situations
- **Uncertainty tolerance:** Handling ambiguous outcomes

### **Leaderboard Types**

- Human players
- AI models (different model families)
- Hybrid agents (human + AI assistance)

---

## XII. FUTURE FEATURES

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

**Seed 1:** Following love interest through sunny school campus (calm atmosphere, low tension)

**Seed 2:** Fleeing monster through branching, looping corridors (difficult atmosphere, high tension)

**Seed 3:** [Additional seeds to be developed]