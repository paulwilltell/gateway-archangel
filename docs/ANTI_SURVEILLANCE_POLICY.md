# Anti-Surveillance Policy

Gateway analyzes **content, never people**. The predictable failure mode of any
tool that evaluates discourse inside a hierarchical community is soft control:
leadership monitoring members' "spiritual posture" through flags and scores.
This platform is architecturally constrained against that use.

## Invariants (enforced by `tests/test_anti_surveillance.py`)

1. **Analyses attach to content only.** The `analyses` table has no user,
   author, or owner column. An analysis can be traced to a post or reply, but
   the schema provides no first-class path from a person to "all analyses of
   everything they ever wrote."
2. **Analysis payloads carry no author identity.** The structured record the
   API and UI display contains claims, evidence, flags, and limitations —
   never the author's ID or display name.
3. **No per-user rollup endpoints.** There is no route that aggregates
   alignment, flags, or confidence by user. None may be added.

## Forbidden features

These must not be built, regardless of who asks:

- A per-member "biblical alignment" score, ranking, or history view.
- Admin or moderator dashboards that list flagged users (flagged *content*
  queues are acceptable; the queue must be content-first, not person-first).
- Exports that join analyses to author identity.
- Notifications to anyone other than the author when their content receives a
  low-support or contradicted analysis.

## What is allowed

- Aggregate, anonymized community insight ("18,400 discussions on forgiveness
  frequently omit the Matthew 18 community-discipline context") — patterns
  over the corpus of discussion, never over an individual.
- The platform-owned safety layer (crisis resources shown to the author).
  Safety display is directed at the person in need, not reported upward.
