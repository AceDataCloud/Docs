#!/usr/bin/env python3
"""
Enhance SEO content with LLM.

Uses Ace Data Cloud's OpenAI-compatible API to improve blog articles,
comparison pages, and use-case tutorials with richer, more natural content.

Usage:
    python scripts/enhance_content.py --content-dir . [--dry-run]

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
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE = "https://api.acedata.cloud/v1"
MODEL = "gpt-4.1-mini"
CACHE_DIR = Path(".cache/enhance")

# Directories to enhance (relative to content root)
ENHANCE_DIRS = ["blog", "comparisons", "use-cases"]

# Skip tutorials — they're code-heavy and don't benefit from LLM rewriting
SKIP_DIRS = ["tutorials"]


def get_api_key() -> str:
    key = os.environ.get("ACEDATACLOUD_OPENAI_KEY", "")
    if not key:
        print("ERROR: ACEDATACLOUD_OPENAI_KEY not set", file=sys.stderr)
        sys.exit(1)
    return key


def call_llm(api_key: str, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    """Call OpenAI-compatible chat completion API."""
    import urllib.request

    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
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


def is_cached(cache_dir: Path, file_path: Path, source_hash: str) -> bool:
    """Check if this file was already enhanced with the same source content."""
    cache_file = cache_dir / f"{file_path.stem}.json"
    if not cache_file.exists():
        return False
    try:
        meta = json.loads(cache_file.read_text())
        return meta.get("source_hash") == source_hash
    except (json.JSONDecodeError, OSError):
        return False


def save_cache(cache_dir: Path, file_path: Path, source_hash: str):
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{file_path.stem}.json"
    cache_file.write_text(json.dumps({"source_hash": source_hash, "file": str(file_path)}))


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from MDX file."""
    if not text.startswith("---"):
        return {}, text
    end = text.index("---", 3)
    fm_text = text[3:end].strip()
    body = text[end + 3:].strip()
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, body


def rebuild_frontmatter(fm: dict, body: str) -> str:
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f'{k}: "{v}"')
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Enhancement prompts per content type
# ---------------------------------------------------------------------------

BLOG_SYSTEM = """You are an expert technical writer for Ace Data Cloud, a unified AI API platform.
Rewrite the following blog article to be more engaging, informative, and SEO-optimized.

Rules:
- Keep the same structure (headings, code blocks, cards, MDX components)
- Keep ALL code examples exactly as-is — do not modify code blocks
- Keep MDX components (<Card>, <CardGroup>, <Steps>, <Note>, etc.) exactly as-is
- Improve the prose: more natural, compelling, technically accurate
- Add more detail about why developers should care
- Keep it factual — Ace Data Cloud is real, api.acedata.cloud is the real endpoint
- Target 800-1200 words total (excluding code blocks)
- Do NOT add any new code blocks or change existing ones
- Do NOT change the frontmatter
- Output ONLY the body content (no frontmatter)"""

COMPARISON_SYSTEM = """You are an expert technical writer comparing AI API services.
Enhance this comparison page with more detailed, fair analysis.

Rules:
- Keep the same MDX structure (tables, headings, code blocks, cards)
- Keep ALL code examples exactly as-is
- Keep MDX components exactly as-is
- Add more specific technical details to comparison aspects
- Be balanced — don't overly favor one service
- Mention that all compared services are available through Ace Data Cloud's unified API
- Keep it factual and up-to-date
- Target 600-1000 words (excluding code blocks)
- Output ONLY the body content (no frontmatter)"""

USE_CASE_SYSTEM = """You are an expert developer advocate writing a tutorial.
Enhance this use-case tutorial to be more practical and thorough.

Rules:
- Keep the same MDX structure (headings, code blocks, steps, cards)
- Keep ALL code examples exactly as-is — do not modify code blocks
- Keep MDX components exactly as-is
- Improve explanations between code blocks
- Add practical tips and common gotchas
- Target 600-1200 words (excluding code blocks)
- Output ONLY the body content (no frontmatter)"""


def get_system_prompt(content_type: str) -> str:
    if content_type == "blog":
        return BLOG_SYSTEM
    elif content_type == "comparisons":
        return COMPARISON_SYSTEM
    elif content_type == "use-cases":
        return USE_CASE_SYSTEM
    return BLOG_SYSTEM


def enhance_file(api_key: str, file_path: Path, content_type: str, dry_run: bool = False) -> bool:
    """Enhance a single MDX file. Returns True if enhanced."""
    text = file_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    h = content_hash(body)

    cache_dir = CACHE_DIR / content_type
    if is_cached(cache_dir, file_path, h):
        return False

    if dry_run:
        print(f"  [dry-run] Would enhance: {file_path}")
        return False

    system = get_system_prompt(content_type)
    try:
        enhanced_body = call_llm(api_key, system, body, max_tokens=4096)
    except Exception as e:
        print(f"  ERROR enhancing {file_path}: {e}", file=sys.stderr)
        return False

    # Sanity check: enhanced body should still have headings
    if "##" not in enhanced_body:
        print(f"  WARNING: LLM output missing headings for {file_path}, skipping")
        return False

    result = rebuild_frontmatter(fm, enhanced_body)
    file_path.write_text(result, encoding="utf-8")
    save_cache(cache_dir, file_path, h)
    return True


def main():
    parser = argparse.ArgumentParser(description="Enhance SEO content with LLM")
    parser.add_argument("--content-dir", default=".", help="Root content directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be enhanced")
    parser.add_argument("--type", choices=["blog", "comparisons", "use-cases"], help="Only enhance specific type")
    args = parser.parse_args()

    root = Path(args.content_dir).resolve()
    api_key = get_api_key()

    dirs = [args.type] if args.type else ENHANCE_DIRS
    total = 0
    enhanced = 0

    for content_type in dirs:
        d = root / content_type
        if not d.exists():
            continue
        for f in sorted(d.glob("*.mdx")):
            total += 1
            if enhance_file(api_key, f, content_type, args.dry_run):
                enhanced += 1
                print(f"  Enhanced: {f.relative_to(root)}")
                time.sleep(1)  # Rate limit courtesy

    print(f"\nDone: {enhanced}/{total} files enhanced")


if __name__ == "__main__":
    main()
