"""Build the synchronic lexicon from public-domain Strong's dictionaries.

Input:  app/data/strongs_{hebrew,greek}_raw.js  (openscriptures/strongs, PD)
Output: app/data/lexicon.json

Two deliberate design decisions, both enforcing the synchronic rule:

1. **The `derivation` field is dropped.** Strong's "from G25 (ἀγαπάω)" is
   root-etymology — exactly the data that produces the etymological fallacy
   ("dunamis comes from the root of dynamite"). Meaning comes from usage at
   the time of writing, not from ancestry, so the ancestry is not loaded.

2. **A reverse index from KJV English word → lemma entries** is built from
   each entry's `kjv_def` (the words the KJV actually uses to render that
   lemma). This is usage-based: it answers "when the KJV prints *charity*,
   which underlying word is it rendering?" rather than guessing from roots.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data"
OUT = DATA / "lexicon.json"

# Words too generic to be useful as reverse-index keys.
STOP = {
    "a", "an", "the", "and", "or", "of", "to", "in", "be", "is", "was", "it",
    "that", "this", "with", "for", "as", "by", "on", "at", "from", "which",
    "who", "not", "but", "have", "had", "do", "did", "one", "up", "out",
    "etc", "also", "any", "all", "make", "made", "self", "him", "her", "them",
    "thing", "things", "man", "men", "own", "same", "such", "unto", "upon",
    "would", "shall", "will", "let", "may", "can", "more", "most", "very",
}


def parse_dictionary(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    start = text.index("{", text.index("="))
    end = text.rindex("}")
    return json.loads(text[start : end + 1])


def kjv_words(kjv_def: str) -> list[str]:
    """Extract the KJV rendering words from a `kjv_def` string."""
    cleaned = re.sub(r"\([^)]*\)", " ", kjv_def or "")
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", cleaned)
    out = []
    for word in words:
        w = word.lower().strip("-'")
        if len(w) >= 3 and w not in STOP and w not in out:
            out.append(w)
    return out


def main() -> int:
    entries: dict[str, dict] = {}
    reverse: dict[str, list[str]] = {}

    for lang, filename, era in (
        ("Hebrew", "strongs_hebrew_raw.js", "Biblical Hebrew (c. 1400-400 BC)"),
        ("Greek", "strongs_greek_raw.js", "Koine Greek (1st century AD)"),
    ):
        path = DATA / filename
        if not path.exists():
            print(f"missing {path.name}", file=sys.stderr)
            return 1
        for code, item in parse_dictionary(path).items():
            definition = (item.get("strongs_def") or "").strip()
            kjv = (item.get("kjv_def") or "").strip()
            if not definition and not kjv:
                continue
            entries[code] = {
                "lemma": item.get("lemma", ""),
                "translit": item.get("translit", ""),
                "language": lang,
                "era": era,
                "sense": definition,
                "kjv_renderings": kjv,
                # NOTE: `derivation` intentionally omitted — see module docstring.
            }
            for word in kjv_words(kjv):
                bucket = reverse.setdefault(word, [])
                if len(bucket) < 6 and code not in bucket:
                    bucket.append(code)

    payload = {
        "source": "Strong's Hebrew and Greek Dictionaries (public domain), via openscriptures/strongs",
        "note": "Synchronic senses only; root-derivation data deliberately excluded.",
        "entries": entries,
        "kjv_word_index": reverse,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(entries)} lemma entries and {len(reverse)} KJV word keys to {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
