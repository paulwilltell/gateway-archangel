# API keys and biblical research sources

This file is the “whole 411” for the foundation’s external data layer. It distinguishes **where to obtain access**, **what the source is useful for**, and **whether its text may be cached or used in model training**.

## Secret-handling rule

1. Copy `.env.example` to `.env`.
2. Paste real keys only into `.env` locally or a production secret manager.
3. Never place keys in browser JavaScript, screenshots, Git commits, support tickets, or community posts.
4. Rotate a key immediately if exposed.
5. Use separate development and production keys where the provider supports it.

## 1. API.Bible

**Official documentation:** https://docs.api.bible/api-reference/getting-started/  
**Developer registration and app approval:** use the registration links from the official documentation.  
**Environment variable:** `API_BIBLE_API_KEY`  
**Header:** `api-key: YOUR_KEY`

Useful for:

- listing Bible translations authorized for your app;
- retrieving books, chapters, passages, verses, and metadata;
- accessing a KJV edition and other translations under the permissions attached to your key.

Current official documentation describes non-commercial access, rate limits, and plan-dependent translation access. The foundation therefore marks API.Bible as a **content provider**, not a blanket training source. Translation-specific copyright and API terms must be checked before caching, redistributing, embedding, fine-tuning, or continued pretraining.

Configured defaults:

```env
API_BIBLE_BASE_URL=https://rest.api.bible/v1
API_BIBLE_KJV_ID=de4e12af7f28f599-01
```

Do not assume the example Bible ID is authorized for every key. Call `/bibles` after approval and verify the returned edition and its rights.

## 2. Bible Brain / Digital Bible Platform v4

**Official API reference:** https://www.faithcomesbyhearing.com/bible-brain/api-reference  
**Official developer signup:** https://4.dbt.io/signup  
**Environment variable:** `BIBLE_BRAIN_API_KEY`

Useful for:

- multilingual Bible metadata;
- text filesets;
- audio and video Scripture;
- verse timing and media delivery;
- finding available content by language and Bible ID.

Bible Brain requires a developer key. Its license can restrict downloading, charging users for access, and where content may be retained. The foundation does not treat Bible Brain content as training-approved by default.

## 3. Sefaria

**Official developer documentation:** https://developers.sefaria.org/docs/welcome  
**Environment variable:** none currently required by this foundation  
**Base URL:** `SEFARIA_BASE_URL=https://www.sefaria.org/api`

Useful for:

- structured Hebrew Bible references;
- Hebrew text and versions;
- links among Jewish texts;
- textual structure and metadata;
- research into how passages are organized and connected.

Sefaria is a research library. Text versions and datasets can carry different licenses. Preserve the exact version, language, attribution, and dataset terms. Rabbinic commentary and community interpretation must remain visibly distinct from the biblical text and cannot silently become canonical authority.

## 4. Open Scriptures Hebrew Bible (OSHB)

**Repository:** https://github.com/openscriptures/morphhb

Useful for:

- Westminster Leningrad Codex Hebrew text;
- lemmas;
- morphology;
- word-level identifiers;
- mapping Hebrew forms to grammatical analysis.

The OSHB project states that the WLC text is public domain and that lemma/morphology data are licensed under CC BY 4.0. Keep required attribution and preserve the release/commit hash in the corpus registry.

Recommended local layout:

```text
corpora/oshb/<release-or-commit>/
  source/
  normalized/
  LICENSE.md
  MANIFEST.json
```

## 5. SBL Greek New Testament

**Official site:** https://www.sblgnt.com/  
**Source download:** https://www.sblgnt.com/download/  
**Repository:** https://github.com/LogosBible/SBLGNT

Useful for:

- a Unicode Greek New Testament text;
- a freely downloadable critical edition;
- New Testament linguistic and textual research.

The SBLGNT is CC BY 4.0. Store the attribution and version metadata with every imported corpus build.

## 6. Optional OpenAI development adapter

**Official API quickstart:** https://platform.openai.com/docs/quickstart  
**Environment variable:** `OPENAI_API_KEY`

The foundation uses the Responses API adapter only when:

```env
ARCHANGEL_ANALYZER=openai
OPENAI_API_KEY=...
ARCHANGEL_MODEL=<a model available to your account>
```

This is a **development reasoning adapter**, not a Bible-only-trained model. Do not describe it otherwise. It receives only the community content, platform safety result, and approved retrieved evidence; its output must validate against the Archangel JSON contract. Provider failure falls back to the deterministic analyzer.

Before sending real community disclosures to any hosted model, review the provider’s current data retention, abuse monitoring, regional processing, and enterprise privacy controls.

## 7. Local/open-weight model path

Configure an OpenAI-compatible local endpoint:

```env
ARCHANGEL_ANALYZER=local_openai_compatible
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=<your-model>
LOCAL_LLM_API_KEY=local-development
```

A local model gives you control over inference privacy. It still does not become “Bible-only” merely because it runs locally. To satisfy the literal dataset requirement, maintain a signed dataset manifest for every pretraining, continued-pretraining, fine-tuning, preference, and evaluation example.

## Required provenance fields

Every corpus item should eventually carry:

```json
{
  "source_id": "oshb",
  "work": "Open Scriptures Hebrew Bible",
  "version": "2.2-or-commit-hash",
  "language": "he",
  "reference": "Genesis 1:1",
  "license": "CC BY 4.0 / WLC public-domain text",
  "canonical_role": "original_language_textual_witness",
  "retrieved_at": "ISO-8601 timestamp",
  "checksum": "sha256:...",
  "transformations": ["unicode-normalization:NFC"],
  "training_permission": "approved-by-policy-id"
}
```

## Sources intentionally not scraped

Do not scrape commercial Bible websites, commentary platforms, YouVersion pages, Bible Hub, Logos content, or copyrighted study Bibles merely because text is visible in a browser. Visibility is not permission to reproduce, cache, embed, or train on the material. Use an official API, licensed export, public-domain source, or written agreement.
