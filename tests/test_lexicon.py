"""The research layer: synchronic senses, two clocks, no root-etymology."""

from __future__ import annotations

import json
from pathlib import Path

from app.lexicon import (
    LEXICAL_RULES,
    archaic_words_in,
    lemma_entries_for,
    lexical_context,
)

DATA = Path(__file__).resolve().parents[1] / "app" / "data"


def test_detects_1611_drift_words():
    found = {item["word"] for item in archaic_words_in(
        "Charity suffereth long; our conversation is in heaven."
    )}
    assert {"charity", "conversation", "suffer"} & found
    charity = next(i for i in archaic_words_in("charity") if i["word"] == "charity")
    assert "love" in charity["sense_1611"].lower()
    assert "donation" in charity["commonly_misread_as"].lower()


def test_lemma_lookup_is_usage_based():
    entries = lemma_entries_for("charity")
    assert entries, "expected at least one lemma the KJV renders as 'charity'"
    agape = [e for e in entries if e["strongs"] == "G26"]
    assert agape, f"expected G26 among {[e['strongs'] for e in entries]}"
    assert agape[0]["language"] == "Greek"
    assert "1st century" in agape[0]["era"]


def test_root_derivation_is_never_loaded():
    """The etymological fallacy is prevented at the data layer: Strong's
    derivation field is excluded from the built lexicon entirely."""
    lexicon = json.loads((DATA / "lexicon.json").read_text(encoding="utf-8"))
    for code in ("G26", "G1411", "H2617"):
        entry = lexicon["entries"].get(code)
        if entry:
            assert "derivation" not in entry, f"{code} must not carry root-derivation data"


def test_context_payload_carries_synchronic_rule():
    payload = lexical_context(
        "Does charity here mean giving money?",
        ["Charity suffereth long, and is kind; charity envieth not"],
    )
    assert payload["rules"] == LEXICAL_RULES
    assert "etymological fallacy" in payload["rules"]
    assert "range" in payload["rules"].lower()
    assert any(item["word"] == "charity" for item in payload["kjv_1611_drift"])
    assert payload["original_language_lemmas"]
    assert all("era" in lemma for lemma in payload["original_language_lemmas"])
