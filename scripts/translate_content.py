#!/usr/bin/env python3
"""
Translate Docs content from Chinese (zh-CN) to all target languages.

Source of truth: root MDX files (Chinese / zh-CN)
Targets: en, zh-TW, ja, ko, es, fr, de, pt, ru, ar, it, fi, sv, el, uk, pl, sr

Uses api.acedata.cloud with ACEDATACLOUD_OPENAI_KEY.

Usage:
    python scripts/translate_content.py [--output-dir .] [--languages en ja ko]
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DOCS_DIR = Path(__file__).parent.parent
API_BASE = "https://api.acedata.cloud/v1"
MODEL = "gpt-4.1-mini"
CACHE_DIR = DOCS_DIR / ".cache" / "translate"

ALL_TARGET_LANGUAGES = [
    "en", "zh-TW", "ja", "ko", "es", "fr", "de", "pt",
    "ru", "ar", "it", "fi", "sv", "el", "uk", "pl", "sr",
]

LANGUAGE_NAMES_ZH = {
    "en": "英文",
    "zh-TW": "繁体中文",
    "ja": "日语",
    "ko": "韩语",
    "es": "西班牙语",
    "fr": "法语",
    "de": "德语",
    "pt": "葡萄牙语",
    "ru": "俄语",
    "ar": "阿拉伯语",
    "it": "意大利语",
    "fi": "芬兰语",
    "sv": "瑞典语",
    "el": "希腊语",
    "uk": "乌克兰语",
    "pl": "波兰语",
    "sr": "塞尔维亚语",
}

# Directories to translate (relative to DOCS_DIR)
TRANSLATABLE_DIRS = [
    "guides",
    "tutorials",
    "comparisons",
    "use-cases",
    "blog",
    "api-reference",
    "mcp",
    "resources",
]

# Also translate root-level MDX files
ROOT_FILES = [
    "introduction.mdx",
    "quickstart.mdx",
    "authentication.mdx",
]


# ===========================================================================
# LLM helpers
# ===========================================================================

def get_api_key() -> str:
    return os.environ.get("ACEDATACLOUD_OPENAI_KEY", "")


def call_llm(api_key: str, system: str, user: str, max_tokens: int = 4096) -> str:
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
    ).encode()
    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as e:
        print(f"    LLM TIMEOUT/NET ERROR: {e}", file=sys.stderr, flush=True)
        return ""
    except Exception as e:
        print(f"    LLM ERROR: {e}", file=sys.stderr, flush=True)
        return ""


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def get_cached(lang: str, rel_path: str, content_hash: str) -> str | None:
    p = CACHE_DIR / lang / f"{rel_path}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
        if d.get("hash") == content_hash:
            return d.get("content", "")
    except Exception:
        pass
    return None


def save_cache(lang: str, rel_path: str, content_hash: str, content: str):
    p = CACHE_DIR / lang / f"{rel_path}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"hash": content_hash, "content": content}, ensure_ascii=False))


# ===========================================================================
# Translation
# ===========================================================================

SYSTEM_PROMPT = """\
你是专业技术文档翻译员。将以下中文 MDX/Markdown 文档翻译为{lang_name}。
规则：
1. 保留完整的 YAML frontmatter（翻译 title/description/sidebarTitle，不翻译 openapi/字段名）
2. 保留所有 MDX 组件标签（<Note>, <Steps>, <CodeGroup> 等）不变
3. 不翻译 URL、代码块内容、API 路径
4. 翻译 MDX 组件 title 属性值（如 <Note title="提示"> 翻译为 <Note title="Tip">）
5. 只输出翻译结果，不加解释
6. 技术术语保持常见译法"""


def translate_file(
    api_key: str,
    src_file: Path,
    lang: str,
    output_dir: Path,
) -> bool:
    """Translate a single file from Chinese to target language."""
    content = src_file.read_text(encoding="utf-8")
    if not content.strip():
        return False

    # Compute relative path from DOCS_DIR
    try:
        rel = src_file.relative_to(DOCS_DIR)
    except ValueError:
        rel = src_file.relative_to(output_dir)
    rel_str = str(rel).replace("\\", "/")

    # Check cache
    ch = _content_hash(content)
    cached = get_cached(lang, rel_str, ch)
    if cached:
        dst = output_dir / lang / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(cached, encoding="utf-8")
        return True

    # Call LLM
    lang_name = LANGUAGE_NAMES_ZH.get(lang, lang)
    sys_prompt = SYSTEM_PROMPT.format(lang_name=lang_name)
    result = call_llm(api_key, sys_prompt, content, max_tokens=4096)
    if not result:
        return False

    # Remove any ```mdx or ``` wrapper
    if result.startswith("```"):
        lines = result.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        result = "\n".join(lines)

    # Save
    dst = output_dir / lang / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(result, encoding="utf-8")
    save_cache(lang, rel_str, ch, result)
    return True


def collect_source_files(docs_dir: Path) -> list[Path]:
    """Collect all Chinese MDX source files to translate."""
    files: list[Path] = []

    # Root files
    for name in ROOT_FILES:
        p = docs_dir / name
        if p.exists():
            files.append(p)

    # Translatable directories
    for d in TRANSLATABLE_DIRS:
        dp = docs_dir / d
        if dp.is_dir():
            for f in sorted(dp.rglob("*.mdx")):
                # Skip files that look like they're already in a language dir
                try:
                    rel = f.relative_to(docs_dir)
                    parts = rel.parts
                    if parts[0] in ALL_TARGET_LANGUAGES:
                        continue
                except ValueError:
                    pass
                files.append(f)

    return files


def collect_root_files(docs_dir: Path) -> list[Path]:
    """Collect only root-level MDX files (intro, quickstart, auth) plus
    generated static pages like api-reference/introduction and mcp/overview
    that are not sourced from PlatformBackend translations."""
    files: list[Path] = []
    for name in ROOT_FILES:
        p = docs_dir / name
        if p.exists():
            files.append(p)

    # Also translate api-reference/introduction.mdx and mcp/overview.mdx
    # since these are generated by sync.py (not from PlatformBackend translations)
    for extra in [
        "api-reference/introduction.mdx",
        "mcp/overview.mdx",
    ]:
        p = docs_dir / extra
        if p.exists():
            files.append(p)

    return files


def main():
    import argparse

    t0 = time.time()

    parser = argparse.ArgumentParser(description="Translate docs from zh-CN to all target languages")
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR)
    parser.add_argument("--languages", nargs="*", default=None, help="Target languages (default: all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root-only", action="store_true",
                        help="Only translate root MDX files (intro, quickstart, auth). "
                             "Use when PlatformBackend translations handle guides/tutorials.")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("ERROR: ACEDATACLOUD_OPENAI_KEY not set", file=sys.stderr, flush=True)
        sys.exit(1)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    langs = args.languages or ALL_TARGET_LANGUAGES
    print(f"Source: zh-CN (root)", flush=True)
    print(f"Targets: {', '.join(langs)}", flush=True)

    if args.root_only:
        src_files = collect_root_files(args.output_dir)
    else:
        src_files = collect_source_files(args.output_dir)
    print(f"Source files: {len(src_files)}", flush=True)

    if args.dry_run:
        for f in src_files:
            print(f"  {f.relative_to(args.output_dir)}", flush=True)
        print(f"\nWould translate {len(src_files)} files × {len(langs)} languages = {len(src_files) * len(langs)} translations", flush=True)
        return

    stats = {"translated": 0, "cached": 0, "failed": 0}
    total = len(src_files) * len(langs)
    done = 0
    llm_calls = 0

    print(f"\nTotal: {total} translations ({len(src_files)} files × {len(langs)} languages)", flush=True)

    for lang_idx, lang in enumerate(langs):
        lang_t0 = time.time()
        lang_translated = 0
        lang_cached = 0
        print(f"\n{'='*40}", flush=True)
        print(f"Language {lang_idx+1}/{len(langs)}: {lang} ({LANGUAGE_NAMES_ZH.get(lang, lang)})", flush=True)
        print(f"{'='*40}", flush=True)
        for src in src_files:
            done += 1
            rel = src.relative_to(args.output_dir)

            # Check if cached
            content = src.read_text(encoding="utf-8")
            ch = _content_hash(content)
            if get_cached(lang, str(rel), ch):
                dst = args.output_dir / lang / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                cached = get_cached(lang, str(rel), ch)
                if cached:
                    dst.write_text(cached, encoding="utf-8")
                stats["cached"] += 1
                lang_cached += 1
                continue

            llm_calls += 1
            t1 = time.time()
            print(f"  [{done}/{total}] {rel} → {lang}", end="", flush=True)
            if translate_file(api_key, src, lang, args.output_dir):
                stats["translated"] += 1
                lang_translated += 1
                dt = time.time() - t1
                print(f" ✓ ({dt:.1f}s)", flush=True)
            else:
                stats["failed"] += 1
                dt = time.time() - t1
                print(f" ✗ FAILED ({dt:.1f}s)", flush=True)
            time.sleep(0.3)

        lang_dt = time.time() - lang_t0
        print(f"  {lang} done: {lang_translated} translated, {lang_cached} cached ({lang_dt:.1f}s)", flush=True)

    elapsed = time.time() - t0
    print(f"\n{'='*40}", flush=True)
    print(f"Translation complete in {elapsed:.1f}s", flush=True)
    print(f"  translated={stats['translated']} cached={stats['cached']} failed={stats['failed']}", flush=True)
    print(f"  LLM calls={llm_calls}", flush=True)
    print(f"{'='*40}", flush=True)


if __name__ == "__main__":
    main()
