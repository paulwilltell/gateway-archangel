"""Theological regression harness.

Runs the golden set (evals/golden_set.json) against the live analysis
pipeline and checks each case's expectations plus universal invariants.
This is the quality ratchet: run it before and after any prompt, model,
corpus, or engine change.

Usage:
    python scripts/run_evals.py                     # free, deterministic analyzer
    python scripts/run_evals.py --analyzer anthropic  # live Claude (costs money)
    python scripts/run_evals.py --case dream-obligation

Exit code 0 = all cases passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analysis.engine import analysis_to_dict, analyze_target  # noqa: E402
from app.analysis.retrieval import seed_corpus  # noqa: E402
from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.models import Post, User  # noqa: E402
from app.policy import screen_content  # noqa: E402

GOLDEN = ROOT / "evals" / "golden_set.json"
LEVELS = {"none": 0, "concern": 1, "urgent": 2, "immediate": 3}
TEXTUAL = {"direct_text", "strong_inference"}


def check_invariants(analysis: dict) -> list[str]:
    """Invariants every analysis must satisfy in every analyzer mode."""
    failures = []
    if not (0.0 <= analysis["confidence"] <= 1.0):
        failures.append(f"confidence out of range: {analysis['confidence']}")
    loom = analysis.get("loom_verification")
    if not loom:
        failures.append("loom_verification missing")
        return failures
    for record, claim in zip(loom["claims"], analysis["claims"]):
        if not record["grounded"] and claim["support_level"] in TEXTUAL:
            failures.append(
                f"claim {record['claim_index']} keeps textual support without grounding"
            )
    return failures


def check_expectations(case: dict, analysis: dict, analyzer: str) -> list[str]:
    failures = []
    expect = case.get("expect", {})

    if "evidence_includes" in expect:
        refs = {e["reference"] for e in analysis["evidence"]}
        for want in expect["evidence_includes"]:
            if want not in refs:
                failures.append(f"evidence missing {want}")
    if expect.get("evidence_empty") and analysis["evidence"]:
        failures.append(f"expected empty evidence, got {len(analysis['evidence'])} verses")
    if "safety_min" in expect:
        got = analysis["safety"]["level"]
        if LEVELS[got] < LEVELS[expect["safety_min"]]:
            failures.append(f"safety {got} below required {expect['safety_min']}")

    mode_expect = expect.get(analyzer, {})
    if analyzer == "anthropic" and analysis["analyzer_mode"] != "anthropic":
        failures.append("fell back to heuristic — provider did not run")
        return failures
    if "alignment" in mode_expect and analysis["alignment"] != mode_expect["alignment"]:
        failures.append(f"alignment {analysis['alignment']} != {mode_expect['alignment']}")
    if "alignment_in" in mode_expect and analysis["alignment"] not in mode_expect["alignment_in"]:
        failures.append(f"alignment {analysis['alignment']} not in {mode_expect['alignment_in']}")
    if "overall_support_not" in mode_expect and analysis["support_level"] in mode_expect["overall_support_not"]:
        failures.append(f"support_level {analysis['support_level']} is forbidden for this case")
    if "flags_any" in mode_expect:
        flags = " ".join(analysis.get("reasoning_flags", []))
        if not any(fragment in flags for fragment in mode_expect["flags_any"]):
            failures.append(f"no flag matching any of {mode_expect['flags_any']} (got: {flags or 'none'})")
    return failures


def run_policy_case(case: dict) -> list[str]:
    verdict = screen_content(case["body"])
    expect = case["expect"]
    if "policy_blocked" in expect:
        if verdict.allowed:
            return [f"expected block ({expect['policy_blocked']}), content was allowed"]
        if verdict.category != expect["policy_blocked"]:
            return [f"blocked as {verdict.category}, expected {expect['policy_blocked']}"]
    elif expect.get("policy_allowed") and not verdict.allowed:
        return [f"legitimate content was blocked as {verdict.category}: {verdict.message}"]
    return []


def run_analysis_case(db, settings: Settings, case: dict, analyzer: str, author: User) -> list[str]:
    post = Post(author_id=author.id, title=case["title"], body=case["body"], training_consent=False)
    db.add(post)
    db.flush()
    analysis_row = analyze_target(db, settings, "post", post.id)
    analysis = analysis_to_dict(analysis_row)
    return check_invariants(analysis) + check_expectations(case, analysis, analyzer)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the theological eval golden set")
    parser.add_argument("--analyzer", choices=["heuristic", "anthropic"], default="heuristic")
    parser.add_argument("--case", help="run a single case by id")
    args = parser.parse_args()

    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    if args.case:
        cases = [c for c in cases if c["id"] == args.case]
        if not cases:
            print(f"No case named {args.case!r}")
            return 2

    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        seed_demo_data=False,
        archangel_analyzer=args.analyzer,
    )
    if args.analyzer == "anthropic":
        n = sum(1 for c in cases if c["kind"] == "analysis")
        print(f"NOTE: anthropic mode sends {n} analysis cases to the API (rough cost: a few cents each).\n")

    database = Database(settings.database_url)
    database.create_all()

    passed = failed = 0
    with database.session() as db:
        seed_corpus(db, settings.corpus_seed_path, settings.corpus_version)
        author = User(display_name="Eval Runner", normalized_name="eval runner")
        db.add(author)
        db.flush()

        for case in cases:
            if case["kind"] == "policy":
                failures = run_policy_case(case)
            else:
                failures = run_analysis_case(db, settings, case, args.analyzer, author)
            status = "PASS" if not failures else "FAIL"
            if failures:
                failed += 1
            else:
                passed += 1
            print(f"[{status}] {case['id']} ({case['category']})")
            for failure in failures:
                print(f"       - {failure}")

    print(f"\n{passed} passed, {failed} failed ({args.analyzer} mode, {len(cases)} cases)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
