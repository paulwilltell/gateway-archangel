# Gateway + Archangel

**Gateway** is the platform: a human Christian discussion network.  
**Archangel** is the silent analysis layer beneath it.

People publish thoughts, testimony, interpretations, and replies. Archangel does **not** enter the thread as a chatbot. It stores and displays a structured record of:

- the actual claims being made;
- direct biblical text versus inference or application;
- relevant approved Scripture evidence;
- context and reasoning risks;
- uncertainty and interpretive limits;
- safety referrals that cannot be overridden by theology;
- whether public, consented material may proceed to human theological review for a future training set.

## What is already built

- A polished web interface for posts and human replies.
- SQLite for local use; PostgreSQL-ready SQLAlchemy models.
- The **complete KJV (1769) corpus — all 31,102 verses across 66 books**, public domain, with source and license metadata (`scripts/build_kjv_corpus.py` rebuilds it from the raw source).
- Three-stage evidence retrieval: explicit citation extraction, a curated topical index, and **BM25 full-text search (SQLite FTS5) over the whole corpus**. When nothing matches, retrieval returns nothing — absence of evidence is reported, never papered over with filler verses.
- A hard evidence lock: model citations outside retrieval are removed, and quoted wording is replaced with the exact corpus record.
- A deterministic analyzer that runs with **no API key**.
- Optional Claude (Anthropic API, recommended hosted analyzer), OpenAI Responses API, and local OpenAI-compatible model adapters.
- A **conversational surface** (`/archangel`) that Gateway itself never persists: no conversation table exists, history lives in the visitor's browser. Stated precisely — the message still reaches the hosted model provider under its retention terms, and the UI says so rather than promising more.
- **Deterministic provenance verification by Loom** (`app/loom_bridge.py`): a truth-maintenance engine checks that every claim's citations are attested in the canonical corpus and withdraws textual support that does not derive, with an inspectable trace. This verifies that citations are *real*; it does **not** verify that a passage entails the claim — that judgment remains the model's and is labeled as such in the UI.
- A **research layer** (`app/lexicon.py`): 1611 English drift glossary plus 14,197 public-domain Strong's lemmas, under a strict synchronic rule — the sense a word carried *when written*, never root-etymology (Strong's derivation data is deliberately not loaded).
- A **theological eval harness** (`python scripts/run_evals.py`): a golden set of hard cases — fabricated verses, apocryphal citations, prosperity claims, crisis content, policy edges — run free against the deterministic analyzer or live against Claude.
- **Anonymous posting** with assigned pen names, and no user accounts of any kind.
- An **anti-surveillance policy enforced by tests**: analyses attach to content, never to people; no per-user rollups exist or may be added (`docs/ANTI_SURVEILLANCE_POLICY.md`).
- A platform-owned 911 / 988 / Poison Control safety layer.
- Structured analysis records rather than AI comments.
- Explicit, separate research consent on every post and reply.
- PII detection and a training gate that excludes unsafe, private, unconsented, non-aligned, or low-confidence content.
- A mandatory `pending_theological_review` state. Nothing auto-trains.
- API.Bible, Bible Brain, and Sefaria connector foundations.
- Source registry, audit events, tests, corpus import, candidate review, and approved-export scripts.

## Run locally

```bash
cd gateway-archangel
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --no-access-log   # the flag matters: see below
```

Open `http://127.0.0.1:8000`. API documentation is at `/docs`.

**Always run with `--no-access-log`.** Uvicorn's access log records every
visitor's IP address. Gateway deliberately has no accounts and stores no
conversations so that no list of who reads or writes here exists; the access
log would rebuild that list in stdout. The Dockerfile and Makefile already
pass the flag.

### Checks

```bash
pytest                                     # 39 tests
python scripts/run_evals.py                # 20-case theological golden set (free)
python scripts/run_evals.py --analyzer anthropic   # same set against Claude (costs money)
python scripts/validate_corpus.py          # corpus integrity
python scripts/backup_db.py                # safe online backup, keeps 30
```

Rebuilding the data layers (only needed if you change sources):

```bash
python scripts/build_kjv_corpus.py   # needs app/data/kjv_full_raw.json
python scripts/build_lexicon.py      # needs app/data/strongs_*_raw.js
```

The default `ARCHANGEL_ANALYZER=heuristic` is deliberate. The app works without sending spiritual disclosures to a hosted model.

## API keys

Open `API_KEYS.env.example` (or `.env.example`) and `docs/API_KEYS_AND_RESEARCH.md`. Real secrets belong in `.env`, a deployment secret manager, or an encrypted vault—never Git.

## The authority model

1. **Canonical layer:** approved biblical texts, versioned and provenance-tracked.
2. **Research layer:** Hebrew/Greek textual witnesses, lexicons, morphology, manuscript data, and historical context. These illuminate the text; they do not silently become new Scripture.
3. **Community layer:** human interpretations and lived experience. This trains understanding of human questions only after explicit consent and review; it never becomes authority by popularity.
4. **Analysis layer:** produces an inspectable classification. It cannot claim private revelation, judge salvation, or speak as God.

## A crucial technical truth

A hosted general-purpose LLM has already learned from broad human data. Retrieval constraints can limit what evidence it is permitted to cite, but they do not transform its pretrained weights into a Bible-only model. Literal compliance requires a separately trained or continued-pretrained model using only an approved, licensed, provenance-tracked corpus. See `docs/MODEL_LIMITATIONS.md`.

## Before public deployment

This repository is a foundation, not a finished public social network. Add verified authentication, account recovery, authorization, production migrations, rate limiting, abuse reporting, moderator tooling, encrypted backups, observability, deletion lineage, accessibility testing, jurisdiction-specific privacy review, child-safety controls, and independent security assessment before inviting the public.

## Project map

```text
app/
  analysis/       structured contract, retrieval, prompts, providers, engine
  integrations/   API.Bible, Bible Brain, Sefaria
  routers/        web and JSON API routes
  templates/      Gateway community UI
  data/           KJV seed and source registry
scripts/          corpus import, review, validation, approved export
docs/             authority, safety, privacy, keys, architecture, threat model
tests/            safety, retrieval, API, and training-gate tests
```
