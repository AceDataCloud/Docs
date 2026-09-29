#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOKEN_FIELD = re.compile(r"^\s*(?:\*\*)?(?:CA|Contract(?: address)?|Mint)(?:\*\*)?\s*[:：]", re.IGNORECASE | re.MULTILINE)
KNOWN_MINTS = (
    "GnHpRsrcyfHSMZNzmpjAzTFQA26vnbRMzbKQ11ZKpump",
    "GEuuznWpn6iuQAJxLKQDVGXPtrqXHNWTk3gZqqvJpump",
)


def main() -> int:
    errors: list[str] = []
    files = sorted(ROOT.glob("*/resources/support.mdx"))
    if not files:
        errors.append("no localized support pages found")
    for path in files:
        text = path.read_text()
        if TOKEN_FIELD.search(text):
            errors.append(f"{path.relative_to(ROOT)}: support page contains a token field")
        if any(mint in text for mint in KNOWN_MINTS):
            errors.append(f"{path.relative_to(ROOT)}: support page contains an ACE mint")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Support identity check passed for {len(files)} localized pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
