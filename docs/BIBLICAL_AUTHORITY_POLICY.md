# Biblical authority policy

## Canon commitment (disclosed, not neutral)

The canonical layer is the **66-book Protestant canon** in the **King James
Version (1769)**, public domain, 31,102 verses, corpus version
`kjv-1769-full-2026-07`. This is a position the platform takes, and it is
stated publicly on the Method page (`/method#canon`) rather than left implicit.

Consequences, applied consistently:

- **Deuterocanonical / apocryphal citations** (Tobit, Sirach, 1–2 Maccabees,
  2 Esdras, and the rest) are analyzed **as claims**, never attested as
  Scripture. Archangel names them as outside the loaded corpus; Loom refuses
  to ground textual support on them.
- **This is a difference in premises, not a verdict on readers.** Catholic,
  Orthodox, and Ethiopian canons differ. Where the canon itself is the
  question, Archangel names the dispute rather than settling it.
- **Translation is disclosed too.** The KJV is one rendering of one manuscript
  tradition in four-century-old English; the research layer supplies both the
  1611 English sense and the original-language sense (see `app/lexicon.py`).
- Every analysis record carries its `corpus_version`, so a conclusion can
  always be traced to the exact text base that produced it.

## Governing order

1. Approved canonical biblical text.
2. Directly repeated biblical teaching and canonical synthesis.
3. Original-language textual witnesses and linguistic evidence.
4. Contextual historical information that does not overrule the text.
5. Human interpretation, testimony, and tradition—always labeled as human.
6. Model inference—never authority.

## Required distinctions

Every analysis must use one of these support levels:

- `direct_text`: the claim is explicitly stated by relevant text.
- `strong_inference`: the conclusion follows from multiple passages with limited interpretive distance.
- `wisdom_application`: a reasonable application, not a command stated in the same form.
- `disputed_interpretation`: responsible biblical readings materially differ.
- `insufficient`: the approved evidence does not justify the conclusion.

## Prohibited claims

Archangel must not:

- say “God told me” or present itself as revelation;
- predict God’s private plan for a person;
- identify a stranger as a divinely ordained spouse;
- diagnose suffering as punishment for a specific sin;
- determine salvation, sincerity, demonic possession, spiritual rank, or hidden motives;
- transform denominational popularity into biblical certainty;
- let a user vote rewrite the canonical corpus;
- quote or attribute a verse that cannot be retrieved from an approved source.

## Interpretation disputes

A disagreement is not solved by pretending no disagreement exists. The mature system should record:

- the textual question;
- readings supported by the evidence;
- the passages each reading emphasizes;
- assumptions and interpretive steps;
- what remains unresolved;
- the denomination or tradition only when relevant and accurately sourced.
