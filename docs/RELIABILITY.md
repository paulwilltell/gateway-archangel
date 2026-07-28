# Reliability of the analysis

An analysis can reason well and the platform still be untrustworthy, because a
reader gets one run, not the distribution. This document records what has been
measured, including the attempts that failed.

Measure with `python scripts/consistency_check.py`. Agreement is counted per
*verse* rather than per claim, because the model may split a post into six
claims one time and eight the next; a reference is a stable identifier.

## Measurements

Probe: `evals/consistency_probe.txt` — five claims resting on Ephesians 4:32,
Hebrews 12:15, Lamentations 3:40, Galatians 6:5, Colossians 3:13. Four runs
each, `claude-opus-5`, identical conditions.

| Configuration | Verse agreement | Note |
|---|---|---|
| Baseline (2026-07-27) | 6/11 (55%) | Mixed two problems: which verses got classified at all, *and* what verdict they got. |
| + axis decision procedures | 3/10 (30%) | **Made it worse.** Reverted. |
| + coverage rule only (current) | 3/9 (33%) | Coverage now stable — every verse appears in every run. The 33% is pure verdict disagreement, and is the honest figure. |

The baseline 55% was flattering: verses that appeared in only one or two runs
were counted as unstable coverage, masking how often the *verdicts* disagree on
passages that do appear every time. With coverage controlled, roughly two
thirds of passages receive a different support level between identical runs.

Worst observed: **Romans 12:18 produced four different support levels across
four identical runs** (`direct_text`, `strong_inference`,
`disputed_interpretation`, `insufficient`), because the axes that decide it —
principally `claim_keeps_conditions` on "if it be possible" — are genuinely
ambiguous rather than merely underspecified.

## What did not work

**Adding decision procedures for each classification axis.** The hypothesis was
that ambiguity came from underspecification, so ~40 lines of explicit tests
were added ("decide speech_act from the grammatical form of this verse in its
sentence", and so on). Agreement fell from 55% to 30%, and a verse that had
been stable (Galatians 6:5) began spanning three levels. More instruction
created new judgment boundaries instead of removing old ones. Reverted, with
the measurement kept here so it is not retried blindly.

**What did work:** stating explicitly *which* passages to classify — the ones
the claim cites plus every supplied counterpassage, and nothing else. Coverage
went from varying (some verses classified in one run of four) to complete. This
is also a fairness property, not only a consistency one: a counterpassage
should not be skipped at random.

## The remaining problem, stated plainly

Prompting has been tried twice and made things worse both times. Classification
variance looks structural rather than persuadable: several axes encode real
interpretive judgment calls where a careful reader could legitimately answer
either way, and asking for the same answer every time does not make the
question less ambiguous.

Structural options, none yet implemented:

1. **Majority vote.** Classify N times, take the modal verdict per verse.
   Reliable and well understood; costs N times as much per post.
2. **Surface the instability instead of hiding it.** Analyze twice; where the
   two runs disagree on a passage, present the *weaker* verdict and mark it
   contested. Costs 2x, never overclaims, and is consistent with the rest of
   this platform's posture toward uncertainty — an unstable verdict is a fact
   about the evidence, and hiding it is the dishonest option.
3. **Reduce the axis space.** Fewer and less overlapping axes mean fewer
   judgment calls to disagree about, at the cost of expressiveness.

Option 2 is the recommended direction: it converts a defect into a disclosure,
which is what this platform does everywhere else.

## Option 2, implemented and measured

Implemented in `app/consensus.py`, `consensus_passes` (default 2). Where two
passes disagree about a passage, the **weaker** reading is presented and the
passage is marked contested — never the stronger, because a support level the
system cannot reproduce is not one it has earned.

Contested rate over two passes:

| Post | Passages settled | Contested | Claims lowered |
|---|---|---|---|
| `evals/consistency_probe.txt` | 5/8 | 38% | 2 of 5 |
| A real 8,266-character testimony | 12/16 | 25% | 2 of 8 |

**The feature is usable at these rates.** The earlier four-run agreement figure
(33%) was pessimistic about the two-pass case: with two passes, three quarters
of passages on a real post reproduce, and only a quarter of claims move. The
page is not reduced to "everything is contested".

Two further findings worth keeping:

- **Most disagreements are between adjacent levels** (`direct_text` versus
  `strong_inference`), not wild swings. The four-way split on Romans 12:18 is
  the tail, not the average.
- **Two different failures were being conflated.** A passage can be contested
  because the passes *read it differently* (`levels_disagree`) or because one
  pass *did not consider it at all* (`coverage_differs`). Reporting both as
  "contested" produced the nonsense line "contested — one reading seen", so the
  record and the UI now name which.

### After expanding the hermeneutic (counterpassage index v2, rules v2)

| Post | Passages settled | Contested | Claims lowered |
|---|---|---|---|
| `evals/consistency_probe.txt` | 7/10 | 30% | 0 of 5 |
| The 8,266-character testimony | 11/14 | 21% | 1 of 8 |

Expanding from 10 tensions to 35, and adding three genre-aware speech acts,
**did not cost reliability** — contested rates held or improved. Re-measuring
also surfaced a bug the test suite had not: `apply_consensus` lowered each
claim to its *weakest* contested passage, so a counterpassage could sink a
claim that a different passage genuinely carried. A claim's level is its
strongest passage; consensus may only lower a verdict, never raise one. Claims
lowered on the real testimony fell from 4 to 1 once fixed.

Remaining cost work, in order of leverage: the Batch API (50% off, and this
analysis is already asynchronous background work), classification on a smaller
model, and prompt caching on the stable prefix. Together these make two passes
cheaper than one Opus pass is today.
