# Privacy threat model

Gateway is built on a principle: **membership lists have historically been the
mechanism of persecution, so this platform builds none.** There are no
accounts, no emails, no passwords, no per-user analysis rollups, and no stored
conversations.

That principle is real, but it is not the same as safety. This document says
plainly what the design resists and what it does not, so nobody trusts it
further than it has earned. **The accurate description is
"privacy-minimized and registry-resistant" — not "anonymous" and not
"persecution-proof."**

## What the design resists

| Threat | Why it is resisted |
|---|---|
| Seizure or subpoena of a membership list | None exists. There is no users-with-identities table, no email column, no credential store. |
| Email or phone subpoena | Never collected. |
| Credential theft / password breach | No passwords exist. |
| Conversation-history breach | Archangel conversations are never persisted by Gateway; no conversation table exists (enforced by test). |
| Per-user behavioral profiling by the operator | Analyses attach to content and carry no author identity; no per-user rollup endpoint exists, and adding one breaks a test. |
| Casual reader-log harvesting | The server runs with `--no-access-log`; visitor IPs are not written by the application, Dockerfile, or Makefile. |
| Loss of control over your own words | Ownership tokens permit withdrawal and consent revocation without an account (`app/ownership.py`). |
| Report-based retaliation | Reports store no reporter identity. |

## What the design does NOT resist

Read this list as seriously as the one above.

| Threat | Reality |
|---|---|
| **Self-identifying content** | The most likely deanonymizer is the text itself. "I'm the only deacon at the church on Elm Street" identifies its author with no registry involved. Nothing in software can fix this. |
| **Stylometry** | Writing style is identifying across enough posts. Persistent pen names make this worse by grouping a corpus under one label. |
| **Hosting-provider records** | Whoever runs the server sees connections. `--no-access-log` stops *application* logging, not the host's, a reverse proxy's, a CDN's, or a firewall's. |
| **Network-level surveillance** | An observer between the reader and the server sees the connection regardless of what the application stores. |
| **Upstream AI-provider retention** | Posts and chat messages are sent to the hosted model provider for analysis and are subject to that provider's retention and legal process. This is the largest gap and the UI states it. |
| **Targeted legal process** | A court order to the operator or the host reaches whatever exists at that moment, including database backups. |
| **Compromised devices or malicious browser extensions** | Out of the platform's reach entirely. |
| **Timing and correlation** | Posting times, and content cross-posted elsewhere, can link a pen name to a known identity. |
| **Backups** | `scripts/backup_db.py` copies the database; those copies live wherever the operator puts them and inherit the operator's own protection. |

## Guidance the platform owes its users

- Use a pen name, or the anonymous option. Never your real name.
- Assume the words themselves are the leak. Change identifying details in
  testimony — the town, the number of children, the job title.
- A fresh pen name per sensitive post beats a persistent one.
- If disclosure would endanger you — a hostile spouse, an employer, a state —
  do not use a general-purpose public platform for it, this one included.

## For the operator

Before any public deployment: choose the jurisdiction deliberately, disable
logging at the proxy and host layers as well as the application, review the
model provider's retention terms and consider a zero-retention agreement,
encrypt backups, and set a deletion policy for audit events. None of these are
done by the code in this repository.
