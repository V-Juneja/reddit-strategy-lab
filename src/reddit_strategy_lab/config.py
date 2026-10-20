"""Load only approved Reddit configuration names; never execute dotenv content."""

import os
import re
from pathlib import Path

NAMES = {
    "REDDIT_ACCESS_TOKEN",
    "REDDIT_USER_AGENT",
    "REDDIT_API_APPROVED",
}


def read_env(path, names=NAMES):
    path = Path(path).expanduser()
    if not path.is_file() or path.stat().st_size > 64000:
        raise ValueError("credential configuration file missing or too large")
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"(?:export )?([A-Z_][A-Z0-9_]*)\s*=\s*(.*)", line.strip())
        if match and match[1] in names:
            value = match[2].strip()
            if len(value) > 1 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            os.environ.setdefault(match[1], value)


def configure():
    if Path(".env").is_file():
        read_env(".env")
