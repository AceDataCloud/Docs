#!/usr/bin/env python3
"""
Enhance Chinese MDX documentation using LLM.

Improves content quality:
- Adds missing sections
- Improves code examples
- Ensures consistent formatting
- Adds SEO-friendly descriptions

Usage:
    python scripts/enhance_content.py [--output-dir .]
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

DOCS_DIR = Path(__file__).parent.parent
API_BASE = "https://api.acedata.cloud/v1"
MODEL = "gpt-4.1-mini"
CACHE_DIR = DOCS_DIR / ".cache" / "enhance"

ENHANCEABLE_DIRS = ["guides"]

SYSTEM_PROMPT = """\
你是 Ace Data Cloud 高级技术文档编辑。优化以下中文 MDX 文档。
规则：
1. 保留原始 frontmatter，可改善 description 使其更 SEO 友好
2. 保留原始结构和大部分内容
3. 修正语法错误和不自然的表述
4. 确保代码示例完整可运行
5. 添加缺失的 <Note>/<Warning> 提示
6. 改善小标题层级（# → ##）
7. 确保所有 API URL 使用 api.acedata.cloud
8. 不改变语言（保持中文）
9. 只输出完整文档（含 frontmatter），不加解释"""


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
    except Exception as e:
        print(f"  LLM ERROR: {e}", file=sys.stderr)
        return ""


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def get_cached(rel_path: str, content_hash: str) -> str | None:
    p = CACHE_DIR / f"{rel_path}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
        if d.get("hash") == content_hash:
            return d.get("content", "")
    except Exception:
        pass
    return None


def save_cache(rel_path: str, content_hash: str, content: str):
    p = CACHE_DIR / f"{rel_path}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"hash": content_hash, "content": content}, ensure_ascii=False)
    )


def enhance_file(api_key: str, filepath: Path, docs_dir: Path) -> bool:
    content = filepath.read_text(encoding="utf-8")
    if not content.strip() or len(content) < 100:
        return False

    rel = str(filepath.relative_to(docs_dir))
    ch = _hash(content)

    cached = get_cached(rel, ch)
    if cached:
        filepath.write_text(cached, encoding="utf-8")
        return True

    result = call_llm(api_key, SYSTEM_PROMPT, content, max_tokens=4096)
    if not result:
        return False

    # Remove code fence wrapper if present
    if result.startswith("```"):
        lines = result.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        result = "\n".join(lines)

    # Verify the result still has frontmatter
    if not result.startswith("---"):
        return False

    filepath.write_text(result, encoding="utf-8")
    save_cache(rel, ch, result)
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Enhance Chinese MDX docs using LLM")
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("ERROR: ACEDATACLOUD_OPENAI_KEY not set", file=sys.stderr)
        sys.exit(1)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []
    for d in ENHANCEABLE_DIRS:
        dp = args.output_dir / d
        if dp.is_dir():
            files.extend(sorted(dp.rglob("*.mdx")))

    print(f"Files to enhance: {len(files)}")

    if args.dry_run:
        for f in files:
            print(f"  {f.relative_to(args.output_dir)}")
        return

    stats = {"enhanced": 0, "cached": 0, "skipped": 0}
    for i, f in enumerate(files, 1):
        rel = f.relative_to(args.output_dir)
        content = f.read_text(encoding="utf-8")
        ch = _hash(content)
        if get_cached(str(rel), ch):
            stats["cached"] += 1
            continue

        print(f"  [{i}/{len(files)}] {rel}")
        if enhance_file(api_key, f, args.output_dir):
            stats["enhanced"] += 1
        else:
            stats["skipped"] += 1
        time.sleep(0.5)

    print(
        f"\nEnhance complete: enhanced={stats['enhanced']} cached={stats['cached']} skipped={stats['skipped']}"
    )


if __name__ == "__main__":
    main()
