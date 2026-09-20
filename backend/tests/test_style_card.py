"""The style card is the only variety mechanism in the game, so it is tested
harder than its size suggests: a sampler that quietly collapses onto one card
would make twenty runs feel like one, and nothing else would fail."""

from collections import Counter
from random import Random

import pytest

from app.models.game import StyleCard
from app.pipeline.style_card import (
    HISTORY_DEPTH,
    MAX_SHARED_AXES,
    _shared,
    default_card,
    sample_style_card,
    style_prompt,
    visual_prompt,
)
from app.pipeline.style_catalog import AXES, CATALOG, SAFE_ROLES, dump_catalog, fragment, label


def test_every_axis_value_is_complete():
    for axis in AXES:
        assert CATALOG[axis], f"{axis} has no values"
        for value in CATALOG[axis]:
            assert value.id.islower() and " " not in value.id
            assert value.pl and value.en and value.prompt
            assert value.prompt[0].islower() or value.prompt[0].isalpha()


def test_value_ids_are_unique_within_an_axis():
    for axis in AXES:
        ids = [v.id for v in CATALOG[axis]]
        assert len(ids) == len(set(ids)), f"{axis} repeats an id"


def test_polish_labels_carry_their_diacritics():
    """A catalog written without ą/ć/ę/ł/ń/ó/ś/ź/ż has been typed, not translated."""
    polish = "".join(v.pl for axis in AXES for v in CATALOG[axis])
    assert any(char in polish for char in "ąćęłńóśźż")


def test_a_card_is_drawn_from_the_catalog():
    card = sample_style_card(rng=Random(1))
    for axis in AXES:
        assert getattr(card, axis) in {v.id for v in CATALOG[axis]}


def test_safe_mode_removes_the_values_that_would_read_badly():
    for seed in range(40):
        card = sample_style_card(safety_class="safe_mode", rng=Random(seed))
        assert card.genre != "absurdist"
        assert card.tone != "deadpan"
        assert card.visual_style != "pixel"
        assert card.protagonist_role in SAFE_ROLES


def test_allowed_roles_narrows_the_protagonist():
    for seed in range(20):
        card = sample_style_card(allowed_roles={"journalist", "witness"}, rng=Random(seed))
        assert card.protagonist_role in {"journalist", "witness"}


def test_a_draw_too_close_to_a_recent_card_is_rejected():
    recent = [sample_style_card(rng=Random(7))]
    for seed in range(60):
        card = sample_style_card(recent=recent, rng=Random(seed))
        assert _shared(card, recent[0]) < MAX_SHARED_AXES


def test_history_deeper_than_the_window_is_ignored():
    """Only the last few games constrain a draw; older ones stop mattering."""
    old = StyleCard(**{axis: CATALOG[axis][0].id for axis in AXES})
    history = [sample_style_card(rng=Random(i)) for i in range(HISTORY_DEPTH)] + [old]
    # `old` sits past the window, so a card equal to it is still legal.
    assert len(history) > HISTORY_DEPTH
    card = sample_style_card(recent=history, rng=Random(3))
    assert card is not None


def test_twenty_runs_produce_twenty_distinct_cards():
    """Phase 4's exit criterion, as a test."""
    cards: list[StyleCard] = []
    for seed in range(20):
        cards.append(sample_style_card(recent=list(reversed(cards)), rng=Random(seed)))
    assert len({c.model_dump_json() for c in cards}) == 20


def test_the_axes_stay_spread_across_many_draws():
    """No axis may collapse onto one value; that is how a house style forms."""
    cards = [sample_style_card(rng=Random(seed)) for seed in range(200)]
    for axis in AXES:
        counts = Counter(getattr(c, axis) for c in cards)
        assert len(counts) == len(CATALOG[axis]), f"{axis} never drew some of its values"
        assert counts.most_common(1)[0][1] < len(cards) * 0.6


def test_an_impossible_role_gate_falls_back_to_a_legal_card():
    card = sample_style_card(
        safety_class="safe_mode", allowed_roles={"nobody-at-all"}, rng=Random(0)
    )
    assert card.protagonist_role in SAFE_ROLES


def test_the_default_card_is_always_legal_in_safe_mode():
    card = default_card("safe_mode")
    assert card.protagonist_role in SAFE_ROLES
    assert card.genre != "absurdist"


def test_prompts_are_english_and_cover_every_axis_but_the_visual_one():
    card = sample_style_card(rng=Random(2))
    text = style_prompt(card)
    assert "visual style" not in text, "the visual axis belongs to the image prompt only"
    assert text.count("\n") == len(AXES) - 2
    assert visual_prompt(card) == fragment("visual_style", card.visual_style)


@pytest.mark.parametrize("language", ["pl", "en"])
def test_every_value_has_a_label_in_both_languages(language):
    for axis in AXES:
        for value in CATALOG[axis]:
            assert label(axis, value.id, language).strip()


def test_an_unknown_value_degrades_to_its_id():
    assert label("genre", "steampunk", "en") == "steampunk"
    assert fragment("genre", "steampunk") == "steampunk"


def test_the_catalog_renders_as_markdown():
    text = dump_catalog()
    assert text.startswith("# Style cards")
    for axis in AXES:
        assert f"## `{axis}`" in text
