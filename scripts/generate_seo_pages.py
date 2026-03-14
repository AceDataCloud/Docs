#!/usr/bin/env python3
"""
LLM-powered SEO page generator for Ace Data Cloud docs.

Generates Chinese (zh-CN) content using the LLM API, then translation scripts
handle converting to English and other languages.

Source of truth: PlatformBackend/cost/service_api_mapping.json
LLM API: api.acedata.cloud with ACEDATACLOUD_OPENAI_KEY

Usage:
    python scripts/generate_seo_pages.py [--backend-dir ../PlatformBackend] [--output-dir .]

Generates:
    - tutorials/<service>/{python,javascript,curl}.mdx  — Chinese quickstarts
    - comparisons/<slug>.mdx                            — Service comparison pages
    - use-cases/<slug>.mdx                              — Use case guides
    - blog/<slug>.mdx                                   — Blog seed articles
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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
CACHE_DIR = DOCS_DIR / ".cache" / "seo"

CATEGORY_ORDER = [
    "AI Chat",
    "AI Image",
    "AI Video",
    "AI Audio",
    "Web Search",
    "CAPTCHA",
    "Identity Verification",
    "Network Proxy",
    "Utility",
]

# ---------------------------------------------------------------------------
# Comparison / Use-case / Blog definitions
# ---------------------------------------------------------------------------

COMPARISONS = [
    {
        "slug": "claude-vs-openai-api",
        "title": "Claude vs OpenAI API 对比",
        "services": ["claude", "openai"],
        "topic": "AI 聊天模型 API",
    },
    {
        "slug": "gemini-vs-deepseek-api",
        "title": "Gemini vs DeepSeek API 对比",
        "services": ["gemini", "deepseek"],
        "topic": "AI 聊天模型 API",
    },
    {
        "slug": "midjourney-vs-flux-api",
        "title": "Midjourney vs Flux API 对比",
        "services": ["midjourney", "flux"],
        "topic": "AI 图像生成 API",
    },
    {
        "slug": "sora-vs-luma-vs-kling-api",
        "title": "Sora vs Luma vs Kling API 对比",
        "services": ["sora", "luma", "kling"],
        "topic": "AI 视频生成 API",
    },
    {
        "slug": "suno-vs-producer-api",
        "title": "Suno vs Producer API 对比",
        "services": ["suno", "producer"],
        "topic": "AI 音乐生成 API",
    },
    {
        "slug": "hailuo-vs-seedance-api",
        "title": "Hailuo vs Seedance API 对比",
        "services": ["hailuo", "seedance"],
        "topic": "AI 视频生成 API",
    },
    {
        "slug": "veo-vs-sora-api",
        "title": "Veo vs Sora API 对比",
        "services": ["veo", "sora"],
        "topic": "AI 视频生成 API",
    },
    {
        "slug": "seedream-vs-midjourney-api",
        "title": "Seedream vs Midjourney API 对比",
        "services": ["seedream", "midjourney"],
        "topic": "AI 图像生成 API",
    },
    {
        "slug": "grok-vs-kimi-api",
        "title": "Grok vs Kimi API 对比",
        "services": ["grok", "kimi"],
        "topic": "AI 聊天模型 API",
    },
]

USE_CASES = [
    {
        "slug": "build-ai-chatbot",
        "title": "构建 AI 聊天机器人",
        "services": ["claude", "openai"],
        "topic": "使用 Claude/OpenAI API 构建多轮对话聊天机器人",
    },
    {
        "slug": "ai-image-generation-app",
        "title": "AI 图像生成应用",
        "services": ["midjourney", "flux", "seedream"],
        "topic": "使用 Midjourney/Flux/Seedream API 构建图像生成应用",
    },
    {
        "slug": "ai-video-generation-pipeline",
        "title": "AI 视频生成流水线",
        "services": ["sora", "luma", "kling"],
        "topic": "使用 Sora/Luma/Kling API 构建视频生成流水线",
    },
    {
        "slug": "ai-music-generation",
        "title": "AI 音乐生成应用",
        "services": ["suno", "producer"],
        "topic": "使用 Suno/Producer API 实现 AI 音乐创作",
    },
    {
        "slug": "web-search-integration",
        "title": "Web 搜索集成",
        "services": ["serp"],
        "topic": "使用 Google Search API (SERP) 为应用添加实时搜索功能",
    },
    {
        "slug": "ai-qr-code-art",
        "title": "AI 艺术二维码",
        "services": ["qrart"],
        "topic": "使用 QR Art API 生成艺术风格二维码",
    },
    {
        "slug": "mcp-server-integration",
        "title": "MCP Server 集成",
        "services": ["suno", "midjourney", "serp"],
        "topic": "将 AI 服务通过 MCP 协议集成到 Cursor/Claude 等编程工具",
    },
    {
        "slug": "build-saas-with-ai-api",
        "title": "基于 AI API 构建 SaaS 产品",
        "services": ["claude", "openai", "midjourney"],
        "topic": "使用 Ace Data Cloud 统一 API 快速搭建 AI SaaS 产品",
    },
]

BLOG_ARTICLES = [
    {
        "slug": "unified-ai-api-platform",
        "title": "为什么选择统一 AI API 平台",
        "topic": "分析使用统一 API 平台（如 Ace Data Cloud）对比直接对接各 AI 厂商 API 的优势",
    },
    {
        "slug": "openai-compatible-api-guide",
        "title": "OpenAI 兼容 API 完全指南",
        "topic": "详解如何通过 OpenAI 兼容接口一次性接入 Claude/Gemini/DeepSeek/Grok 等多种模型",
    },
    {
        "slug": "best-ai-apis-2025",
        "title": "2025 年最佳 AI API 推荐",
        "topic": "盘点 2025 年最值得关注的 AI API：聊天、图像、视频、音乐、搜索等各领域",
    },
    {
        "slug": "ai-video-generation-guide",
        "title": "AI 视频生成 API 入门",
        "topic": "介绍 Sora/Veo/Luma/Kling/Hailuo/Seedance 等视频生成 API 的使用及对比",
    },
    {
        "slug": "suno-music-api-tutorial",
        "title": "Suno 音乐生成 API 教程",
        "topic": "深入讲解如何使用 Suno API 生成定制音乐、填词、分离人声",
    },
    {
        "slug": "midjourney-api-guide",
        "title": "Midjourney API 调用指南",
        "topic": "详解通过 API 调用 Midjourney 进行图像生成、编辑、描述、视频等操作",
    },
    {
        "slug": "mcp-servers-explained",
        "title": "MCP Server 是什么",
        "topic": "解释 Model Context Protocol (MCP) 协议，以及如何使用 MCP Server 连接 AI 工具与 API",
    },
    {
        "slug": "ai-api-pricing-comparison",
        "title": "AI API 价格对比分析",
        "topic": "对比各大 AI API 平台的定价策略，分析 Ace Data Cloud 的按量付费优势",
    },
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
            "temperature": 0.7,
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
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
            dt = time.time() - t0
            print(f"    LLM call: {dt:.1f}s", flush=True)
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as e:
        print(f"    LLM TIMEOUT/NET ERROR after {time.time() - t0:.0f}s: {e}", file=sys.stderr, flush=True)
        return ""
    except Exception as e:
        print(f"    LLM ERROR: {e}", file=sys.stderr, flush=True)
        return ""


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def get_cached(category: str, slug: str, phash: str) -> str | None:
    p = CACHE_DIR / category / f"{slug}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
        if d.get("hash") == phash:
            return d.get("content", "")
    except Exception:
        pass
    return None


def save_cache(category: str, slug: str, phash: str, content: str):
    p = CACHE_DIR / category / f"{slug}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"hash": phash, "content": content}, ensure_ascii=False))


# ===========================================================================
# Service loader
# ===========================================================================


def load_services(backend_dir: Path | None) -> list[dict]:
    if backend_dir:
        f = backend_dir / "cost" / "service_api_mapping.json"
    else:
        f = DOCS_DIR.parent / "PlatformBackend" / "cost" / "service_api_mapping.json"
    if not f.exists():
        print(f"WARNING: {f} not found")
        return []
    return json.loads(f.read_text())


def svc_by_alias(services: list[dict], alias: str) -> dict | None:
    for s in services:
        if s.get("alias") == alias:
            return s
    return None


def display_name(svc: dict) -> str:
    title = svc.get("title", svc.get("alias", ""))
    m = re.match(r"^\$t\(service_title_([^)]+)\)$", title)
    return m.group(1).replace("_", " ").title() if m else title


def first_endpoint(svc: dict) -> tuple[str, str]:
    apis = svc.get("apis", [])
    if apis:
        return apis[0].get("method", "POST"), apis[0].get("path", "")
    return "POST", ""


# ===========================================================================
# Generators
# ===========================================================================

TUTORIAL_SYS = """\
你是 Ace Data Cloud 技术文档作者，生成 MDX 中文教程。
规则：
- 简洁专业的中文，面向开发者
- 代码示例使用 api.acedata.cloud，Bearer Token 认证
- 使用 Mintlify MDX 组件（<Note>, <Steps>, <Step>, <CodeGroup>）
- 只输出正文，不输出 frontmatter
- 包含：简介、安装、基础用法（完整代码）、响应处理、进阶用法、下一步链接"""

COMPARISON_SYS = """\
你是 Ace Data Cloud 技术分析师，生成 MDX 中文对比文章。
规则：
- 客观专业，用表格展示核心差异
- 对比维度：功能、模型、定价、速度、推荐场景
- 所有 API 通过 api.acedata.cloud 调用
- 只输出正文，不输出 frontmatter
- 末尾推荐 Ace Data Cloud 平台"""

USE_CASE_SYS = """\
你是 Ace Data Cloud 解决方案架构师，生成 MDX 中文用例指南。
规则：
- 实战导向，包含完整项目代码
- API 通过 api.acedata.cloud 调用
- 使用 <Steps>, <CodeGroup>, <Note> 等 MDX 组件
- 只输出正文，不输出 frontmatter"""

BLOG_SYS = """\
你是 Ace Data Cloud 博客作者，生成 MDX 中文博客。
规则：
- 有深度且易读，1500-2500 字
- 自然提及 Ace Data Cloud 和 api.acedata.cloud
- 使用 MDX 组件
- 只输出正文，不输出 frontmatter"""


def gen_tutorial(api_key: str, svc: dict, lang: str, out: Path) -> bool:
    alias = svc.get("alias", "")
    name = display_name(svc)
    method, path = first_endpoint(svc)
    apis = svc.get("apis", [])
    api_list = ", ".join(a.get("path", "") for a in apis[:5])
    lang_map = {"python": "Python", "javascript": "JavaScript", "curl": "cURL"}
    lang_d = lang_map.get(lang, lang)

    prompt = f"""为 {name} 服务写 {lang_d} 快速入门。
