# Content Policy

Gateway is a free place for anyone to post. No account, no payment, no
approval. **No viewpoint, theology, doctrine, or quality judgment is ever
grounds for removal.** Heterodox, unpopular, or poorly argued posts receive an
honest Archangel analysis — never censorship.

Content is refused or removed only for four categories:

| Category | What it covers | What it does NOT cover |
|---|---|---|
| `sexual_content` | Explicit sexual material, solicitation, porn links | Confession of lust/porn addiction, pastoral discussion of sexuality |
| `abusive_content` | Harassment or abuse directed at a person (slurs, "kill yourself") | Testimony about abuse suffered, sharp theological disagreement |
| `spam` | Commercial flooding, link farms, repeated automated posts | Enthusiastic humans posting a lot |
| `illegal` | CSAM, true threats, content the operator is legally required to remove | — |

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
