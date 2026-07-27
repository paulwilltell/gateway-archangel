"""Measure whether the same post gets the same verdict twice.

The reasoning in an analysis can be excellent and the system still be
untrustworthy, because a reader gets one run, not the distribution. This
harness re-analyzes one post N times and reports where the verdicts disagree.

Claims are not stable identifiers across runs — the model may split a post
into six claims one time and eight the next — so agreement is measured per
*verse*: for each cited reference, which hermeneutic rule fired and which
support level was derived. A reference whose derived level swings between runs
is the concrete defect to fix.

Usage:
    python scripts/consistency_check.py --title "blame" --runs 3
    python scripts/consistency_check.py --body-file post.txt --runs 5

Requires the server running with an anthropic analyzer.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

BASE = "http://127.0.0.1:8000"


def call(path: str, payload=None, timeout: int = 900):
    url = f"{BASE}{path}"
    if payload is None:
        request = urllib.request.Request(url)
    else:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def resolve_post(args) -> str:
    if args.post_id:
        return args.post_id
    if args.title:
        posts = call("/api/v1/posts")
        match = next((p for p in posts if p["title"] == args.title), None)
        if not match:
            raise SystemExit(f"no post titled {args.title!r}")
        return match["id"]
    body = Path(args.body_file).read_text(encoding="utf-8").strip()
    created = call(
        "/api/v1/posts",
        {
            "author_name": "Consistency Harness",
            "title": args.new_title,
            "body": body,
            "training_consent": False,
        },
    )
    print(f"created post {created['id']}")
    return created["id"]


def summarize_run(analysis: dict) -> dict:
    """Per-verse verdicts, keyed by reference — the stable identifier."""
    per_reference: dict[str, tuple[str, str]] = {}
    entailment = (analysis.get("loom_verification") or {}).get("entailment")
    if entailment:
        for record in entailment["claims"]:
            for fired in record["rules_fired"]:
                per_reference[fired["reference"]] = (fired["rule"], fired["yields"])
    return {
        "analyzer": analysis["analyzer_mode"],
        "overall": f"{analysis['alignment']}/{analysis['support_level']}",
        "claim_count": len(analysis["claims"]),
        "confidence": analysis["confidence"],
        "per_reference": per_reference,
        "flags": sorted(analysis.get("reasoning_flags") or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure analysis consistency")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--post-id")
    group.add_argument("--title", help="re-analyze an existing post by title")
    group.add_argument("--body-file", help="create a post from this file first")
    parser.add_argument("--new-title", default="Consistency probe")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", help="write the raw per-run summaries here")
    args = parser.parse_args()

    post_id = resolve_post(args)
    print(f"post {post_id} — {args.runs} runs\n")

    runs = []
    for index in range(args.runs):
        start = time.time()
        analysis = call(f"/api/v1/analysis/post/{post_id}/rerun", payload={})
        elapsed = time.time() - start
        summary = summarize_run(analysis)
        runs.append(summary)
        print(
            f"  run {index + 1}: {elapsed:>4.0f}s  {summary['analyzer']:<10} "
            f"{summary['claim_count']} claims  overall={summary['overall']}  "
            f"refs={len(summary['per_reference'])}"
        )
        if summary["analyzer"] != "anthropic":
            print("    WARNING: fell back to the deterministic analyzer; result not comparable")

    print("\n=== PER-VERSE AGREEMENT ===")
    references = sorted({ref for run in runs for ref in run["per_reference"]})
    stable = unstable = 0
    unstable_detail = []
    for reference in references:
        seen = [run["per_reference"].get(reference) for run in runs]
        present = [s for s in seen if s]
        levels = {s[1] for s in present}
        rules = {s[0] for s in present}
        appearances = f"{len(present)}/{len(runs)}"
        if len(levels) == 1 and len(present) == len(runs):
            stable += 1
            print(f"  STABLE   {reference:<26} {next(iter(levels)):<26} ({appearances})")
        else:
            unstable += 1
            unstable_detail.append((reference, levels, rules, appearances))
            print(f"  VARIES   {reference:<26} {' | '.join(sorted(levels)):<26} ({appearances})")
            print(f"           rules: {', '.join(sorted(rules))}")

    total = stable + unstable
    print("\n=== SUMMARY ===")
    if total:
        print(f"  verse-level agreement: {stable}/{total} ({100 * stable / total:.0f}%)")
    print(f"  claim counts:          {[r['claim_count'] for r in runs]}")
    print(f"  overall verdicts:      {sorted({r['overall'] for r in runs})}")
    confidences = [r["confidence"] for r in runs]
    print(f"  confidence:            {min(confidences):.2f}-{max(confidences):.2f}"
          + (f" (stdev {statistics.stdev(confidences):.3f})" if len(confidences) > 1 else ""))
    flag_sets = [set(r["flags"]) for r in runs]
    common = set.intersection(*flag_sets) if flag_sets else set()
    everything = set.union(*flag_sets) if flag_sets else set()
    print(f"  flags in every run:    {len(common)}/{len(everything)}")

    if args.out:
        Path(args.out).write_text(json.dumps(runs, indent=2, default=list), encoding="utf-8")
        print(f"\n  raw summaries -> {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
