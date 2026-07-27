"""The research layer — synchronic word meaning, two clocks.

Gateway answers word questions with the meaning attested **at the time of
writing**, never with root-etymology. Two independent clocks, because a KJV
reader faces two languages:

- **1611 English** — the KJV's own vocabulary has drifted. "Charity" meant
  self-giving love; "conversation" meant conduct; "prevent" meant to go
  before. `app/data/kjv_glossary.json` is the curated drift list.
- **Biblical Hebrew / Koine Greek** — the underlying lemma's attested sense
  range, from public-domain Strong's (`app/data/lexicon.json`), built with
  the root-derivation field deliberately excluded.

Three rules travel with the data into every prompt:

1. Synchronic only. Meaning is usage at the time of writing. A word's
   ancestry never proves an author's intent (the etymological fallacy).
2. Range, not point. Words carry a range of attested senses; context selects
   within it, and that selection is an interpretive judgment to be labeled,
   not asserted.
3. Sourced or silent. Any lexical claim must rest on a loaded entry, and the
   19th-century vintage of the public-domain lexicons is disclosed.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
LEXICON_PATH = DATA_DIR / "lexicon.json"
GLOSSARY_PATH = DATA_DIR / "kjv_glossary.json"

LEXICAL_RULES = (
    "SYNCHRONIC RULE (word meaning): Give only the sense a word carried at the time "
    "the text was written — Koine Greek of the first century, Biblical Hebrew of its "
    "period, and 1611 English for the KJV's own wording. Never argue from a word's "
    "root or ancestry to an author's meaning (the etymological fallacy: 'dunamis' does "
    "not mean 'dynamite'). Words carry a RANGE of attested senses; say which sense the "
    "context supports and label that selection as an interpretive judgment, not a fact. "
    "Cite only lexical data supplied below; if it is not supplied, say the lexicon is "
    "silent rather than reconstructing a meaning. The supplied lexicons are public-domain "
    "19th-century scholarship (Strong's) — reliable for basic sense ranges, not the final "
    "word of modern lexicography."
)

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'-]{2,}")


@lru_cache(maxsize=1)
def _lexicon() -> dict:
    if not LEXICON_PATH.exists():
        return {"entries": {}, "kjv_word_index": {}}
    return json.loads(LEXICON_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _glossary() -> dict:
    if not GLOSSARY_PATH.exists():
        return {"words": {}}
    return json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))


def lexicon_source() -> str:
    return _lexicon().get("source", "unavailable")


def archaic_words_in(text: str) -> list[dict]:
    """KJV-era English words present in ``text`` whose sense has drifted."""
    words = _glossary().get("words", {})
    lowered = text.lower()
    found = []
    for word, senses in words.items():
        pattern = r"\b" + re.escape(word) + (r"\b" if " " not in word else "")
        if re.search(pattern, lowered):
            found.append(
                {
                    "word": word,
                    "sense_1611": senses["then"],
                    "commonly_misread_as": senses["now_misread_as"],
                }
            )
    return sorted(found, key=lambda item: item["word"])


def lemma_entries_for(word: str, limit: int = 3) -> list[dict]:
    """Original-language lemmas the KJV renders with this English word."""
    lex = _lexicon()
    codes = lex.get("kjv_word_index", {}).get(word.lower(), [])[:limit]
    out = []
    for code in codes:
        entry = lex.get("entries", {}).get(code)
        if entry:
            out.append({"strongs": code, **entry})
    return out


def lexical_context(user_text: str, evidence_texts: list[str], max_lemmas: int = 6) -> dict:
    """Assemble the research-layer payload for one analysis or chat turn.

    Drift words are collected from the retrieved KJV text (where the reader
    actually meets them) and from the user's own wording. Lemma lookups are
    driven by those drift words first, then by significant words the user
    used, so the data supplied is relevant rather than a dump.
    """
    corpus_text = "\n".join(evidence_texts)
    drift = archaic_words_in(corpus_text) + [
        item for item in archaic_words_in(user_text)
        if item["word"] not in {d["word"] for d in archaic_words_in(corpus_text)}
    ]

    candidates = [item["word"] for item in drift if " " not in item["word"]]
    for match in WORD_RE.finditer(user_text.lower()):
        word = match.group(0)
        if len(word) >= 5 and word not in candidates:
            candidates.append(word)

    lemmas: list[dict] = []
    for word in candidates:
        if len(lemmas) >= max_lemmas:
            break
        for entry in lemma_entries_for(word, limit=2):
            if len(lemmas) >= max_lemmas:
                break
            lemmas.append({"kjv_word": word, **entry})

    return {
        "rules": LEXICAL_RULES,
        "kjv_1611_drift": drift[:8],
        "original_language_lemmas": lemmas,
        "lexicon_source": _lexicon().get("source", "unavailable"),
    }
