# The Workbench

A personal Bible-study instrument, separate from Gateway on purpose.

**Gateway is a trust engine** — it refuses to claim more than the text
supports, because strangers rely on it. **The Workbench is a discovery
instrument** for one honest user who knows he is the validator. It *generates*
candidates — echoes, anomalies, connections — so a human can dig deeper than a
reader ever could unaided.

## The one rule

Every pattern it surfaces arrives with a **null test**. These methods never
fail to produce impressive-looking output; the null baseline is the only thing
that separates a real signal from an artifact you can talk yourself into.
Nothing is shown without "…and here is whether it survives chance."

There is a one-way door to Gateway: anything the Workbench makes you curious
about, take through Gateway's trust pipeline (Loom, the counterpassage index,
the published hermeneutic) to test whether it holds. **Generate divergent here;
validate convergent there.**

## Use

```bash
python -m workbench.study echo "Micah 6:8"          # verses that echo this one
python -m workbench.study echo "John 3:16" --top 15
python -m workbench.study novel                     # most lexically novel verses
python -m workbench.study novel --null              # the shuffle discipline, shown
```

### echo

For any verse, every place in the canon that echoes it, ranked by shared
vocabulary weighted so a rare shared word ("propitiation") counts far more than
a common one. Each result carries:

- a **z-score** — standard deviations above *this verse's* similarity to random
  verses, so a real echo is distinguished from a mundane overlap;
- the **shared words**, so you can see the basis of every link and filter the
  incidental matches yourself.

Verified: echoing Habakkuk 2:4 surfaces all three New Testament quotations of
it (Hebrews 10:38, Romans 1:17, Galatians 3:11) at the top of the list.

### novel

The most lexically novel verses — those introducing vocabulary rare in the
canon and unseen in their recent context. Book openers are excluded (an empty
context makes any opener look novel — an artifact, not a discovery), and the
score is IDF-weighted so a cluster of proper names does not automatically win.
`--null` shuffles verse order and re-ranks: if the top looks the same, the
score is tracking form, not meaning.

## Semantic layer (embeddings)

`semantic.py` finds where *meaning* recurs, not just words:

```bash
python -m workbench.study semantic "Micah 6:8"            # closest in meaning
python -m workbench.study semantic "Psalms 23:1" --bridges  # close meaning, NO shared words
python -m workbench.study outliers                        # least like the rest of Scripture
```

Verse embeddings come in tunable **variants** (`workbench/embed.py`), so
quality is *measured*, not guessed:

- `mini` — local all-MiniLM-L6-v2 (384-dim). Free, offline, no key. Fallback.
- `openai` — text-embedding-3-large (3072-dim) via API. **The default.**
- `openai-ctx` — same, but embedding each verse with its neighbours. Rejected.

### The bridge-tuning experiment

Bridges (close meaning, zero shared words) were weak with the small local
model — Psalm 23:1's top bridges sat at z≈2.7, barely above noise, and were
generic devotional filler. `workbench/compare_variants.py` ran a measured A/B/C:

| query | mini top-z | openai top-z | openai-ctx top-z |
|---|---|---|---|
| Psalms 23:1 | 2.7 | **5.9** | 7.4 |
| Ecclesiastes 1:9 | 3.8 | **7.1** | 7.4 |
| Matthew 7:12 | 2.9 | **4.9** | 7.1 |
| Proverbs 16:18 | 2.6 | **5.2** | 6.6 |
| John 1:1 | 2.5 | **4.8** | 6.4 |

`openai` roughly **doubled** the signal and, crucially, its bridges became
genuinely thematic — Psalm 23:1 now surfaces **Psalm 119:176** ("I have gone
astray like a lost sheep; seek thy servant"), a real shepherd-kinship bridge
across entirely different vocabulary that the small model missed completely;
Ecclesiastes 1:9 → 3:15 (cyclical time) climbed from z=3.8 to 7.1; Matthew 7:12
found the Luke 6 Sermon-on-the-Plain golden-rule parallel.

`openai-ctx` scored *higher still* — and was **rejected anyway**. Reading its
actual bridges showed they had degraded into *adjacent verses* (Psalm 23:1 →
23:2, 23:3): embedding a verse with its neighbours leaks context, so
neighbouring verses embed alike and pass the no-shared-words filter while being
trivially "connected." Higher numbers, worse tool. The z-score alone would have
picked the wrong variant; reading the verses caught the trap. That is the whole
discipline in one decision.

## What it is not

It is lexical, not semantic — it finds where *language* recurs, not where
*meaning* does, and it does not understand the text. It surfaces quotations and
strong verbal parallels extremely well, thematic cousins decently, and some
incidental overlap the transparency lets you discard. It points somewhere to
look. It never establishes that a connection is meaningful — that is your work,
and Gateway's.
