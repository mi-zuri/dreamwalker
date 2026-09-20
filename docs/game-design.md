# The game

What Dreamwalker is, as a thing you play. For how it is built, see
[architecture.md](architecture.md).

## In one paragraph

You give it a sentence, or you let it reach for the news. It writes a short
story, draws a small walkable map of that story's world, illustrates each
place, scores ambient music live, and hands you three mechanics to move
through it with. A run takes **two to ten minutes**. At the end it tells you
what your story became — and in News mode, how far it drifted from what
actually happened.

## A session

| | |
|---|---|
| **Menu** | Type an idea, or leave the box empty and pick a region. Set the interface language and the story language separately. |
| **Loading** | 6–10 s. A vague stage label and the `z / zz / zzz` loader. |
| **Content note** | Safe-mode runs only. One sentence about the subject, with a way to back out. |
| **Travel** | The ASCII map. Walk to a lettered destination. |
| **Scene** | 3–5 sentences, three choices, and once or twice a run a question you answer by typing. |
| **Ending** | What your run became. News mode adds the real account, citations and a match score. |
| **Library** | Every run is saved and can be replayed turn by turn. |

Three to five destinations per run, three choices per scene, at most two open
questions. Those numbers are the two-to-ten-minute budget.

## The two modes

| | **Idea** | **News** |
|---|---|---|
| Brief | the sentence you typed | a real recent event |
| Region | — | Polish or World |
| Canon | none | a beat graph built from the sources |
| Ending | a recap of what your story became | recap **plus** what happened, sources, match score |
| Safety | not classified | classified before the event ever enters the pool |

They share every stage after the brief.

## The three mechanics

**Walking.** An ASCII tile grid: `#` wall, `.` floor, `+` locked door,
`@` you, `A`–`E` destinations. A door opens when you reach the place that
unlocks it, so the map has an order without a quest log. Click a tile or use
the arrow keys; the client animates the path, the server re-walks it and
ignores anything it cannot reach.

**Choices.** Three per scene, presented as equals. One of them is the one the
story — or the real event — leaned towards; which one is decided when the
scene is written and kept server-side. You are never told, and nothing pushes
you back on course. The world just reacts as though you had done what you did.

**Open questions.** Once or twice a run, instead of three options you get a
prompt and a text box. What you write is carried into the ending.

## Divergence

News mode tracks each canon beat as `pending`, `matched`, `diverged` or
`skipped`, and keeps a running divergence figure. The scene prompt is told
that figure and instructed to let consequences accumulate — never to railroad
you back. The ending's **match score** is the order-weighted fraction of beats
you hit, weighted towards the later ones: finishing a real event the way it
actually finished is a stronger result than getting its opening right.

Idea mode has no match score. There is nothing to be right about.

## Style cards

Every run draws a card of seven axes:

`genre` · `narrative_voice` · `tone` · `protagonist_role` · `visual_style` ·
`music_mood` · `pacing`

The card runs through every prompt after it — plan, scenes, image prompts,
music, ending — so two games from the same idea do not read or look alike.
Axis values are language-neutral ids with a Polish label, an English label and
an English prompt fragment, which is what makes the same card work in both
languages. The catalog is in [style-cards.md](style-cards.md).

Two constraints on the draw: a **safety gate** removes values that read badly
over a real tragedy, and **anti-repetition** avoids what *you* have seen in
your last five runs. There is no global check — two strangers drawing the same
card is not a problem worth making one player's variety depend on another's.

## Language

Interface language and story language are set separately, and the story
language is independent of the region: a Polish player can play World news in
Polish. Image prompts are always written in English, with a clause forbidding
text on the picture, because letters on an image are the one failure mode
nothing downstream could fix.

## Real events, handled carefully

Anything not worth dramatizing is blocked during scoring and never enters the
pool. Anything that is a real tragedy is played in **safe mode**: you are a
rescuer, witness, official, journalist or volunteer rather than a victim; no
graphic injury; private individuals are anonymized during enrichment, so
nothing downstream ever holds a name it could leak; a content note appears
before the game starts; and the ending never frames a death toll as a score.
Every News run carries a "based on real events, dramatized" line and its
sources. See [safety.md](safety.md).

## What this replaced

The original design was a dream simulator: arousal/valence/self-awareness
metrics, derived luck and turbulence, wake conditions, 87 steps, descent into
deeper dream layers, an inventory, hallucinations and inconsistencies. All of
it was cut. What survived is the terminal look, the live generation and the
idea of a short run you can replay. The reasoning is in
[decisions.md](decisions.md).
