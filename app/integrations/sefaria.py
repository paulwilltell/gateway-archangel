from __future__ import annotations

from urllib.parse import quote

import httpx


class SefariaClient:
    """Read-only research connector for structured Jewish texts.

    Sefaria material is evidence with provenance, not an automatic doctrinal ruling.
    Respect Sefaria's current API and dataset terms before caching or model training.
    """

    def __init__(self, base_url: str = "https://www.sefaria.org/api"):
        self.base_url = base_url.rstrip("/")

    def get_text(self, reference: str, language: str = "he") -> dict:
        encoded = quote(reference, safe="")
        response = httpx.get(
            f"{self.base_url}/v3/texts/{encoded}",
            params={"version": "primary", "language": language},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
