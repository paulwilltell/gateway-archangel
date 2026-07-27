from __future__ import annotations

import httpx


class ApiBibleClient:
    """Minimal API.Bible connector.

    Scripture content must be stored, displayed, and trained on only when the
    translation's license and the application's API plan permit it.
    """

    def __init__(self, api_key: str, base_url: str = "https://rest.api.bible/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str, params: dict | None = None) -> dict:
        response = httpx.get(
            f"{self.base_url}{path}",
            headers={"api-key": self.api_key, "accept": "application/json"},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def list_bibles(self, language: str = "eng") -> list[dict]:
        return self._get("/bibles", {"language": language}).get("data", [])

    def get_verse(self, bible_id: str, verse_id: str) -> dict:
        return self._get(
            f"/bibles/{bible_id}/verses/{verse_id}",
            {
                "content-type": "text",
                "include-notes": "false",
                "include-titles": "false",
                "include-chapter-numbers": "false",
                "include-verse-numbers": "false",
            },
        ).get("data", {})
