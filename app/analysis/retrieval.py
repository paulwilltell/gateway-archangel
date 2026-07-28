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

THEME_INDEX_VERSION = "theme-index-v1-2026-07"

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

# Curated counterpassage index — passages the tradition has long held in
# tension. Supplying these alongside a retrieved verse is what separates
# analysis from proof-texting: a claim resting on one side of a tension must
# be told the other side exists. This mapping is an EDITORIAL artifact of the
# platform (versioned below, shown on the Method page), not a discovery in the
# text, and listing two passages together asserts tension, never that one
# defeats the other.
COUNTERPASSAGE_VERSION = "counterpassage-index-v2-2026-07"
COUNTERPASSAGES: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    (
        ("Ephesians 2:8", "Ephesians 2:9", "Romans 3:28", "Galatians 2:16"),
        ("James 2:17", "James 2:24", "Matthew 7:21"),
        "Faith and works: justification apart from works, held against faith without works being dead.",
    ),
    (
        ("Malachi 3:10", "Luke 6:38", "Proverbs 3:9"),
        ("1 Timothy 6:9", "1 Timothy 6:10", "Matthew 6:19", "Luke 12:15", "Job 1:21"),
        "Giving and provision, held against warnings that wealth is not a measure of favor.",
    ),
    (
        ("Matthew 6:14", "Ephesians 4:32", "Colossians 3:13"),
        ("Luke 17:3", "Matthew 18:15", "Proverbs 22:3", "Romans 12:18"),
        "Forgiveness commanded, held against rebuke, conditions, and prudence about repeated harm.",
    ),
    (
        ("Romans 13:1", "1 Peter 2:13"),
        ("Acts 5:29", "Daniel 3:18", "Exodus 1:17"),
        "Submission to governing authority, held against obedience to God over men.",
    ),
    (
        ("Acts 2:17", "Joel 2:28", "Numbers 12:6"),
        ("Deuteronomy 13:1", "Deuteronomy 13:3", "Jeremiah 23:16", "1 John 4:1", "1 Thessalonians 5:21"),
        "Dreams and visions as divine communication, held against commands to test every such claim.",
    ),
    (
        ("Romans 12:19", "Matthew 5:39", "Matthew 5:44"),
        ("Romans 13:4", "Psalms 82:3", "Proverbs 31:8"),
        "Personal non-retaliation, held against the pursuit of justice and defense of the wronged.",
    ),
    (
        ("Mark 16:16", "Acts 2:38", "1 Peter 3:21"),
        ("Luke 23:43", "Romans 10:9", "Ephesians 2:8"),
        "Baptism language, held against passages read as salvation apart from it. Historically disputed.",
    ),
    (
        ("1 Corinthians 14:34", "1 Timothy 2:12"),
        ("Galatians 3:28", "Acts 18:26", "Romans 16:1", "Judges 4:4", "Joel 2:28"),
        "Restriction passages, held against women teaching, leading, and prophesying. Historically disputed.",
    ),
    (
        ("Proverbs 22:6", "Proverbs 13:24"),
        ("Ezekiel 18:20", "Ephesians 6:4"),
        "Proverbs as general wisdom, held against passages denying they are guarantees.",
    ),
    (
        ("John 14:14", "Matthew 21:22", "Mark 11:24"),
        ("1 John 5:14", "James 4:3", "2 Corinthians 12:8", "2 Corinthians 12:9"),
        "Promises about prayer, held against the will-of-God condition and unanswered petition.",
    ),
    (
        ("Romans 9:16", "Romans 9:18", "Ephesians 1:4", "Ephesians 1:5"),
        ("1 Timothy 2:4", "2 Peter 3:9", "Revelation 22:17", "Joshua 24:15"),
        "Election and God's choosing, held against passages on God's desire that all be saved. Historically disputed.",
    ),
    (
        ("John 10:28", "John 10:29", "Romans 8:38", "Romans 8:39"),
        ("Hebrews 6:4", "Hebrews 6:6", "Hebrews 10:26", "2 Peter 2:20"),
        "Passages read as the security of the believer, held against warnings about falling away. Historically disputed.",
    ),
    (
        ("Ephesians 2:8", "Ephesians 2:9", "Titus 3:5"),
        ("Philippians 2:12", "2 Corinthians 13:5", "1 Corinthians 9:27"),
        "Salvation not of works, held against working out salvation and examining oneself.",
    ),
    (
        ("Colossians 2:16", "Romans 14:5", "Galatians 4:10"),
        ("Exodus 20:8", "Exodus 20:9", "Exodus 20:10", "Isaiah 58:13"),
        "Passages read as freedom regarding days, held against the Sabbath command. Historically disputed.",
    ),
    (
        ("Mark 7:19", "Acts 10:15", "1 Timothy 4:4"),
        ("Leviticus 11:7", "Leviticus 11:8", "Acts 15:29"),
        "Passages read as declaring foods clean, held against dietary law and the Jerusalem decree.",
    ),
    (
        ("Matthew 19:9", "Matthew 5:32"),
        ("Mark 10:11", "Mark 10:12", "Luke 16:18", "Malachi 2:16", "1 Corinthians 7:15"),
        "The exception clause on divorce, held against the absolute form and the desertion case. Historically disputed.",
    ),
    (
        ("Isaiah 53:5", "James 5:15", "Matthew 8:17"),
        ("2 Corinthians 12:8", "2 Corinthians 12:9", "2 Timothy 4:20", "Philippians 2:27", "1 Timothy 5:23"),
        "Passages read as promising healing, held against faithful people left unhealed.",
    ),
    (
        ("Matthew 5:34", "James 5:12"),
        ("Numbers 30:2", "Hebrews 6:16", "Deuteronomy 6:13"),
        "The command not to swear, held against oaths taken and even required elsewhere.",
    ),
    (
        ("Proverbs 20:1", "Proverbs 23:31", "Ephesians 5:18"),
        ("1 Timothy 5:23", "Psalms 104:15", "John 2:10"),
        "Warnings about wine, held against its ordinary and even commended use.",
    ),
    (
        ("Ephesians 6:5", "Colossians 3:22", "1 Peter 2:18"),
        ("Galatians 3:28", "Philemon 1:16", "Exodus 21:16", "1 Timothy 1:10"),
        "Household codes addressed to servants, held against passages undercutting the institution.",
    ),
    (
        ("Psalms 137:9", "Psalms 69:24", "Psalms 109:9"),
        ("Matthew 5:44", "Romans 12:14", "Luke 23:34"),
        "Imprecatory psalms, held against the command to bless and not curse.",
    ),
    (
        ("1 Corinthians 11:5", "1 Corinthians 11:6"),
        ("Galatians 3:28", "1 Corinthians 11:16"),
        "Head-covering instruction, held against there being no such custom in the churches. Historically disputed.",
    ),
    (
        ("Ephesians 5:22", "Colossians 3:18", "1 Peter 3:1"),
        ("Ephesians 5:21", "Ephesians 5:25", "1 Corinthians 7:4"),
        "Instruction to wives, held against mutual submission and the charge to husbands.",
    ),
    (
        ("Matthew 7:1", "Romans 14:4", "James 4:12"),
        ("1 Corinthians 5:12", "John 7:24", "1 Corinthians 6:2", "Galatians 6:1"),
        "Judge not, held against commanded discernment and judgment within the church.",
    ),
    (
        ("Matthew 19:21", "Luke 14:33", "Acts 2:45"),
        ("1 Timothy 5:8", "2 Thessalonians 3:10", "Proverbs 13:22", "Job 42:12"),
        "Calls to give everything away, held against providing for one's household and lawful provision.",
    ),
    (
        ("Matthew 5:39", "Matthew 26:52"),
        ("Luke 22:36", "Romans 13:4", "Nehemiah 4:14"),
        "Non-resistance, held against defence and the magistrate's sword. Historically disputed.",
    ),
    (
        ("Matthew 6:25", "Matthew 6:34", "Philippians 4:6"),
        ("Proverbs 6:6", "Proverbs 6:8", "Luke 14:28", "1 Timothy 5:8"),
        "Take no thought for tomorrow, held against commended foresight and planning.",
    ),
    (
        ("1 Corinthians 14:39", "1 Corinthians 14:5"),
        ("1 Corinthians 14:28", "1 Corinthians 14:40", "1 Corinthians 13:8"),
        "Forbid not to speak with tongues, held against the ordering restrictions. Historically disputed.",
    ),
    (
        ("1 John 5:13", "Romans 8:16"),
        ("2 Corinthians 13:5", "Matthew 7:22", "Matthew 7:23", "2 Peter 1:10"),
        "Assurance of salvation, held against the command to examine oneself.",
    ),
    (
        ("Exodus 20:16", "Proverbs 12:22", "Colossians 3:9"),
        ("Exodus 1:19", "Exodus 1:20", "Joshua 2:4", "Hebrews 11:31"),
        "The prohibition of lying, held against deception commended in Scripture's own narratives.",
    ),
    (
        ("Matthew 24:36", "1 Thessalonians 5:2", "Matthew 24:44"),
        ("Matthew 24:6", "2 Thessalonians 2:3", "Luke 21:20"),
        "The unknown hour and sudden coming, held against signs preceding it. Historically disputed.",
    ),
    (
        ("Matthew 6:16", "Matthew 6:17", "Matthew 6:18"),
        ("Joel 2:15", "Acts 13:2", "Acts 13:3"),
        "Fasting in secret, held against called corporate fasts.",
    ),
    (
        ("James 5:16", "1 John 1:9"),
        ("1 Timothy 2:5", "Hebrews 4:16"),
        "Confession to one another, held against the one mediator and direct access. Historically disputed.",
    ),
    (
        ("Genesis 1:28", "Psalms 127:3", "Psalms 127:5"),
        ("1 Corinthians 7:8", "1 Corinthians 7:32", "Matthew 19:12"),
        "The blessing of children and family, held against the commendation of singleness.",
    ),
    (
        ("2 Timothy 3:16", "Psalms 119:105"),
        ("2 Peter 3:16", "John 16:13", "Acts 8:31"),
        "The sufficiency and clarity of Scripture, held against passages acknowledging hard texts and the need for teaching.",
    ),
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


