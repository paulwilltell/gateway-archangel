# Content Policy

Gateway is a free place for anyone to post. No account, no payment, no
approval. **No viewpoint, theology, doctrine, or quality judgment is ever
grounds for removal.** Heterodox, unpopular, or poorly argued posts receive an
honest Archangel analysis — never censorship.

Every removal category below describes **conduct**, never belief. The line is:
moderate harmful conduct, never doctrinal conclusions.

| Category | What it covers | What it does NOT cover |
|---|---|---|
| `abusive_content` | Harassment or abuse directed at a person (slurs, "kill yourself") | Testimony about abuse suffered, sharp theological disagreement |
| `threat` | Credible threats of violence against a person | Imprecatory psalms, discussion of biblical violence, angry venting |
| `doxxing` | Publishing private identifying information, or attempting to unmask an anonymous member | Someone voluntarily disclosing their own details |
| `self_harm_encouragement` | Urging another person toward suicide or self-injury | **Disclosing your own suicidal thoughts** — that is a crisis to support (see `app/safety.py`), never a violation |
| `exploitation` | Grooming or sexual approach to a minor | Youth ministry discussion, parenting questions |
| `sexual_content` | Explicit sexual material, solicitation, porn links | Confession of lust/porn addiction, pastoral discussion of sexuality |
| `fraud` | Financial scams, solicitation, impersonating another person | Legitimate requests for prayer or help |
| `spam` | Commercial flooding, link farms, repeated automated posts | Enthusiastic humans posting a lot |
| `illegal` | CSAM, content the operator is legally required to remove | — |

**Doxxing is a first-class category, not a footnote.** People post here under
pen names precisely so they cannot be identified; protecting that is the
platform keeping its central promise, not viewpoint moderation.

## Enforcement layers

1. **Submission screen** (`app/policy.py`) — deterministic, deliberately
   narrow; refuses only unambiguous cases (slurs, direct harassment phrases,
   porn-domain links, link-flood spam) with a message explaining why. It is
   tuned to *never* block abuse testimony or confession.
2. **Archangel flag** — the analyzer may add `content_policy_review_needed`
   to a post's reasoning flags; this opens a content-first report for human
   review. **Analysis never removes content.**
3. **Reader reports** — anyone can report content (`/api/v1/reports` or the
   form on each post). Reports carry no reporter identity.
4. **Human decision** — removal/restore requires the `MODERATION_TOKEN`
   (`POST /api/v1/moderation/{type}/{id}/remove|restore`). Removed content is
   hidden from all listings but retained with its audit trail.

## Rate limits

Open posting is protected by per-client sliding-window limits (defaults: 5
posts, 20 replies, 10 reports per 10 minutes) — see `RATE_LIMIT_*` in
`.env.example`.

## Interaction with the anti-surveillance policy

Reports and moderation are **content-first**: no reporter identity is stored,
no per-author violation history exists, and the moderation queue lists
content, not people. See `docs/ANTI_SURVEILLANCE_POLICY.md`.
