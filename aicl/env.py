"""Load KEY=VALUE lines from a .env file next to the repository root into os.environ.

Lets API keys live in one git-ignored file instead of being typed into every
terminal. Existing environment variables win; nothing is printed or logged.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path | None = None) -> int:
    path = path or Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return 0
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            n += 1
    return n
