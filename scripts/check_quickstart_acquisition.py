#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACQUISITION_URL = (
    "https://platform.acedata.cloud/"
    "?utm_source=docs&utm_medium=quickstart&utm_campaign=docs-quickstart"
)
PLATFORM_ROOT_LINK = re.compile(r"https://platform\.acedata\.cloud(?:/\?[^)\s]*)?\)")


def quickstart_navigation_paths(node: object) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for value in node.values():
            found.update(quickstart_navigation_paths(value))
    elif isinstance(node, list):
        for value in node:
            found.update(quickstart_navigation_paths(value))
    elif isinstance(node, str) and node.endswith("/quickstart"):
        found.add(node)
    return found


def main() -> int:
    errors: list[str] = []
    files = sorted(ROOT.glob("*/quickstart.mdx"))
    if not files:
        errors.append("no localized quickstart pages found")
    for path in files:
        text = path.read_text()
        root_links = PLATFORM_ROOT_LINK.findall(text)
        if not root_links:
            errors.append(f"{path.relative_to(ROOT)}: no platform signup link")
            continue
        expected = f"{ACQUISITION_URL})"
        if any(link != expected for link in root_links):
            errors.append(f"{path.relative_to(ROOT)}: contains an unattributed platform root link")
    navigation = json.loads((ROOT / "docs.json").read_text())
    for page in sorted(quickstart_navigation_paths(navigation)):
        if not (ROOT / f"{page}.mdx").exists():
            errors.append(f"docs.json: missing navigated page {page}.mdx")
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Quickstart acquisition links cover {len(files)} localized pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