服务: {name}，分类: {svc.get("category", "")}
主端点: {method} https://api.acedata.cloud{path}
其他端点: {api_list}
按结构生成：简介→前置条件→基础用法→响应处理→进阶→错误处理→下一步（链接 /guides/{alias}/ 和 /api-reference/{alias}/）"""

    ph = _hash(f"tut_{alias}_{lang}_v3")
    content = get_cached("tutorials", f"{alias}_{lang}", ph)
    if not content and api_key:
        print(f"  tutorial: {alias}/{lang}")
        content = call_llm(api_key, TUTORIAL_SYS, prompt, 3000)
        if content:
            save_cache("tutorials", f"{alias}_{lang}", ph, content)
        time.sleep(0.3)
    if not content:
        return _fallback_tutorial(svc, lang, out)

    fm = f"""---
title: "{name} {lang_d} 快速入门"
sidebarTitle: "{lang_d}"
description: "使用 {lang_d} 调用 Ace Data Cloud {name} API 的完整教程"
---

"""
    p = out / "tutorials" / alias / f"{lang}.mdx"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(fm + content, encoding="utf-8")
    return True


def _fallback_tutorial(svc: dict, lang: str, out: Path) -> bool:
    alias = svc.get("alias", "")
    name = display_name(svc)
    method, path = first_endpoint(svc)
    lang_map = {"python": "Python", "javascript": "JavaScript", "curl": "cURL"}
    lang_d = lang_map.get(lang, lang)

    if lang == "python":
        code = f"""```python
import requests

resp = requests.{method.lower()}(
    "https://api.acedata.cloud{path}",
    headers={{"Authorization": "Bearer YOUR_API_TOKEN"}},
    json={{"model": "default"}},
)
print(resp.json())
```"""
    elif lang == "javascript":
        code = f"""```javascript
const resp = await fetch("https://api.acedata.cloud{path}", {{
  method: "{method}",
  headers: {{ Authorization: "Bearer YOUR_API_TOKEN", "Content-Type": "application/json" }},
  body: JSON.stringify({{ model: "default" }}),
}});
console.log(await resp.json());
```"""
    else:
        code = f"""```bash
curl -X {method} "https://api.acedata.cloud{path}" \\
  -H "Authorization: Bearer YOUR_API_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{{"model": "default"}}'
```"""

    mdx = f"""---
