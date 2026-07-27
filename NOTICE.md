# Third-party content

The Gateway source code is MIT licensed (see `LICENSE`). The data and vendored
code bundled in this repository carry their own provenance:

| Item | Source | Terms |
|---|---|---|
| `app/data/kjv_full.json` | King James Version (1769), built from the [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases) dataset | Public domain in the United States |
| `app/data/lexicon.json` | Strong's Hebrew and Greek Dictionaries, built from [openscriptures/strongs](https://github.com/openscriptures/strongs) | Public domain |
| `app/data/kjv_glossary.json` | Curated 1611 English drift glossary, written for this project | MIT, with the rest of the source |
| `app/vendor/loom_engine.py` | Loom v2.2, a deterministic reasoning engine by the same author, vendored as a pinned copy | See `app/vendor/README.md` |

Two notes on how the data was prepared, because both are deliberate and both
affect what the software will tell you:

- **Strong's root-derivation fields are excluded.** Etymology of ancestry
  ("this word comes from that root") is the raw material of the etymological
  fallacy, so it is never loaded. Only synchronic sense data — what a word
  meant when the text was written — reaches the model. See
  `scripts/build_lexicon.py`.
- **The canonical layer is the 66-book Protestant canon.** That is a
  commitment, not a neutral default, and its consequences are documented in
  `docs/BIBLICAL_AUTHORITY_POLICY.md` and stated publicly at `/method#canon`.
