#!/usr/bin/env python3
"""
Translate documentation pages using LLM.

Translates MDX pages while preserving frontmatter, code blocks, and MDX components.
Uses Ace Data Cloud's OpenAI-compatible API.

Usage:
    python scripts/translate_content.py --content-dir . --target-langs zh-CN,ja,ko [--dry-run]

Requires:
    ACEDATACLOUD_OPENAI_KEY environment variable
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "https://api.acedata.cloud/v1"
MODEL = "gpt-4.1-mini"
CACHE_DIR = Path(".cache/translate")

# Directories with English content to translate
TRANSLATE_DIRS = ["tutorials", "comparisons", "use-cases", "blog"]

# Supported target languages (code → display name for prompts)
LANG_NAMES = {
    "zh-CN": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "it": "Italian",
}

# Mintlify i18n locale directory mapping
# Translated files go to: <locale>/<original-path>
# e.g., blog/my-article.mdx → zh-CN/blog/my-article.mdx


def get_api_key() -> str:
    key = os.environ.get("ACEDATACLOUD_OPENAI_KEY", "")
    if not key:
        print("ERROR: ACEDATACLOUD_OPENAI_KEY not set", file=sys.stderr)
        sys.exit(1)
    return key


def call_llm(api_key: str, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    import urllib.request

    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode()

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def cache_key(file_path: Path, lang: str) -> str:
    return f"{file_path.stem}_{lang}"


def is_cached(file_path: Path, lang: str, source_hash: str) -> bool:
    cache_file = CACHE_DIR / f"{cache_key(file_path, lang)}.json"
    if not cache_file.exists():
        return False
    try:
        meta = json.loads(cache_file.read_text())
        return meta.get("source_hash") == source_hash
    except (json.JSONDecodeError, OSError):
        return False


def save_cache(file_path: Path, lang: str, source_hash: str):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cf = CACHE_DIR / f"{cache_key(file_path, lang)}.json"
    cf.write_text(json.dumps({"source_hash": source_hash, "lang": lang}))


def parse_frontmatter(text: str) -> tuple[str, str]:
    """Split frontmatter block and body. Returns (frontmatter_block, body)."""
    if not text.startswith("---"):
        return "", text
    end = text.index("---", 3)
    return text[:end + 3], text[end + 3:]


TRANSLATE_SYSTEM = """You are a professional technical translator for developer documentation.
Translate the following MDX documentation page from English to {lang_name}.

CRITICAL RULES:
1. Translate ALL prose/text to {lang_name}
2. Do NOT translate:
   - Code inside ``` code blocks (keep code exactly as-is)
   - URLs and links (keep href values as-is)
   - API endpoints, model names, parameter names
   - Brand names: Ace Data Cloud, Claude, OpenAI, Midjourney, etc.
   - MDX component names: <Card>, <CardGroup>, <Steps>, <Step>, <Note>, <CodeGroup>
   - Frontmatter keys (title, seo, description)
3. DO translate:
   - Frontmatter VALUES (title, seo, description)
   - Prose paragraphs
   - Table cell text
   - List item text
   - Card title and description text
   - Step title text
4. Keep the same Markdown/MDX structure exactly
5. Output the COMPLETE translated page including frontmatter

The translation should feel natural to a native {lang_name} speaker, not machine-translated."""


def translate_file(
    api_key: str, source_path: Path, lang: str, output_root: Path, dry_run: bool = False
) -> bool:
    """Translate a single file. Returns True if translated."""
    text = source_path.read_text(encoding="utf-8")
    h = content_hash(text)

    if is_cached(source_path, lang, h):
        return False

    if dry_run:
        print(f"  [dry-run] Would translate {source_path} → {lang}")
        return False

    lang_name = LANG_NAMES.get(lang, lang)
    system = TRANSLATE_SYSTEM.format(lang_name=lang_name)

    try:
        translated = call_llm(api_key, system, text, max_tokens=8192)
    except Exception as e:
        print(f"  ERROR translating {source_path} to {lang}: {e}", file=sys.stderr)
        return False

    # Sanity: should still have frontmatter
    if not translated.strip().startswith("---"):
        print(f"  WARNING: Translation missing frontmatter for {source_path} → {lang}, skipping")
        return False

    # Write to locale directory: <lang>/<relative-path>
    rel = source_path.relative_to(output_root)
    out_path = output_root / lang / rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(translated.strip() + "\n", encoding="utf-8")

    save_cache(source_path, lang, h)
    return True


def main():
    parser = argparse.ArgumentParser(description="Translate docs pages using LLM")
    parser.add_argument("--content-dir", default=".", help="Root content directory")
    parser.add_argument("--target-langs", default="zh-CN,ja,ko", help="Comma-separated target languages")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be translated")
    parser.add_argument("--dir", help="Only translate files in this subdirectory")
    args = parser.parse_args()

    root = Path(args.content_dir).resolve()
    api_key = get_api_key()
    langs = [l.strip() for l in args.target_langs.split(",")]

    dirs = [args.dir] if args.dir else TRANSLATE_DIRS
    total = 0
    translated = 0

    for content_dir in dirs:
        d = root / content_dir
        if not d.exists():
            continue
        for f in sorted(d.rglob("*.mdx")):
            for lang in langs:
                total += 1
                if translate_file(api_key, f, lang, root, args.dry_run):
                    translated += 1
                    print(f"  Translated: {f.relative_to(root)} → {lang}")
                    time.sleep(0.5)

    print(f"\nDone: {translated}/{total} translations")


if __name__ == "__main__":
    main()
