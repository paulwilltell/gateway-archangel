#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json

from app.config import get_settings
from app.integrations.api_bible import ApiBibleClient
from app.integrations.bible_brain import BibleBrainClient
from app.integrations.sefaria import SefariaClient


def main() -> None:
    settings = get_settings()
    report: dict[str, object] = {}

    try:
        sefaria = SefariaClient(settings.sefaria_base_url)
        result = sefaria.get_text("Genesis 1:1", language="he")
        report["sefaria"] = {"ok": True, "keys": sorted(result.keys())[:12]}
    except Exception as exc:
        report["sefaria"] = {"ok": False, "error": str(exc)}

    if settings.api_bible_api_key:
        try:
            bibles = ApiBibleClient(settings.api_bible_api_key, settings.api_bible_base_url).list_bibles()
            report["api_bible"] = {"ok": True, "bibles": len(bibles)}
        except Exception as exc:
            report["api_bible"] = {"ok": False, "error": str(exc)}
    else:
        report["api_bible"] = {"ok": False, "skipped": "API_BIBLE_API_KEY not configured"}

    if settings.bible_brain_api_key:
        try:
            result = BibleBrainClient(
                settings.bible_brain_api_key,
                settings.bible_brain_base_url,
            ).search_bibles("eng")
            report["bible_brain"] = {"ok": True, "response_type": type(result).__name__}
        except Exception as exc:
            report["bible_brain"] = {"ok": False, "error": str(exc)}
    else:
        report["bible_brain"] = {"ok": False, "skipped": "BIBLE_BRAIN_API_KEY not configured"}

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
