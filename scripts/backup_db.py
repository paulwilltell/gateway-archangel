"""Back up gateway.db safely (uses SQLite's online backup API, so it is
correct even while the server is running). Keeps the newest 30 backups.

Usage:  python scripts/backup_db.py
Schedule it (Windows Task Scheduler) daily once the community matters.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "gateway.db"
BACKUP_DIR = ROOT / "backups"
KEEP = 30


def main() -> int:
    if not DB.exists():
        print("No gateway.db found — nothing to back up.")
        return 0
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"gateway-{stamp}.db"

    src = sqlite3.connect(DB)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    print(f"Backed up to {target} ({target.stat().st_size:,} bytes)")

    backups = sorted(BACKUP_DIR.glob("gateway-*.db"))
    for old in backups[:-KEEP]:
        old.unlink()
        print(f"Pruned {old.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
