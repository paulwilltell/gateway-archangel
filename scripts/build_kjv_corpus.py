"""Convert the scrollmapper KJV JSON into the Gateway corpus seed format.

Input:  app/data/kjv_full_raw.json  (scrollmapper/bible_databases, public domain)
Output: app/data/kjv_full.json      (list of verse records in the app seed shape)

Book names are normalized to the arabic-numeral citation convention used by
the reference extractor ("1 Samuel", not "I Samuel"; "Revelation", not
"Revelation of John").
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "app" / "data" / "kjv_full_raw.json"
OUT = ROOT / "app" / "data" / "kjv_full.json"

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

MARKUP = re.compile(r"[{}<>\[\]]|\{[HG]\d+\}")


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
                # Square brackets in 1769 printings mark translator-supplied
                # (italicized) words; keep the words, drop the markers.
                text = verse["text"].replace("[", "").replace("]", "")
                text = re.sub(r"\s+", " ", text).strip()
                if MARKUP.search(text):
                    markup_hits += 1
                records.append(
                    {
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
                )

    if markup_hits:
        print(f"WARNING: {markup_hits} verses contain markup characters", file=sys.stderr)

    OUT.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(records)} verses across {len(data['books'])} books to {OUT.name}")
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
