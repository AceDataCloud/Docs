#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SDK_URL = (
    "https://github.com/AceDataCloud/SDK"
    "?utm_source=docs&utm_medium=quickstart&utm_campaign=docs-sdk"
)


def main() -> int:
    errors: list[str] = []
    files = sorted(ROOT.glob("*/quickstart.mdx"))
    if not files:
        errors.append("no localized quickstart pages found")
    for path in files:
        text = path.read_text()
        if text.count(f'<Card title="SDK" icon="box" href="{SDK_URL}">') != 1:
            errors.append(f"{path.relative_to(ROOT)}: expected one canonical SDK card")
        for package in ("`acedatacloud`", "`@acedatacloud/sdk`", "Go"):
            if package not in text:
                errors.append(f"{path.relative_to(ROOT)}: SDK card is missing {package}")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Quickstart SDK cards cover {len(files)} localized pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
