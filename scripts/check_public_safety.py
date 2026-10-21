#!/usr/bin/env python3
"""Scan Git's actual public candidates, including tracked ignored files; never echo matches."""

import subprocess
import sys
from pathlib import Path

from reddit_strategy_lab.security import findings

# Manually reviewed article artwork. Keep this list explicit so new image files
# still require review before they can be included in a public snapshot.
REVIEWED_PUBLIC_ARTWORK = {
    "assets/reddit-logo-user-upload.png",
    "assets/reddit-strategy-finder-cover.png",
    "assets/reddit-strategy-finder-cover.svg.png",
    "assets/reddit-strategy-finder-preview-1400x1000.png",
    "assets/road-to-1m-900.png",
}


def scan(root):
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    names = sorted(set(n for n in result.stdout.decode().split("\0") if n))
    blocked = []
    for name in names:
        p = root / name
        categories = []
        if p.is_symlink():
            categories.append("symlink-review")
        lower = name.lower()
        if p.name.startswith(".env") and p.name != ".env.example":
            categories.append("unexpected-env")
        if (
            any(t in lower for t in ("credential", "oauth", "account_export", "raw_posts"))
            or lower.startswith(("runs/", "data/"))
            and lower != "data/readme.md"
        ):
            categories.append("private-output")
        if p.is_file() and not p.is_symlink():
            if p.suffix.lower() in (".png", ".jpg", ".pdf"):
                if not name.startswith("examples/reports/") and name not in REVIEWED_PUBLIC_ARTWORK:
                    categories.append("unreviewed-binary")
            else:
                try:
                    categories += findings(p.read_text())
                except UnicodeError:
                    categories.append("unknown-binary")
        for category in sorted(set(categories)):
            blocked.append((name, category))
    for name, category in blocked:
        print(f"{name}: {category}")
    print(f"Scanned {len(names)} public candidate files; {len(blocked)} blocking findings. Not a guarantee.")
    return bool(blocked)


if __name__ == "__main__":
    sys.exit(int(scan(Path(__file__).resolve().parents[1])))
