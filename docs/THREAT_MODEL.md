# Threat model

## Spiritual and social threats

- A user presents abuse, revenge, racism, political ideology, or financial exploitation as God’s command.
- A charismatic user accumulates status and pressures others through “prophetic” certainty.
- Majority voting converts popularity into apparent doctrine.
- The AI labels people rather than claims.
- Users become dependent on the platform instead of real community, prayer, and accountable human care.
- Denominational assumptions are hidden behind the label “biblical.”

## Technical threats

- Prompt injection inside posts instructs the analyzer to ignore policy.
- Fabricated verse quotations enter training data.
- API keys leak into logs or frontend bundles.
- Private confessions are copied into datasets.
- Attackers enumerate accounts, scrape discussions, or trigger costly analyses.
- A compromised research connector supplies altered text.
- Deleted content remains in derived exports.

## Controls already represented

- Structured analysis, not freeform replies.
- Local corpus evidence.
- Exact citation locking that removes unapproved references and replaces altered quotations with the stored corpus text.
- Fixed safety result outside model control.
- Consent events and candidate review state.
- PII screening and audit events.
- Server-side API keys.
- Model-provider fallback.

## Controls still required before production

- Verified authentication, MFA for moderators, and role-based authorization.
- Rate limiting, CSRF protection, bot detection, and content-abuse workflows.
- Signed corpus manifests and connector integrity checks.
- Durable queue isolation and idempotency keys.
- Secret manager and redacted logs.
- Independent penetration test and privacy impact assessment.
- Appeals for analysis and moderator decisions.
- Child-safety policy and age gates.
