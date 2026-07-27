from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from sqlalchemy import func, select, text as sql_text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import BibleVerse

BOOK_PATTERN = (
    r"(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
    r"1\s*Samuel|2\s*Samuel|1\s*Kings|2\s*Kings|1\s*Chronicles|2\s*Chronicles|"
    r"Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes|Song(?:\s+of\s+Solomon)?|"
    r"Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|"
    r"Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|"
    r"Romans|1\s*Corinthians|2\s*Corinthians|Galatians|Ephesians|Philippians|Colossians|"
    r"1\s*Thessalonians|2\s*Thessalonians|1\s*Timothy|2\s*Timothy|Titus|Philemon|"
    r"Hebrews|James|1\s*Peter|2\s*Peter|1\s*John|2\s*John|3\s*John|Jude|Revelation)"
)
REFERENCE_RE = re.compile(rf"\b({BOOK_PATTERN})\s+(\d{{1,3}}):(\d{{1,3}})(?:-(\d{{1,3}}))?\b", re.IGNORECASE)

BOOK_ALIASES = {
    "psalm": "Psalms",
    "psalms": "Psalms",
    "song": "Song of Solomon",
    "song of solomon": "Song of Solomon",
}

# Curated topical index. These pairings are an editorial artifact of the
# platform (documented on the Method page), not an output of the model. They
# bridge modern vocabulary ("anxiety") to KJV vocabulary ("take no thought")
# that lexical search alone cannot connect.
THEME_REFERENCES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("forgive", "forgiveness", "resentment"), ("Ephesians 4:32", "Matthew 6:14", "Romans 12:19")),
    (("anger", "argument", "conflict", "humiliation"), ("James 1:19", "Proverbs 15:1", "Matthew 18:15")),
    (("fear", "afraid", "anxiety", "anxious", "worry"), ("Philippians 4:6", "Isaiah 41:10", "2 Timothy 1:7")),
    (("money", "wealth", "rich", "greed"), ("Matthew 6:33", "1 Timothy 6:10", "Proverbs 11:4")),
    (("truth", "lie", "lying", "deceive"), ("Ephesians 4:25", "Proverbs 12:22", "John 8:32")),
    (("enemy", "revenge", "retaliate", "vengeance"), ("Matthew 5:44", "Romans 12:19", "Proverbs 20:22")),
    (("work", "job", "labor", "lazy"), ("Colossians 3:23", "Proverbs 14:23", "2 Thessalonians 3:10")),
    (("pride", "humble", "humility"), ("James 4:6", "Proverbs 16:18", "Philippians 2:3")),
    (("judge", "judgment", "condemn"), ("Matthew 7:1", "John 7:24", "Galatians 6:1")),
    (("love", "kindness", "compassion"), ("1 Corinthians 13:4", "John 13:34", "Micah 6:8")),
)

STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are as at be because been
    before being below between both but by can did do does doing down during each
    few for from further had has have having he her here hers herself him himself
    his how i if in into is it its itself just me more most my myself no nor not
    now of off on once only or other our ours ourselves out over own same she
    should so some such than that the their theirs them themselves then there
    these they this those through to too under until up very was we were what
    when where which while who whom why will with you your yours yourself
    yourselves would could also really think believe people something someone
    thing things want said says say
    """.split()
)

WORD_RE = re.compile(r"[A-Za-z][A-Za-z']{2,}")


def canonicalize_book(raw: str) -> str:
    compact = re.sub(r"\s+", " ", raw.strip())
    key = compact.lower()
    if key in BOOK_ALIASES:
        return BOOK_ALIASES[key]
    if key and key[0].isdigit():
        return f"{key[0]} {key[1:].strip().title()}"
    return compact.title()


def extract_references(text: str) -> list[str]:
    references: list[str] = []
    for match in REFERENCE_RE.finditer(text):
        book = canonicalize_book(match.group(1))
        chapter = int(match.group(2))
        verse_start = int(match.group(3))
        verse_end = match.group(4)
        if verse_end:
            for verse in range(verse_start, int(verse_end) + 1):
                references.append(f"{book} {chapter}:{verse}")
        else:
            references.append(f"{book} {chapter}:{verse_start}")
    return list(dict.fromkeys(references))


def infer_theme_references(text: str) -> list[str]:
    lowered = text.lower()
    refs: list[str] = []
    for keywords, references in THEME_REFERENCES:
        if any(keyword in lowered for keyword in keywords):
            refs.extend(references)
    return list(dict.fromkeys(refs))


def _content_terms(text: str, cap: int = 24) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for match in WORD_RE.finditer(text):
        term = match.group(0).lower().strip("'")
        if len(term) < 3 or term in STOPWORDS or term in seen:
            continue
        seen.add(term)
        terms.append(term)
        if len(terms) >= cap:
            break
    return terms


def search_corpus(db: Session, text: str, limit: int = 8) -> list[str]:
    """BM25-ranked full-text search over the whole canonical corpus.

    Returns verse references, best match first. Empty when full-text search is
    unavailable (non-SQLite backends) or nothing matches — never padded.
    """

    if db.get_bind().dialect.name != "sqlite":
        return []
    terms = _content_terms(text)
    if not terms:
        return []
    query = " OR ".join(f'"{term}"' for term in terms)
    try:
        rows = db.execute(
            sql_text(
                "SELECT reference FROM bible_fts WHERE bible_fts MATCH :q "
                "ORDER BY bm25(bible_fts) LIMIT :n"
            ),
            {"q": query, "n": limit},
        ).fetchall()
    except OperationalError:
        return []
    return [row[0] for row in rows]


def retrieve_evidence(db: Session, text: str, limit: int = 10) -> list[BibleVerse]:
    """Gather approved-corpus evidence for a piece of community content.

    Priority order: passages the author explicitly cited, then the curated
    topical index, then corpus-wide BM25 matches. When nothing is found the
    result is empty — absence of evidence is itself the finding, and the
    analyzer must report it rather than receive filler verses.
    """

    explicit = extract_references(text)
    ordered = list(explicit)
    for ref in infer_theme_references(text):
        if ref not in ordered:
            ordered.append(ref)
    if len(ordered) < limit:
        for ref in search_corpus(db, text, limit=limit):
            if ref not in ordered:
                ordered.append(ref)

    requested = ordered[:limit]
    if not requested:
        return []

    rows = db.scalars(select(BibleVerse).where(BibleVerse.reference.in_(requested))).all()
    by_ref = {row.reference: row for row in rows}
    return [by_ref[ref] for ref in requested if ref in by_ref]


def _build_fts_index(db: Session) -> None:
    if db.get_bind().dialect.name != "sqlite":
        return
    try:
        db.execute(
            sql_text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS bible_fts "
                "USING fts5(reference UNINDEXED, text)"
            )
        )
        indexed = db.execute(sql_text("SELECT count(*) FROM bible_fts")).scalar() or 0
        if not indexed:
            db.execute(
                sql_text(
                    "INSERT INTO bible_fts(reference, text) "
                    "SELECT reference, text FROM bible_verses"
                )
            )
    except OperationalError:
        # SQLite built without FTS5: retrieval degrades to explicit
        # references and the curated topical index.
        return


def seed_corpus(db: Session, seed_path: str, corpus_version: str) -> int:
    count = db.scalar(select(func.count()).select_from(BibleVerse)) or 0
    if count:
        _build_fts_index(db)
        return 0

    path = Path(seed_path)
    if not path.exists():
        return 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        {
            "id": str(uuid.uuid4()),
            "source_id": item.get("source_id", "kjv_local"),
            "reference": item["reference"],
            "book": item["book"],
            "chapter": item["chapter"],
            "verse": item["verse"],
            "text": item["text"],
            "language": item.get("language", "English"),
            "original_language": item.get("original_language"),
            "license": item.get("license", "Public Domain in the United States"),
            "corpus_version": corpus_version,
            "is_canonical_source": item.get("is_canonical_source", True),
        }
        for item in payload
    ]
    db.execute(BibleVerse.__table__.insert(), rows)
    db.flush()
    _build_fts_index(db)
    return len(rows)
