#!/usr/bin/env python3
"""
Translate Docs content to all target languages (including zh-CN).

Source of truth: root MDX files (any language)
Targets: zh-CN (overwrites root), en, zh-TW, ja, ko, es, fr, de, pt, ru, ar, it, fi, sv, el, uk, pl, sr

The zh-CN translation writes back to the root directory (Mintlify default language).
All other translations write to their respective language subdirectories.

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
    "zh-CN",
    "en",
    "zh-TW",
    "ja",
    "ko",
    "es",
    "fr",
    "de",
    "pt",
    "ru",
    "ar",
    "it",
    "fi",
    "sv",
    "el",
    "uk",
    "pl",
    "sr",
]

LANGUAGE_NAMES_ZH = {
    "zh-CN": "简体中文",
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


def call_llm(api_key: str, system: str, user: str, max_tokens: int = 16384) -> str:
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
        with urllib.request.urlopen(req, timeout=180) as resp:
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
    p.write_text(
        json.dumps({"hash": content_hash, "content": content}, ensure_ascii=False)
    )


def _is_mostly_chinese(text: str, threshold: float = 0.15) -> bool:
    """Check if text has significant Chinese character density (CJK Unified)."""
    # Strip code blocks and frontmatter to check prose only
    import re

    stripped = re.sub(r"```[\s\S]*?```", "", text)
    stripped = re.sub(r"^---[\s\S]*?---", "", stripped, count=1)
    stripped = re.sub(r"<[^>]+>", "", stripped)
    stripped = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", stripped)
    stripped = re.sub(r"[`#*_\-=|>\[\](){}]", "", stripped)
    chars = [c for c in stripped if not c.isspace()]
    if not chars:
        return False
    cjk = sum(1 for c in chars if "\u4e00" <= c <= "\u9fff")
    return cjk / len(chars) > threshold


# ===========================================================================
# Translation
# ===========================================================================

SYSTEM_PROMPT = """\
你是专业技术文档翻译员。将以下 MDX/Markdown 文档翻译为{lang_name}。
源文档可能是任何语言，请准确翻译为目标语言。
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
    """Translate a single file to target language. Source can be any language."""
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
        # zh-CN writes to root (overwrites source), others to lang subdir
        if lang == "zh-CN":
            dst = output_dir / rel
        else:
            dst = output_dir / lang / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(cached, encoding="utf-8")
        return True

    # For zh-CN: skip LLM if source is already Chinese (use as-is)
    if lang == "zh-CN" and _is_mostly_chinese(content):
        save_cache(lang, rel_str, ch, content)
        return True

    # Call LLM — scale max_tokens to content length (rough ~4 chars/token)
    lang_name = LANGUAGE_NAMES_ZH.get(lang, lang)
    sys_prompt = SYSTEM_PROMPT.format(lang_name=lang_name)
    estimated_tokens = max(4096, len(content) // 2)
    result = call_llm(api_key, sys_prompt, content, max_tokens=estimated_tokens)
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

    # zh-CN writes to root (overwrites source), others to lang subdir
    if lang == "zh-CN":
        dst = output_dir / rel
    else:
        dst = output_dir / lang / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(result, encoding="utf-8")
    save_cache(lang, rel_str, ch, result)

    # For zh-CN: also cache with the NEW root hash so subsequent runs skip it
    if lang == "zh-CN":
        new_hash = _content_hash(result)
        if new_hash != ch:
            save_cache(lang, rel_str, new_hash, result)

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
    generated static pages like mcp/overview
    that are not sourced from PlatformBackend translations."""
    files: list[Path] = []
    for name in ROOT_FILES:
        p = docs_dir / name
        if p.exists():
            files.append(p)

    # Also translate mcp/overview.mdx
    # since it is generated by sync.py (not from PlatformBackend translations)
    for extra in [
        "mcp/overview.mdx",
    ]:
        p = docs_dir / extra
        if p.exists():
            files.append(p)

    return files


def main():
    import argparse

    t0 = time.time()

    parser = argparse.ArgumentParser(
        description="Translate docs from zh-CN to all target languages"
    )
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR)
    parser.add_argument(
        "--languages", nargs="*", default=None, help="Target languages (default: all)"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--root-only",
        action="store_true",
        help="Only translate root MDX files (intro, quickstart, auth). "
        "Use when PlatformBackend translations handle guides/tutorials.",
    )
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("ERROR: ACEDATACLOUD_OPENAI_KEY not set", file=sys.stderr, flush=True)
        sys.exit(1)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    langs = args.languages or ALL_TARGET_LANGUAGES
    print(f"Source: root MDX files (any language)", flush=True)
    print(f"Targets: {', '.join(langs)}", flush=True)
    if "zh-CN" in langs:
        print(f"Note: zh-CN output overwrites root files (default language)", flush=True)

    if args.root_only:
        src_files = collect_root_files(args.output_dir)
    else:
        src_files = collect_source_files(args.output_dir)
    print(f"Source files: {len(src_files)}", flush=True)

    if args.dry_run:
        for f in src_files:
            print(f"  {f.relative_to(args.output_dir)}", flush=True)
        print(
            f"\nWould translate {len(src_files)} files × {len(langs)} languages = {len(src_files) * len(langs)} translations",
            flush=True,
        )
        return

    stats = {"translated": 0, "cached": 0, "failed": 0}
    total = len(src_files) * len(langs)
    done = 0
    llm_calls = 0

    print(
        f"\nTotal: {total} translations ({len(src_files)} files × {len(langs)} languages)",
        flush=True,
    )

    for lang_idx, lang in enumerate(langs):
        lang_t0 = time.time()
        lang_translated = 0
        lang_cached = 0
        print(f"\n{'=' * 40}", flush=True)
        print(
            f"Language {lang_idx + 1}/{len(langs)}: {lang} ({LANGUAGE_NAMES_ZH.get(lang, lang)})",
            flush=True,
        )
        print(f"{'=' * 40}", flush=True)
        for src in src_files:
            done += 1
            rel = src.relative_to(args.output_dir)

            # Check if cached
            content = src.read_text(encoding="utf-8")
            ch = _content_hash(content)
            if get_cached(lang, str(rel), ch):
                # zh-CN writes to root, others to lang subdir
                if lang == "zh-CN":
                    dst = args.output_dir / rel
                else:
                    dst = args.output_dir / lang / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                cached = get_cached(lang, str(rel), ch)
                if cached:
                    dst.write_text(cached, encoding="utf-8")
                stats["cached"] += 1
                lang_cached += 1
                continue

            # For zh-CN: skip if source is already Chinese
            if lang == "zh-CN" and _is_mostly_chinese(content):
                save_cache(lang, str(rel), ch, content)
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
        print(
            f"  {lang} done: {lang_translated} translated, {lang_cached} cached ({lang_dt:.1f}s)",
            flush=True,
        )

    elapsed = time.time() - t0
    print(f"\n{'=' * 40}", flush=True)
    print(f"Translation complete in {elapsed:.1f}s", flush=True)
    print(
        f"  translated={stats['translated']} cached={stats['cached']} failed={stats['failed']}",
        flush=True,
    )
    print(f"  LLM calls={llm_calls}", flush=True)
    print(f"{'=' * 40}", flush=True)


if __name__ == "__main__":
    main()
