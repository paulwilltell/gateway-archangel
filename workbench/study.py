"""The Workbench CLI — dig into the KJV, honestly.

    python -m workbench.study echo "Micah 6:8"
    python -m workbench.study echo "John 3:16" --top 15
    python -m workbench.study novel
    python -m workbench.study novel --null

Every result carries its null baseline. A z-score near 0 means the pattern is
what chance gives; a high z-score means it stands out. Read accordingly, and
take anything worth pursuing through Gateway's trust pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workbench.echo import find_echoes  # noqa: E402
from workbench.novelty import most_novel, null_comparison  # noqa: E402


def cmd_echo(args) -> int:
    try:
        result = find_echoes(args.reference, top=args.top)
    except KeyError as exc:
        print(exc)
        return 1
    print(f"\n{result['query']} — {result['text']}\n")
    if not result["echoes"]:
        print(result.get("note", "No echoes found."))
        return 0
    null = result["null"]
    print(f"(baseline: this verse's similarity to random verses averages "
          f"{null['mean']}; z = how far above that a match sits)\n")
    for echo in result["echoes"]:
        flag = "  ***" if echo.z_score >= 8 else ("   **" if echo.z_score >= 4 else "     ")
        print(f"{flag} z={echo.z_score:>5}  sim={echo.similarity:<5}  {echo.reference}")
        print(f"        {echo.text[:88]}")
        print(f"        shared: {', '.join(echo.shared_words)}\n")
    return 0


def cmd_novel(args) -> int:
    if args.null:
        report = null_comparison()
        print("\nNull check — mean score of top 100:")
        print(f"  real order:     {report['real_mean_score']}")
        print(f"  shuffled order: {report['shuffled_mean_score']}")
        gap = report["real_mean_score"] - report["shuffled_mean_score"]
        print(f"  gap:            {round(gap, 3)}  "
              f"({'real order carries signal' if gap > 0.05 else 'little separation — mostly form'})\n")
        print("Real-order top 10:")
        for score, reference in report["real_top"]:
            print(f"  {score:5}  {reference}")
        return 0

    print("\nMost lexically novel verses (book openers excluded):\n")
    for score, verse in most_novel(top=args.top):
        print(f"  {score:5.2f}  {verse['reference']:<20} {verse['text'][:66]}")
    print("\nLexical novelty points somewhere to look; it does not establish meaning.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Personal KJV study workbench")
    sub = parser.add_subparsers(dest="command", required=True)

    p_echo = sub.add_parser("echo", help="find verses that echo a given verse")
    p_echo.add_argument("reference")
    p_echo.add_argument("--top", type=int, default=12)

    p_novel = sub.add_parser("novel", help="most lexically novel verses")
    p_novel.add_argument("--top", type=int, default=20)
    p_novel.add_argument("--null", action="store_true", help="run the shuffle baseline")

    args = parser.parse_args()
    if args.command == "echo":
        return cmd_echo(args)
    return cmd_novel(args)


if __name__ == "__main__":
    raise SystemExit(main())
