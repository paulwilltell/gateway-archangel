"""The deterministic slice of the theological eval harness runs in CI.

Full golden-set runs (including hosted-model expectations) are manual:
`python scripts/run_evals.py --analyzer anthropic`.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("run_evals", ROOT / "scripts" / "run_evals.py")
run_evals = importlib.util.module_from_spec(spec)
sys.modules["run_evals"] = run_evals
spec.loader.exec_module(run_evals)

from app.analysis.retrieval import seed_corpus  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.models import User  # noqa: E402


def test_golden_set_passes_in_deterministic_mode():
    cases = json.loads((ROOT / "evals" / "golden_set.json").read_text(encoding="utf-8"))
    assert len(cases) >= 15

    settings = Settings(
        app_env="test", database_url="sqlite://", seed_demo_data=False, archangel_analyzer="heuristic"
    )
    database = Database(settings.database_url)
    database.create_all()

    all_failures: dict[str, list[str]] = {}
    with database.session() as db:
        seed_corpus(db, settings.corpus_seed_path, settings.corpus_version)
        author = User(display_name="Eval Runner", normalized_name="eval runner")
        db.add(author)
        db.flush()
        for case in cases:
            if case["kind"] == "policy":
                failures = run_evals.run_policy_case(case)
            else:
                failures = run_evals.run_analysis_case(db, settings, case, "heuristic", author)
            if failures:
                all_failures[case["id"]] = failures

    assert not all_failures, f"Golden-set failures: {json.dumps(all_failures, indent=2)}"
