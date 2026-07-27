"""Anonymous post ownership.

Gateway has no accounts, so there is no login that proves you wrote something.
Without a substitute, an anonymous author could never delete a post they
regret, correct an error, or withdraw research consent — anonymity would mean
permanent loss of control over your own words.

The substitute is a bearer token:

- On publishing, the server generates a long random token and stores **only
  its SHA-256 hash** on the row.
- The token is shown to the author exactly once and never again.
- Possession of the token authorises withdrawal (delete) or consent
  withdrawal for that one item.

Because only a hash is stored, the token links a person to *one* post and to
nothing else: it cannot be used to enumerate someone's contributions, and a
seized database yields no tokens. Losing the token means losing control of
that post — which is the honest cost of having no account to recover.
"""

from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 24


def new_token() -> tuple[str, str]:
    """Return (token_shown_once, hash_to_store)."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def token_matches(token: str, stored_hash: str | None) -> bool:
    if not token or not stored_hash:
        return False
    return secrets.compare_digest(hash_token(token), stored_hash)
