from __future__ import annotations

import httpx


class BibleBrainClient:
    """Bible Brain / Digital Bible Platform v4 connector."""

    def __init__(self, api_key: str, base_url: str = "https://4.dbt.io/api"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str, params: dict | None = None) -> dict:
        query = dict(params or {})
        query["key"] = self.api_key
        response = httpx.get(f"{self.base_url}{path}", params=query, timeout=30)
        response.raise_for_status()
        return response.json()

    def search_bibles(self, language_code: str = "eng") -> dict:
        return self._get("/bibles", {"language_code": language_code})
