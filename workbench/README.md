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

## What it is not

It is lexical, not semantic — it finds where *language* recurs, not where
*meaning* does, and it does not understand the text. It surfaces quotations and
strong verbal parallels extremely well, thematic cousins decently, and some
incidental overlap the transparency lets you discard. It points somewhere to
look. It never establishes that a connection is meaningful — that is your work,
and Gateway's.
