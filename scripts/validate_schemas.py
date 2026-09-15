#!/usr/bin/env python3
"""Validate every file under data/ against its JSON Schema.

Used by CI and by `apk validate`. Exits non-zero on any schema violation.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from apk.cli import cmd_validate  # noqa: E402


class _Args:
    def __init__(self, path: str):
        self.path = path
        self.schemas = None


def main() -> int:
    data_dir = REPO_ROOT / "data"
    return cmd_validate(_Args(str(data_dir)))


if __name__ == "__main__":
    raise SystemExit(main())
