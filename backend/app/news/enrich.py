"""Turning a scored event into something playable.

This is the expensive half of the news pipeline and it is therefore the half
that runs least: collecting and scoring a whole region costs a fraction of a
cent and happens for everything, while enrichment reads real articles and
writes a beat graph and happens only for an event somebody is about to play.
The result is cached on the event, so the second player to draw it pays
nothing at all.

Everything here is in the source language. Translating the dossier would be a
separate call and a separate bill; instead the scene stage is handed the
dossier as it stands plus an instruction about which language to write in,
and does the adaptation inside a call it was making anyway.
"""

import asyncio
import logging

import httpx
from pydantic import BaseModel, Field

from app.llm.base import LLM
from app.models.plan import Certainty
from app.news.fulltext import fetch_bodies
from app.news.models import Dossier, Event, Fact, Person, Photo
from app.news.sources.rss import TIMEOUT, USER_AGENT
from app.storage.assets import AssetStore, asset_key

log = logging.getLogger(__name__)

STAGE = "dossier"
PHOTO_STAGE = "photo-safety"

#: Beats in a canon graph. Fewer than three is not a story; more than five
#: will not fit a two-to-ten minute game.
MIN_BEATS, MAX_BEATS = 3, 5
#: Press photos considered per event. Each one is an input-token cost in the
#: safety check and a location candidate later.
MAX_PHOTOS = 4
#: Bigger than this and it is a hero banner or an ad, not a press photo.
MAX_PHOTO_BYTES = 6_000_000


class PersonDraft(BaseModel):
    name: str
    role: str = ""
    public_figure: bool = False


class FactDraft(BaseModel):
    text: str
    certainty: Certainty = "high"


class CanonBeatDraft(BaseModel):
    title: str
    summary: str
    #: A named, physical place this happened - it becomes a map location.
    place: str = ""


class DossierDraft(BaseModel):
    what: str
    where: str
    when: str
    who: list[PersonDraft] = Field(default_factory=list)
    timeline: list[FactDraft] = Field(default_factory=list)
    uncertain: list[FactDraft] = Field(default_factory=list)
    beats: list[CanonBeatDraft] = Field(default_factory=list)


INSTRUCTIONS = f"""You are building a factual dossier on one real news event, from the \
articles below, for a short interactive story that will be based on it.

Write in the language the articles are written in. Do not translate.

Use only what the articles say. Where they disagree, or where something is reported but \
not confirmed, put it in `uncertain` rather than `timeline`. Invent nothing - a thin \
dossier is useful and a confident wrong one is not.

- `what`, `where`, `when`: one or two sentences each.
- `who`: the people involved. Set `public_figure` true only for someone acting in a \
public role - a politician, an official spokesperson, a company's chief executive. \
Everyone else is a private individual: give their `role` ("a neighbour", "the driver") \
and leave `name` empty. Never name a private individual, a victim or a suspect.
- `timeline`: what happened, in order, one fact per entry, with a `certainty`.
- `uncertain`: claims that are contested, attributed to a single source, or not yet \
confirmed.
- `beats`: {MIN_BEATS} to {MAX_BEATS} steps this event actually went through, in order. \
Each has a `place` - a concrete physical location a person could stand in, named as the \
articles name it. Beats are what the player's run will be compared against, so they \
must be things that happened, not themes."""


def _articles_brief(event: Event) -> str:
    lines = [f"EVENT: {event.title}", ""]
    for article in event.articles[:6]:
        body = article.body or article.summary
        lines.append(f"--- {article.source} ({article.published_at:%Y-%m-%d %H:%M}) ---")
        lines.append(article.title)
        lines.append(body[:4000])
        lines.append("")
    return "\n".join(lines)