title: "{name} {lang_d} 快速入门"
sidebarTitle: "{lang_d}"
description: "使用 {lang_d} 调用 Ace Data Cloud {name} API"
---

## 简介

本教程介绍如何使用 {lang_d} 调用 {name} API。

## 前置条件

1. 在 [platform.acedata.cloud](https://platform.acedata.cloud) 注册并获取 API Token
2. 订阅 {name} 服务

## 基础用法

{code}

## 下一步

- [查看完整指南](/guides/{alias}/)
- [API 参考文档](/api-reference/{alias}/)
"""
    p = out / "tutorials" / alias / f"{lang}.mdx"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(mdx, encoding="utf-8")
    return True


def gen_comparison(api_key: str, comp: dict, services: list[dict], out: Path) -> bool:
    slug = comp["slug"]
    infos = [svc_by_alias(services, a) for a in comp["services"]]
    details = []
    for s, a in zip(infos, comp["services"]):
        if s:
            paths = [api.get("path", "") for api in s.get("apis", [])[:3]]
            details.append(
                f"- {a}: 分类={s.get('category', '')}, 端点: {', '.join(paths)}"
            )
        else:
            details.append(f"- {a}: 未知")

    prompt = f"""写「{comp["title"]}」对比文章。
主题: {comp["topic"]}
服务:\n{chr(10).join(details)}
结构：概述→对比表格→详细分析→场景推荐→Python 代码示例（api.acedata.cloud）→总结"""

    ph = _hash(f"cmp_{slug}_v3")
    content = get_cached("comparisons", slug, ph)
    if not content and api_key:
        print(f"  comparison: {slug}")
        content = call_llm(api_key, COMPARISON_SYS, prompt, 3000)
        if content:
            save_cache("comparisons", slug, ph, content)
        time.sleep(0.3)
    if not content:
        return False

    names = [display_name(s) if s else a for s, a in zip(infos, comp["services"])]
    fm = f"""---
title: "{comp["title"]}"
sidebarTitle: "{" vs ".join(names)}"
description: "{comp["topic"]}：功能、定价、场景全面对比"
---

"""
    p = out / "comparisons" / f"{slug}.mdx"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(fm + content, encoding="utf-8")
    return True


def gen_use_case(api_key: str, uc: dict, services: list[dict], out: Path) -> bool:
    slug = uc["slug"]
    infos = [svc_by_alias(services, a) for a in uc["services"]]
    details = []
    for s, a in zip(infos, uc["services"]):
        if s:
            paths = [api.get("path", "") for api in s.get("apis", [])[:3]]
            details.append(f"- {a}: {', '.join(paths)}")
        else:
            details.append(f"- {a}")

    prompt = f"""写「{uc["title"]}」用例指南。
主题: {uc["topic"]}
服务:\n{chr(10).join(details)}
结构：概述→技术架构→环境准备→分步实现（完整 Python）→测试→优化建议→相关链接"""

    ph = _hash(f"uc_{slug}_v3")
    content = get_cached("use-cases", slug, ph)
    if not content and api_key:
        print(f"  use-case: {slug}")
        content = call_llm(api_key, USE_CASE_SYS, prompt, 3000)
        if content:
            save_cache("use-cases", slug, ph, content)
        time.sleep(0.3)
    if not content:
        return False

    fm = f"""---
title: "{uc["title"]}"
description: "{uc["topic"]}"
---

"""
    p = out / "use-cases" / f"{slug}.mdx"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(fm + content, encoding="utf-8")
    return True


def gen_blog(api_key: str, art: dict, out: Path) -> bool:
    slug = art["slug"]
    prompt = f"""写博客「{art["title"]}」。\n主题: {art["topic"]}\n结构：引言→3-5个要点→代码示例（如适用）→总结"""

    ph = _hash(f"blog_{slug}_v3")
    content = get_cached("blog", slug, ph)
    if not content and api_key:
        print(f"  blog: {slug}")
        content = call_llm(api_key, BLOG_SYS, prompt, 3000)
        if content:
            save_cache("blog", slug, ph, content)
        time.sleep(0.3)
    if not content:
        return False

    fm = f"""---
title: "{art["title"]}"
description: "{art["topic"]}"
---

"""
    p = out / "blog" / f"{slug}.mdx"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(fm + content, encoding="utf-8")
    return True


# ===========================================================================
# Main
# ===========================================================================


def main():
    import argparse

    t0 = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR)
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    out = args.output_dir
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    services = load_services(args.backend_dir)
    api_key = "" if args.no_llm else get_api_key()
    if not api_key and not args.no_llm:
        print("WARNING: ACEDATACLOUD_OPENAI_KEY not set, tutorials use fallback", flush=True)

    tutorial_svcs = [
        s
        for s in services
        if s.get("type") == "Api" and s.get("apis") and not s.get("private")
    ]

    # Calculate totals for progress
    total_tutorials = len(tutorial_svcs) * 3  # 3 languages each
    total_comps = len(COMPARISONS)
    total_ucs = len(USE_CASES)
    total_blogs = len(BLOG_ARTICLES)
    total_all = total_tutorials + total_comps + total_ucs + total_blogs
    done = 0

    stats = {"tutorials": 0, "comparisons": 0, "use_cases": 0, "blog": 0}

    print(f"SEO generation: {total_all} total items ({total_tutorials} tutorials, {total_comps} comparisons, {total_ucs} use-cases, {total_blogs} blog)", flush=True)

    print(f"\n--- Tutorials ({total_tutorials}) ---", flush=True)
    for i, svc in enumerate(tutorial_svcs):
        alias = svc.get("alias", "?")
        for lang in ["python", "javascript", "curl"]:
            done += 1
            if gen_tutorial(api_key, svc, lang, out):
                stats["tutorials"] += 1
        elapsed = time.time() - t0
        print(f"  [{done}/{total_all}] {alias} done ({elapsed:.1f}s)", flush=True)

    print(f"\n--- Comparisons ({total_comps}) ---", flush=True)
    for comp in COMPARISONS:
        done += 1
        t1 = time.time()
        ok = gen_comparison(api_key, comp, services, out)
        dt = time.time() - t1
        status = "OK" if ok else "SKIP"
        print(f"  [{done}/{total_all}] {comp['slug']} → {status} ({dt:.1f}s)", flush=True)
        if ok:
            stats["comparisons"] += 1

    print(f"\n--- Use cases ({total_ucs}) ---", flush=True)
    for uc in USE_CASES:
        done += 1
        t1 = time.time()
        ok = gen_use_case(api_key, uc, services, out)
        dt = time.time() - t1
        status = "OK" if ok else "SKIP"
        print(f"  [{done}/{total_all}] {uc['slug']} → {status} ({dt:.1f}s)", flush=True)
        if ok:
            stats["use_cases"] += 1

    print(f"\n--- Blog ({total_blogs}) ---", flush=True)
    for art in BLOG_ARTICLES:
        done += 1
        t1 = time.time()
        ok = gen_blog(api_key, art, out)
        dt = time.time() - t1
        status = "OK" if ok else "SKIP"
        print(f"  [{done}/{total_all}] {art['slug']} → {status} ({dt:.1f}s)", flush=True)
        if ok:
            stats["blog"] += 1

    elapsed = time.time() - t0
    print(f"\nSEO generation complete in {elapsed:.1f}s: tutorials={stats['tutorials']} comparisons={stats['comparisons']} use-cases={stats['use_cases']} blog={stats['blog']}", flush=True)


if __name__ == "__main__":
    main()
