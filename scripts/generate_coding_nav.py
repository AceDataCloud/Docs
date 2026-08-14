#!/usr/bin/env python3
"""Generate deterministic locale paths and publish them into docs.json."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXACT_MAP = ROOT / "scripts" / "data" / "coding-docs-map.json"
OUTPUT = ROOT / "scripts" / "data" / "coding-nav.generated.json"
DOCS_CONFIG = ROOT / "docs.json"
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


def publish_navigation(docs_config: dict[str, object], generated: dict[str, object]) -> None:
    languages = docs_config.get("navigation", {}).get("languages", [])
    language_by_id = {language.get("language"): language for language in languages}
    routes = generated["routes"]
    for locale in LOCALES:
        language = language_by_id.get(locale)
        if not language or not language.get("tabs"):
            raise RuntimeError(f"Missing navigation tab for Coding locale {locale}")
        groups = language["tabs"][0].setdefault("groups", [])
        pages = [
            route["paths"][locale]
            for route in routes
            if (ROOT / f"{route['paths'][locale]}.mdx").is_file()
        ]
        if locale == "zh-Hans" and len(pages) != len(routes):
            raise RuntimeError("The default Coding locale must publish every route")
        coding_group = {
            "group": "Coding",
            "icon": "code",
            "pages": pages,
        }
        indexes = [index for index, group in enumerate(groups) if group.get("group") == "Coding"]
        if indexes:
            groups[indexes[0]] = coding_group
            for index in reversed(indexes[1:]):
                groups.pop(index)
        else:
            groups.append(coding_group)


def main() -> None:
    generated = generate()
    OUTPUT.write_text(json.dumps(generated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    docs_config = json.loads(DOCS_CONFIG.read_text(encoding="utf-8"))
    publish_navigation(docs_config, generated)
    DOCS_CONFIG.write_text(json.dumps(docs_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {len(LOCALES)} locales and {len(generated['routes'])} routes")


if __name__ == "__main__":
    main()