def context_window(db: Session, verse: BibleVerse, before: int = 2, after: int = 2) -> list[dict]:
    """Neighbouring verses around a retrieved passage.

    Verse divisions were imposed on these documents centuries after they were
    written, so an exactly-quoted verse can still be badly misapplied. Every
    retrieved passage therefore travels with the sentences around it.
    """
    low = max(1, verse.verse - before)
    rows = db.scalars(
        select(BibleVerse)
        .where(
            BibleVerse.book == verse.book,
            BibleVerse.chapter == verse.chapter,
            BibleVerse.verse >= low,
            BibleVerse.verse <= verse.verse + after,
        )
        .order_by(BibleVerse.verse)
    ).all()
    return [
        {"reference": row.reference, "text": row.text, "is_cited_verse": row.reference == verse.reference}
        for row in rows
    ]


def counterpassages_for(db: Session, references: list[str]) -> list[dict]:
    """Passages standing in tension with what was retrieved.

    A claim resting on one side of a long-standing tension must be shown the
    other side. Returns the actual corpus text, so the model reasons over
    verses rather than over a summary of them.
    """
    retrieved = set(references)
    out: list[dict] = []
    for side_a, side_b, description in COUNTERPASSAGES:
        for near, far in ((side_a, side_b), (side_b, side_a)):
            if not retrieved & set(near):
                continue
            rows = db.scalars(select(BibleVerse).where(BibleVerse.reference.in_(far))).all()
            if not rows:
                continue
            out.append(
                {
                    "tension": description,
                    "triggered_by": sorted(retrieved & set(near)),
                    "passages": [{"reference": r.reference, "text": r.text} for r in rows],
                }
            )
            break
    return out[:4]


def retrieval_context(db: Session, evidence_rows: list[BibleVerse]) -> dict:
    """The full contextual payload: each cited verse with its surrounding
    verses, plus counterpassages standing in tension with the set."""
    references = [row.reference for row in evidence_rows]
    return {
        "note": (
            "Verse divisions are a later editorial imposition; read each cited verse inside "
            "the surrounding context supplied here. Counterpassages are passages the Christian "
            "tradition has long held in tension with the retrieved ones — they are supplied so "
            "a conclusion is not drawn from one side alone, not because they defeat it. The "
            "counterpassage index is an editorial artifact of this platform, not a discovery "
            "in the text."
        ),
        "counterpassage_index_version": COUNTERPASSAGE_VERSION,
        "context_windows": [
            {"cited": row.reference, "surrounding": context_window(db, row)}
            for row in evidence_rows[:6]
        ],
        "counterpassages": counterpassages_for(db, references),
    }


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
