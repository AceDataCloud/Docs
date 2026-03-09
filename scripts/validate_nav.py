#!/usr/bin/env python3
"""Validate docs.json navigation structure."""
import json
from pathlib import Path

docs_dir = Path(__file__).resolve().parent.parent
with open(docs_dir / "docs.json") as f:
    d = json.load(f)

nav = d["navigation"]
langs = nav["languages"]
print(f"Total languages: {len(langs)}")

errors = []
for l in langs:
    code = l["language"]
    has_tabs = "tabs" in l
    has_href = "href" in l

    if has_tabs and has_href:
        errors.append(f"{code}: has BOTH tabs and href (invalid per schema)")

    if has_tabs:
        for tab in l["tabs"]:
            if "tab" not in tab:
                errors.append(f"{code}: tab missing 'tab' key")
            if "groups" not in tab:
                errors.append(f"{code}: tab '{tab.get('tab')}' missing 'groups'")
            else:
                for g in tab["groups"]:
                    if "group" not in g:
                        errors.append(f"{code}: group missing 'group' key")
                    if "pages" not in g and "openapi" not in g:
                        errors.append(f"{code}: group '{g.get('group')}' has no pages or openapi")

if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  - {e}")
else:
    print("Schema validation: OK")


def count_pages(items):
    c = 0
    for item in items:
        if isinstance(item, str):
            c += 1
        elif isinstance(item, dict) and "pages" in item:
            c += count_pages(item["pages"])
    return c


for l in langs:
    code = l["language"]
    if "tabs" in l:
        total = 0
        for tab in l["tabs"]:
            if "groups" in tab:
                for g in tab["groups"]:
                    if "pages" in g:
                        total += count_pages(g["pages"])
        print(f"  {code}: {len(l['tabs'])} tabs, ~{total} pages")
