"""Convert the scrollmapper KJV JSON into the Gateway corpus seed format.

Input:  app/data/kjv_full_raw.json  (scrollmapper/bible_databases, public domain)
Output: app/data/kjv_full.json      (list of verse records in the app seed shape)

Book names are normalized to the arabic-numeral citation convention used by
the reference extractor ("1 Samuel", not "I Samuel"; "Revelation", not
"Revelation of John").

Square brackets in 1769 printings mark words the translators supplied for
English readability — words with no counterpart in the source language. That
distinction is real scholarly information, so the brackets are removed from
the display text but their spans are **preserved as metadata**
(`supplied_word_spans`) rather than discarded. A reader sees clean text; a
word study can still tell explicit source wording from supplied English.

A build manifest (`kjv_full.manifest.json`) records the source checksum,
output checksum, verse count, and build date, so "KJV 1769" is reproducible
rather than merely asserted.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "app" / "data" / "kjv_full_raw.json"
OUT = ROOT / "app" / "data" / "kjv_full.json"
MANIFEST = ROOT / "app" / "data" / "kjv_full.manifest.json"
CORPUS_VERSION = "kjv-1769-full-2026-07"

BOOK_RENAMES = {
    "I Samuel": "1 Samuel",
    "II Samuel": "2 Samuel",
    "I Kings": "1 Kings",
    "II Kings": "2 Kings",
    "I Chronicles": "1 Chronicles",
    "II Chronicles": "2 Chronicles",
    "I Corinthians": "1 Corinthians",
    "II Corinthians": "2 Corinthians",
    "I Thessalonians": "1 Thessalonians",
    "II Thessalonians": "2 Thessalonians",
    "I Timothy": "1 Timothy",
    "II Timothy": "2 Timothy",
    "I Peter": "1 Peter",
    "II Peter": "2 Peter",
    "I John": "1 John",
    "II John": "2 John",
    "III John": "3 John",
    "Revelation of John": "Revelation",
}

MARKUP = re.compile(r"[{}<>]|\{[HG]\d+\}")


def strip_supplied_markers(raw: str) -> tuple[str, list[dict]]:
    """Remove [translator-supplied] brackets, returning clean text plus the
    character spans those words occupy in it."""
    out: list[str] = []
    spans: list[dict] = []
    depth_start: int | None = None
    for char in raw:
        if char == "[":
            depth_start = len(out)
            continue
        if char == "]":
            if depth_start is not None:
                spans.append({"start": depth_start, "end": len(out)})
                depth_start = None
            continue
        out.append(char)
    text = "".join(out)
    # Collapse whitespace, adjusting recorded spans by what was removed before them.
    collapsed: list[str] = []
    shift_at: list[tuple[int, int]] = []  # (original_index, cumulative_removed)
    removed = 0
    previous_space = False
    for index, char in enumerate(text):
        is_space = char.isspace()
        if is_space and (previous_space or not collapsed):
            removed += 1
            shift_at.append((index, removed))
            continue
        collapsed.append(" " if is_space else char)
        previous_space = is_space
        shift_at.append((index, removed))
    final = "".join(collapsed).rstrip()

    def adjust(position: int) -> int:
        shift = 0
        for original_index, cumulative in shift_at:
            if original_index >= position:
                break
            shift = cumulative
        return max(0, min(len(final), position - shift))

    return final, [{"start": adjust(s["start"]), "end": adjust(s["end"])} for s in spans]


def main() -> int:
    data = json.loads(RAW.read_text(encoding="utf-8"))
    records: list[dict] = []
    markup_hits = 0

    for book in data["books"]:
        name = BOOK_RENAMES.get(book["name"], book["name"])
        for chapter in book["chapters"]:
            ch = int(chapter["chapter"])
            for verse in chapter["verses"]:
                v = int(verse["verse"])
                text, supplied = strip_supplied_markers(verse["text"])
                if MARKUP.search(text):
                    markup_hits += 1
                record = {
                    "source_id": "kjv_1769",
                    "reference": f"{name} {ch}:{v}",
                    "book": name,
                    "chapter": ch,
                    "verse": v,
                    "text": text,
                    "language": "English",
                    "original_language": "Hebrew" if name in OT_BOOKS else "Greek",
                    "license": "Public Domain in the United States",
                    "is_canonical_source": True,
                }
                if supplied:
                    record["supplied_word_spans"] = supplied
                records.append(record)

    if markup_hits:
        print(f"WARNING: {markup_hits} verses contain markup characters", file=sys.stderr)

    payload = json.dumps(records, ensure_ascii=False)
    OUT.write_text(payload, encoding="utf-8")

    manifest = {
        "corpus_version": CORPUS_VERSION,
        "translation": "King James Version (1769)",
        "license": "Public Domain in the United States",
        "source": "https://github.com/scrollmapper/bible_databases",
        "source_file": RAW.name,
        "source_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "verse_count": len(records),
        "book_count": len(data["books"]),
        "verses_with_supplied_words": sum(1 for r in records if "supplied_word_spans" in r),
        "builder": "scripts/build_kjv_corpus.py",
        "built_on": date.today().isoformat(),
        "notes": (
            "Translator-supplied words (square brackets in 1769 printings) are removed from "
            "display text and recorded as character spans in supplied_word_spans."
        ),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} verses across {len(data['books'])} books to {OUT.name}")
    print(f"  {manifest['verses_with_supplied_words']} verses carry supplied-word spans")
    print(f"  manifest: {MANIFEST.name} (output sha256 {manifest['output_sha256'][:16]}...)")
    return 0


OT_BOOKS = {
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua",
    "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
    "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
    "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah",
    "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai",
    "Zechariah", "Malachi",
}

if __name__ == "__main__":
    raise SystemExit(main())
