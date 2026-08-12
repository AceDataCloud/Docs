#!/usr/bin/env python3
"""Generate deterministic locale paths for Coding selector guides."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXACT_MAP = ROOT / "scripts" / "data" / "coding-docs-map.json"
OUTPUT = ROOT / "scripts" / "data" / "coding-nav.generated.json"
LOCALES = ["zh-Hans", "zh-Hant", "en", "ja", "ko", "es", "fr", "de", "pt", "ru", "ar", "it", "sv", "uk", "pl"]


def generate() -> dict[str, object]:
    bundle = json.loads(EXACT_MAP.read_text(encoding="utf-8"))
    routes = [
        {
            "canonical_alias": record["canonical_alias"],
            "source_doc_key": record["source_doc_key"],
            "paths": {locale: f"{locale}/{record['output_path'].removesuffix('.mdx')}" for locale in LOCALES},
        }
        for record in bundle["records"]
    ]
    return {
        "schema_version": 1,
        "locales": LOCALES,
        "routes": routes,
    }


def main() -> None:
    expected = json.dumps(generate(), ensure_ascii=False, indent=2) + "\n"
    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"generated {len(LOCALES)} locales and {len(generate()['routes'])} routes")


if __name__ == "__main__":
    main()