async def enrich(llm: LLM, event: Event, assets: AssetStore | None = None) -> Event:
    """Read the articles, write the dossier and the beats, keep the photos.

    Idempotent: an event that already has a dossier is returned untouched, so
    two players drawing the same event pay for it once between them.
    """
    if event.dossier is not None:
        return event

    await fetch_bodies(event.articles)
    draft = await llm.json(STAGE, _articles_brief(event), DossierDraft, system=INSTRUCTIONS)

    event.dossier = Dossier(
        what=draft.what.strip(),
        where=draft.where.strip(),
        when=draft.when.strip(),
        who=[
            Person(
                # A private individual's name is dropped here rather than in a
                # prompt later, so nothing downstream can leak what it never had.
                name=p.name.strip() if p.public_figure else "",
                role=p.role.strip(),
                public_figure=p.public_figure,
            )
            for p in draft.who
            if p.role.strip() or p.public_figure
        ],
        timeline=[_fact(f, event) for f in draft.timeline],
        uncertain=[_fact(f, event) for f in draft.uncertain],
        language=event.language,
        # Asked of the articles rather than of the fetch, so a body that
        # arrived some other way still counts as having been read.
        thin=not any(a.body for a in event.articles),
    )
    event.beats = [b.model_dump() for b in draft.beats[:MAX_BEATS]]
    if event.dossier.thin:
        # Summary-only dossiers carry less detail, so they get a shorter graph
        # rather than a full-length one padded out of thin air.
        event.beats = event.beats[:MIN_BEATS]

    if assets is not None:
        event.photos = await collect_photos(llm, event, assets)
    return event


def _fact(draft: FactDraft, event: Event) -> Fact:
    return Fact(
        text=draft.text.strip(),
        # Per-fact attribution is not something the model can be trusted to
        # get right, so the event's own sources are attached instead.
        sources=[a.canonical_url for a in event.articles[:3]],
        certainty=draft.certainty,
    )


# ── press photos ────────────────────────────────────────────────────────


class PhotoVerdict(BaseModel):
    index: int
    safe: bool = True
    caption: str = ""


class PhotoCheck(BaseModel):
    photos: list[PhotoVerdict] = Field(default_factory=list)


PHOTO_INSTRUCTIONS = """You are checking press photographs before they are shown inside a \
game about the event they document.

For each image, in order, return its `index`, a `safe` flag and a short English \
`caption` describing what is physically in it.

Mark `safe` false for: visible injury, blood, human remains, a body, a person in \
evident extreme distress whose face is identifiable, a child's identifiable face, or \
anything that would be indecent to use as scenery. A photograph of damage, wreckage, \
emergency vehicles, crowds, buildings or officials is safe.

The caption is used to match the photograph to a place in the story, so name what is \
in it plainly: "a flooded street with a collapsed shopfront", not "a scene of sorrow"."""


async def collect_photos(llm: LLM, event: Event, assets: AssetStore) -> list[Photo]:
    """Download, store and vision-check the cluster's press photos.

    Every photo keeps the URL of the article it came from and a credit line,
    and both are rendered wherever the photo is. That does not make using
    press photography unproblematic; it makes it attributable.
    """
    candidates: list[Photo] = []
    seen: set[str] = set()
    for article in event.articles:
        if not article.image_url or article.image_url in seen:
            continue
        seen.add(article.image_url)
        candidates.append(
            Photo(
                url=article.image_url,
                source_url=article.url,
                credit=article.image_credit or article.source,
            )
        )
        if len(candidates) >= MAX_PHOTOS:
            break

    if not candidates:
        return []

    blobs = await asyncio.gather(*(_download(p) for p in candidates))
    kept = [(photo, data) for photo, data in zip(candidates, blobs, strict=True) if data]
    if not kept:
        return []

    try:
        check = await llm.vision(
            PHOTO_STAGE,
            f"Check these {len(kept)} photographs, in order.",
            [data for _, data in kept],
            PhotoCheck,
            system=PHOTO_INSTRUCTIONS,
        )
        verdicts = {v.index: v for v in check.photos}
    except Exception:
        log.exception("photo safety check failed for %s", event.id)
        verdicts = {}

    stored: list[Photo] = []
    for index, (photo, data) in enumerate(kept):
        verdict = verdicts.get(index)
        if verdict is None or not verdict.safe:
            continue
        photo.caption = verdict.caption.strip()
        photo.stored_url = await assets.put(asset_key(photo.url, ".jpg"), data, "image/jpeg")
        photo.safe = True
        stored.append(photo)
    return stored


async def _download(photo: Photo) -> bytes | None:
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            response = await client.get(photo.url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        log.info("could not download %s: %s", photo.url, exc)
        return None

    data = response.content
    if not data or len(data) > MAX_PHOTO_BYTES:
        return None
    return data
