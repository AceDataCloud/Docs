#!/usr/bin/env python3
"""
Sync script: PlatformBackend → Mintlify Docs

Reads OpenAPI specs, development guides, and other docs from PlatformBackend
and generates a complete Mintlify documentation site in the Docs repo.

Usage:
    python scripts/sync.py --backend-dir ../PlatformBackend --output-dir .
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Service categorization
# ---------------------------------------------------------------------------
SERVICE_CATEGORIES = {
    "AI Chat": {
        "icon": "comments",
        "services": ["claude", "openai", "gemini", "deepseek", "grok", "kimi"],
    },
    "AI Image": {
        "icon": "image",
        "services": ["midjourney", "flux", "seedream", "nano-banana", "qrart", "face", "headshots"],
    },
    "AI Video": {
        "icon": "video",
        "services": ["sora", "veo", "luma", "kling", "hailuo", "seedance", "wan", "pika", "pixverse"],
    },
    "AI Audio": {
        "icon": "music",
        "services": ["suno", "fish", "producer", "riffusion", "udio"],
    },
    "Web & Data": {
        "icon": "globe",
        "services": ["serp", "localization", "shorturl", "aichat"],
    },
    "CAPTCHA": {
        "icon": "shield-halved",
        "services": ["recaptcha", "hcaptcha", "image2text"],
    },
    "Identity": {
        "icon": "id-card",
        "services": ["identity"],
    },
    "Proxy": {
        "icon": "network-wired",
        "services": ["global-rotating-proxy", "adsl", "adsl-http-proxy", "cellular-rotating-proxy"],
    },
}

# Map service alias → human-readable name
SERVICE_NAMES = {
    "claude": "Claude",
    "openai": "OpenAI",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
    "grok": "Grok",
    "kimi": "Kimi",
    "midjourney": "Midjourney",
    "flux": "Flux",
    "seedream": "Seedream",
    "nano-banana": "Nano Banana",
    "qrart": "QR Art",
    "face": "Face",
    "headshots": "Headshots",
    "sora": "Sora",
    "veo": "Veo",
    "luma": "Luma",
    "kling": "Kling",
    "hailuo": "Hailuo",
    "seedance": "Seedance",
    "wan": "Wan",
    "pika": "Pika",
    "pixverse": "Pixverse",
    "suno": "Suno",
    "fish": "Fish Audio",
    "producer": "Producer",
    "riffusion": "Riffusion",
    "udio": "Udio",
    "serp": "Google Search",
    "localization": "Localization",
    "shorturl": "Short URL",
    "aichat": "AI Chat Widget",
    "recaptcha": "reCAPTCHA",
    "hcaptcha": "hCaptcha",
    "image2text": "Image2Text",
    "identity": "Identity Verification",
    "global-rotating-proxy": "Global Rotating Proxy",
    "adsl": "ADSL Rotating Proxy",
    "adsl-http-proxy": "ADSL HTTP Proxy",
    "cellular-rotating-proxy": "Cellular Rotating Proxy",
}

# Map development doc key → service alias
DEV_DOC_SERVICE_MAP = {
    "claude_chat_completions": "claude",
    "claude_messages": "claude",
    "claude_messages_count_tokens": "claude",
    "claude_code": "claude",
    "claude_code_desktop": "claude",
    "claude_code_github_actions": "claude",
    "claude_code_jetbrains": "claude",
    "claude_code_terminal": "claude",
    "claude_code_vscode": "claude",
    "openai_chat_completions": "openai",
    "openai_chat_completions_4o_image": "openai",
    "openai_embeddings": "openai",
    "openai_images_generations": "openai",
    "openai_images_edits": "openai",
    "openai_responses": "openai",
    "gemini_chat_completions": "gemini",
    "deepseek_chat_completions": "deepseek",
    "grok_chat_completions": "grok",
    "kimi_chat_completions": "kimi",
    "midjourney_imagine": "midjourney",
    "midjourney_edits": "midjourney",
    "midjourney_describe": "midjourney",
    "midjourney_translate": "midjourney",
    "midjourney_videos": "midjourney",
    "midjourney_tasks": "midjourney",
    "flux_images": "flux",
    "flux_tasks": "flux",
    "seedream_images": "seedream",
    "seedream_tasks": "seedream",
    "nanobanana_images": "nano-banana",
    "nanobanana_tasks": "nano-banana",
    "qrart_generate": "qrart",
    "qrart_tasks": "qrart",
    "face_analyze": "face",
    "face_beautify": "face",
    "face_cartoon": "face",
    "face_change_age": "face",
    "face_change_gender": "face",
    "face_detect_live": "face",
    "face_swap": "face",
    "headshots_generation": "headshots",
    "headshots_tasks": "headshots",
    "sora_videos": "sora",
    "sora_tasks": "sora",
    "veo_videos": "veo",
    "veo_tasks": "veo",
    "luma_videos": "luma",
    "luma_tasks": "luma",
    "kling_videos": "kling",
    "kling_motion": "kling",
    "kling_tasks": "kling",
    "hailuo_videos": "hailuo",
    "hailuo_tasks": "hailuo",
    "seedance_videos": "seedance",
    "seedance_tasks": "seedance",
    "wan_videos": "wan",
    "wan_tasks": "wan",
    "pika_videos": "pika",
    "pika_tasks": "pika",
    "pixverse_videos": "pixverse",
    "pixverse_character": "pixverse",
    "pixverse_tasks": "pixverse",
    "suno_audios": "suno",
    "suno_persona": "suno",
    "suno_mp4": "suno",
    "suno_timing": "suno",
    "suno_vox": "suno",
    "suno_wav": "suno",
    "suno_midi": "suno",
    "suno_style": "suno",
    "suno_lyrics": "suno",
    "suno_mashup_lyrics": "suno",
    "suno_tasks": "suno",
    "suno_upload": "suno",
    "fish_audios": "fish",
    "fish_voices": "fish",
    "fish_tasks": "fish",
    "producer_audios": "producer",
    "producer_videos": "producer",
    "producer_upload": "producer",
    "producer_wav": "producer",
    "producer_tasks": "producer",
    "producer_lyrics": "producer",
    "riffusion_audios": "riffusion",
    "riffusion_tasks": "riffusion",
    "riffusion_upload": "riffusion",
    "udio_audios": "udio",
    "udio_tasks": "udio",
    "serp_google": "serp",
    "localization_translation": "localization",
    "short_url": "shorturl",
    "aichat_conversations": "aichat",
    "captcha_recognition_recaptcha2": "recaptcha",
    "captcha_token_recaptcha2": "recaptcha",
    "captcha_token_recaptcha3": "recaptcha",
    "captcha_recognition_hcaptcha": "hcaptcha",
    "captcha_token_hcaptcha": "hcaptcha",
    "captcha_recognition_image2text": "image2text",
    "identity_bankcard_check-1e": "identity",
    "identity_bankcard_check-2e": "identity",
    "identity_bankcard_check-3e": "identity",
    "identity_bankcard_check-4e": "identity",
    "identity_idcard_check-1e": "identity",
    "identity_idcard_check-2e": "identity",
    "identity_idcard_ocr": "identity",
    "identity_phone_check-1e": "identity",
    "identity_phone_check-2e": "identity",
    "identity_phone_check-3e": "identity",
    "adsl_extract_proxy": "adsl-http-proxy",
    "adsl_rotating_proxy": "adsl",
    "global_rotating_proxy": "global-rotating-proxy",
    "cellular_rotating_proxy": "cellular-rotating-proxy",
    "acedataext": None,  # skip
    "application_remaining_amount": None,  # platform internal
    "nexior_vercel_deployment": None,  # platform internal
    "tw_comments": None,  # skip
    "tw_posts": None,  # skip
    "tw_users": None,  # skip
}


def load_service_mapping(backend_dir: Path) -> list[dict]:
    """Load service_api_mapping.json from PlatformBackend."""
    path = backend_dir / "cost" / "service_api_mapping.json"
    with open(path) as f:
        return json.load(f)


def load_openapi_spec(backend_dir: Path, api_id: str) -> dict | None:
    """Load a single OpenAPI spec file."""
    path = backend_dir / "openapi" / f"{api_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def resolve_t_keys(obj):
    """Replace $t(key) translation markers with the key itself as a readable title."""
    if isinstance(obj, str):
        return re.sub(r'\$t\(([^)]+)\)', lambda m: m.group(1).replace('_', ' ').title(), obj)
    if isinstance(obj, dict):
        return {k: resolve_t_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_t_keys(item) for item in obj]
    return obj


def merge_openapi_specs(backend_dir: Path, service: dict) -> dict | None:
    """Merge multiple per-API OpenAPI specs into one per-service spec."""
    apis = service.get("apis", [])
    if not apis:
        return None

    merged = {
        "openapi": "3.0.0",
        "info": {
            "title": SERVICE_NAMES.get(service.get("alias", ""), service.get("alias", "API")),
            "version": "1.0.0",
            "description": f"API reference for {SERVICE_NAMES.get(service.get('alias', ''), service.get('alias', ''))} on Ace Data Cloud.",
        },
        "servers": [
            {
                "url": "https://api.acedata.cloud",
                "description": "Ace Data Cloud API",
            }
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "API token from https://platform.acedata.cloud",
                }
            }
        },
        "security": [{"bearerAuth": []}],
        "paths": {},
    }

    for api in apis:
        spec = load_openapi_spec(backend_dir, api["id"])
        if not spec:
            continue
        for path, methods in spec.get("paths", {}).items():
            merged["paths"][path] = methods
        # Merge component schemas if any
        for key in ("schemas", "requestBodies", "responses"):
            if key in spec.get("components", {}):
                merged["components"].setdefault(key, {}).update(spec["components"][key])

    if not merged["paths"]:
        return None

    # Resolve translation keys
    merged = resolve_t_keys(merged)
    return merged


def convert_dev_doc_to_mdx(content: str, doc_key: str, service_alias: str) -> str:
    """Convert a PlatformBackend development markdown doc to Mintlify MDX format."""
    # Extract a title from the first heading or generate one
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = doc_key.replace("_", " ").title()

    # Clean up the content
    # Remove the first h1 if we extracted it
    if title_match:
        content = content[:title_match.start()] + content[title_match.end():]

    # Replace image references that use platform URLs with relative paths
    content = re.sub(
        r'!\[([^\]]*)\]\(https://cdn\.acedata\.cloud/([^)]+)\)',
        r'![\1](https://cdn.acedata.cloud/\2)',
        content,
    )

    # Replace $t() references
    content = re.sub(r'\$t\(([^)]+)\)', lambda m: m.group(1).replace('_', ' ').title(), content)

    # Build frontmatter
    service_name = SERVICE_NAMES.get(service_alias, service_alias)
    frontmatter = f"""---
title: "{title}"
description: "Integration guide for {service_name} on Ace Data Cloud"
---

"""
    return frontmatter + content.strip() + "\n"


def generate_mcp_doc(content: str, mcp_name: str) -> str:
    """Convert MCP doc to MDX."""
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else f"MCP {mcp_name}"
    if title_match:
        content = content[:title_match.start()] + content[title_match.end():]
    content = re.sub(r'\$t\(([^)]+)\)', lambda m: m.group(1).replace('_', ' ').title(), content)

    return f"""---
title: "{title}"
description: "MCP server for {mcp_name} integration"
---

{content.strip()}
"""


def generate_extra_doc(content: str, doc_key: str) -> str:
    """Convert extra docs (privacy, terms, etc.) to MDX."""
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else doc_key.replace('_', ' ').title()
    if title_match:
        content = content[:title_match.start()] + content[title_match.end():]
    content = re.sub(r'\$t\(([^)]+)\)', lambda m: m.group(1).replace('_', ' ').title(), content)

    return f"""---
title: "{title}"
---

{content.strip()}
"""


def build_navigation(service_map: dict, dev_docs_by_service: dict, output_dir: Path) -> dict:
    """Build the Mintlify navigation structure."""
    tabs = []

    # Tab 1: Guides (Getting Started + Integration Guides by category)
    guide_groups = [
        {
            "group": "Getting Started",
            "pages": ["introduction", "quickstart", "authentication"],
        }
    ]

    # Integration guides by category
    for cat_name, cat_info in SERVICE_CATEGORIES.items():
        pages = []
        for svc_alias in cat_info["services"]:
            if svc_alias in dev_docs_by_service:
                docs = dev_docs_by_service[svc_alias]
                if len(docs) == 1:
                    pages.append(f"guides/{svc_alias}/{docs[0]}")
                else:
                    svc_pages = [f"guides/{svc_alias}/{d}" for d in docs]
                    pages.append({
                        "group": SERVICE_NAMES.get(svc_alias, svc_alias),
                        "pages": svc_pages,
                    })
        if pages:
            guide_groups.append({
                "group": cat_name,
                "icon": cat_info["icon"],
                "pages": pages,
            })

    # X402 and other special guides
    special_pages = []
    if (output_dir / "guides" / "x402.mdx").exists():
        special_pages.append("guides/x402")
    if special_pages:
        guide_groups.append({
            "group": "Advanced",
            "pages": special_pages,
        })

    tabs.append({
        "tab": "Guides",
        "groups": guide_groups,
    })

    # Tab 2: API Reference (auto-populated from OpenAPI per service category)
    api_groups = [
        {
            "group": "Overview",
            "pages": ["api-reference/introduction"],
        }
    ]
    for cat_name, cat_info in SERVICE_CATEGORIES.items():
        cat_pages = []
        for svc_alias in cat_info["services"]:
            openapi_path = f"openapi/{svc_alias}.json"
            if (output_dir / openapi_path).exists():
                cat_pages.append({
                    "group": SERVICE_NAMES.get(svc_alias, svc_alias),
                    "openapi": {
                        "source": f"/{openapi_path}",
                        "directory": f"api-reference/{svc_alias}",
                    },
                })
        if cat_pages:
            api_groups.extend(cat_pages)

    tabs.append({
        "tab": "API Reference",
        "groups": api_groups,
    })

    # Tab 3: MCP Servers
    mcp_pages = []
    mcp_dir = output_dir / "mcp"
    if mcp_dir.exists():
        for f in sorted(mcp_dir.iterdir()):
            if f.suffix == ".mdx":
                mcp_pages.append(f"mcp/{f.stem}")
    if mcp_pages:
        tabs.append({
            "tab": "MCP Servers",
            "groups": [
                {
                    "group": "MCP Servers",
                    "pages": ["mcp/overview"] + mcp_pages if (output_dir / "mcp" / "overview.mdx").exists() else mcp_pages,
                }
            ],
        })

    # Tab 4: Resources
    resource_pages = []
    if (output_dir / "resources" / "privacy.mdx").exists():
        resource_pages.append("resources/privacy")
    if (output_dir / "resources" / "terms.mdx").exists():
        resource_pages.append("resources/terms")
    if (output_dir / "resources" / "support.mdx").exists():
        resource_pages.append("resources/support")
    if resource_pages:
        tabs.append({
            "tab": "Resources",
            "groups": [{"group": "Resources", "pages": resource_pages}],
        })

    return {
        "tabs": tabs,
        "global": {
            "anchors": [
                {
                    "anchor": "Platform",
                    "href": "https://platform.acedata.cloud",
                    "icon": "browser",
                },
                {
                    "anchor": "API Status",
                    "href": "https://status.acedata.cloud",
                    "icon": "signal",
                },
            ]
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Sync PlatformBackend docs to Mintlify")
    parser.add_argument("--backend-dir", required=True, help="Path to PlatformBackend")
    parser.add_argument("--output-dir", required=True, help="Path to Docs repo root")
    args = parser.parse_args()

    backend_dir = Path(args.backend_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    print(f"Backend: {backend_dir}")
    print(f"Output:  {output_dir}")

    # Load service mapping
    services = load_service_mapping(backend_dir)
    service_by_alias = {}

    # Map $t(service_title_*) patterns to aliases for services without explicit alias
    T_TITLE_TO_ALIAS = {
        "service_title_deepseek": "deepseek",
        "service_title_face_change": "face",
        "service_title_identity": "identity",
        "service_title_qrart": "qrart",
        "service_title_shorturl": "shorturl",
        "service_title_aichat": "aichat",
        "service_title_image2text": "image2text",
        "service_title_global_rotating_proxy": "global-rotating-proxy",
        "service_title_adsl_http_proxy": "adsl-http-proxy",
        "service_title_cellular_rotating_proxy": "cellular-rotating-proxy",
        "service_title_localization": "localization",
    }

    for svc in services:
        if svc.get("private"):
            continue
        alias = svc.get("alias")
        if not alias:
            # Try to derive alias from $t() title
            title = svc.get("title", "")
            m = re.match(r'^\$t\(([^)]+)\)$', title)
            if m:
                alias = T_TITLE_TO_ALIAS.get(m.group(1))
        if alias:
            service_by_alias[alias] = svc

    # ---------------------------------------------------------------------------
    # 1. Generate merged OpenAPI specs per service
    # ---------------------------------------------------------------------------
    openapi_dir = output_dir / "openapi"
    openapi_dir.mkdir(parents=True, exist_ok=True)

    generated_specs = set()
    for alias, svc in service_by_alias.items():
        if svc.get("type") != "Api":
            continue
        spec = merge_openapi_specs(backend_dir, svc)
        if spec:
            out_path = openapi_dir / f"{alias}.json"
            with open(out_path, "w") as f:
                json.dump(spec, f, indent=2, ensure_ascii=False)
            generated_specs.add(alias)
            print(f"  OpenAPI: {alias} ({len(spec['paths'])} endpoints)")

    print(f"Generated {len(generated_specs)} OpenAPI specs")

    # ---------------------------------------------------------------------------
    # 2. Convert development guides to MDX
    # ---------------------------------------------------------------------------
    guides_dir = output_dir / "guides"
    # Clean old guides
    if guides_dir.exists():
        shutil.rmtree(guides_dir)
    guides_dir.mkdir(parents=True, exist_ok=True)

    dev_docs_by_service: dict[str, list[str]] = {}  # alias → [doc_key, ...]
    docs_dir = backend_dir / "docs"

    for md_file in sorted(docs_dir.glob("development_*.md")):
        doc_key = md_file.stem.removeprefix("development_")
        service_alias = DEV_DOC_SERVICE_MAP.get(doc_key)
        if service_alias is None:
            continue  # skip unmapped docs

        content = md_file.read_text(encoding="utf-8")
        mdx_content = convert_dev_doc_to_mdx(content, doc_key, service_alias)

        svc_dir = guides_dir / service_alias
        svc_dir.mkdir(parents=True, exist_ok=True)
        out_path = svc_dir / f"{doc_key}.mdx"
        out_path.write_text(mdx_content, encoding="utf-8")

        dev_docs_by_service.setdefault(service_alias, []).append(doc_key)

    print(f"Generated {sum(len(v) for v in dev_docs_by_service.values())} guide pages across {len(dev_docs_by_service)} services")

    # ---------------------------------------------------------------------------
    # 3. MCP docs
    # ---------------------------------------------------------------------------
    mcp_dir = output_dir / "mcp"
    if mcp_dir.exists():
        shutil.rmtree(mcp_dir)
    mcp_dir.mkdir(parents=True, exist_ok=True)

    mcp_count = 0
    for md_file in sorted(docs_dir.glob("mcp_*.md")):
        mcp_name = md_file.stem.removeprefix("mcp_")
        content = md_file.read_text(encoding="utf-8")
        mdx_content = generate_mcp_doc(content, mcp_name)
        out_path = mcp_dir / f"{mcp_name}.mdx"
        out_path.write_text(mdx_content, encoding="utf-8")
        mcp_count += 1

    # MCP overview page
    mcp_overview = """---
title: "MCP Servers"
description: "Model Context Protocol servers for AI tool integration"
---

Ace Data Cloud provides MCP (Model Context Protocol) servers that allow AI assistants like Claude, Cursor, and Windsurf to directly use our APIs.

<CardGroup cols={2}>
  <Card title="Suno" icon="music" href="/mcp/suno">
    AI music generation
  </Card>
  <Card title="Midjourney" icon="image" href="/mcp/midjourney">
    AI image generation
  </Card>
  <Card title="SERP" icon="magnifying-glass" href="/mcp/serp">
    Google search
  </Card>
  <Card title="Luma" icon="video" href="/mcp/luma">
    AI video generation
  </Card>
  <Card title="Sora" icon="film" href="/mcp/sora">
    OpenAI video generation
  </Card>
  <Card title="Veo" icon="camera-movie" href="/mcp/veo">
    Google video generation
  </Card>
  <Card title="Nano Banana" icon="wand-magic-sparkles" href="/mcp/nanobanana">
    Gemini image generation
  </Card>
</CardGroup>
"""
    (mcp_dir / "overview.mdx").write_text(mcp_overview, encoding="utf-8")
    print(f"Generated {mcp_count} MCP pages")

    # ---------------------------------------------------------------------------
    # 4. Extra docs (privacy, terms, support, x402, etc.)
    # ---------------------------------------------------------------------------
    resources_dir = output_dir / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    extra_docs = {
        "privacy": "resources/privacy.mdx",
        "terms": "resources/terms.mdx",
        "support": "resources/support.mdx",
    }
    for doc_key, out_rel in extra_docs.items():
        src = docs_dir / f"{doc_key}.md"
        if src.exists():
            content = src.read_text(encoding="utf-8")
            mdx = generate_extra_doc(content, doc_key)
            (output_dir / out_rel).write_text(mdx, encoding="utf-8")

    # X402 guide
    x402_src = docs_dir / "x402_integration_guide.md"
    if x402_src.exists():
        content = x402_src.read_text(encoding="utf-8")
        mdx = convert_dev_doc_to_mdx(content, "x402_integration_guide", "x402")
        (guides_dir / "x402.mdx").write_text(mdx, encoding="utf-8")

    # ---------------------------------------------------------------------------
    # 5. Generate static pages
    # ---------------------------------------------------------------------------

    # Introduction page
    intro = """---
title: "Introduction"
description: "Ace Data Cloud provides unified APIs for AI services including LLMs, image generation, video generation, music generation, web search, and more."
---

## What is Ace Data Cloud?

Ace Data Cloud is a unified API platform that provides access to the world's leading AI services through a single API key and consistent interface.

<CardGroup cols={2}>
  <Card title="AI Chat" icon="comments" href="/guides/claude/claude_chat_completions">
    Access Claude, GPT, Gemini, DeepSeek, Grok, and Kimi through OpenAI-compatible endpoints.
  </Card>
  <Card title="AI Image" icon="image" href="/guides/midjourney/midjourney_imagine">
    Generate images with Midjourney, Flux, DALL·E, Seedream, and more.
  </Card>
  <Card title="AI Video" icon="video" href="/guides/sora/sora_videos">
    Create videos with Sora, Veo, Luma, Kling, Hailuo, and Seedance.
  </Card>
  <Card title="AI Audio" icon="music" href="/guides/suno/suno_audios">
    Generate music and audio with Suno, Fish Audio, and Producer.
  </Card>
</CardGroup>

## Key Features

- **Unified API** — One API key for 50+ AI services
- **OpenAI Compatible** — Drop-in replacement for ChatGPT, Claude, Gemini
- **Interactive Playground** — Test every API directly in the docs
- **Pay-as-you-go** — No subscriptions, only pay for what you use
- **MCP Servers** — Native integration with AI coding assistants

## Quick Links

<CardGroup cols={3}>
  <Card title="Get API Key" icon="key" href="https://platform.acedata.cloud">
    Sign up and get your API token
  </Card>
  <Card title="API Reference" icon="code" href="/api-reference/introduction">
    Interactive API documentation
  </Card>
  <Card title="MCP Servers" icon="plug" href="/mcp/overview">
    Connect AI assistants to our APIs
  </Card>
</CardGroup>
"""
    (output_dir / "introduction.mdx").write_text(intro, encoding="utf-8")

    # Quickstart page
    quickstart = """---
title: "Quickstart"
description: "Get started with Ace Data Cloud APIs in 5 minutes"
---

## 1. Get Your API Key

Sign up at [platform.acedata.cloud](https://platform.acedata.cloud) and create an API credential.

<Steps>
  <Step title="Create an Account">
    Visit [platform.acedata.cloud](https://platform.acedata.cloud) and sign up.
  </Step>
  <Step title="Subscribe to a Service">
    Browse available services and click **Acquire** to subscribe. Most services offer free credits to start.
  </Step>
  <Step title="Create a Credential">
    Go to your service's **Credentials** section and create a new API token.
  </Step>
</Steps>

## 2. Make Your First Request

All APIs use Bearer token authentication:

<CodeGroup>

```bash cURL
curl -X POST https://api.acedata.cloud/v1/chat/completions \\
  -H "Authorization: Bearer YOUR_API_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

```python Python
import requests

response = requests.post(
    "https://api.acedata.cloud/v1/chat/completions",
    headers={"Authorization": "Bearer YOUR_API_TOKEN"},
    json={
        "model": "claude-sonnet-4-20250514",
        "messages": [{"role": "user", "content": "Hello!"}],
    },
)
print(response.json())
```

```javascript JavaScript
const response = await fetch("https://api.acedata.cloud/v1/chat/completions", {
  method: "POST",
  headers: {
    Authorization: "Bearer YOUR_API_TOKEN",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "claude-sonnet-4-20250514",
    messages: [{ role: "user", content: "Hello!" }],
  }),
});
const data = await response.json();
console.log(data);
```

</CodeGroup>

## 3. Explore the APIs

<CardGroup cols={2}>
  <Card title="API Reference" icon="code" href="/api-reference/introduction">
    Browse and test all endpoints interactively
  </Card>
  <Card title="Integration Guides" icon="book" href="/guides/claude/claude_chat_completions">
    Step-by-step tutorials for each service
  </Card>
</CardGroup>
"""
    (output_dir / "quickstart.mdx").write_text(quickstart, encoding="utf-8")

    # Authentication page
    auth_page = """---
title: "Authentication"
description: "How to authenticate with Ace Data Cloud APIs"
---

All Ace Data Cloud APIs use **Bearer token** authentication.

## Getting Your Token

1. Sign up at [platform.acedata.cloud](https://platform.acedata.cloud)
2. Subscribe to the services you need
3. Create a credential (API token) for each service

## Using Your Token

Include the token in the `Authorization` header of every request:

```bash
Authorization: Bearer YOUR_API_TOKEN
```

<Note>
  Each token is tied to a specific service subscription. Use different tokens for different services, or create a **Global** credential that works across all your subscriptions.
</Note>

## Rate Limits

Rate limits vary by service and subscription tier. If you exceed the limit, the API returns `429 Too Many Requests`.

## Security Best Practices

- Never expose your API token in client-side code
- Use environment variables to store tokens
- Rotate tokens periodically
- Use separate tokens for development and production
"""
    (output_dir / "authentication.mdx").write_text(auth_page, encoding="utf-8")

    # API Reference introduction
    api_ref_dir = output_dir / "api-reference"
    api_ref_dir.mkdir(parents=True, exist_ok=True)
    api_intro = """---
title: "API Reference"
description: "Interactive API reference for all Ace Data Cloud services"
---

## Base URL

All API endpoints are served from:

```
https://api.acedata.cloud
```

## Authentication

All endpoints require Bearer token authentication:

```
Authorization: Bearer YOUR_API_TOKEN
```

## Try It Out

Every endpoint in this reference includes an interactive playground. Enter your API token and test requests directly from the browser.

<Note>
  Get your API token at [platform.acedata.cloud](https://platform.acedata.cloud).
</Note>

## Services

Browse APIs by category:

<CardGroup cols={2}>
  <Card title="AI Chat" icon="comments">
    Claude, OpenAI, Gemini, DeepSeek, Grok, Kimi — OpenAI-compatible chat completions
  </Card>
  <Card title="AI Image" icon="image">
    Midjourney, Flux, Seedream, DALL·E, QR Art, Face tools
  </Card>
  <Card title="AI Video" icon="video">
    Sora, Veo, Luma, Kling, Hailuo, Seedance, Wan, Pika
  </Card>
  <Card title="AI Audio" icon="music">
    Suno, Fish Audio, Producer, Riffusion, Udio
  </Card>
</CardGroup>
"""
    (api_ref_dir / "introduction.mdx").write_text(api_intro, encoding="utf-8")

    # ---------------------------------------------------------------------------
    # 6. Generate docs.json
    # ---------------------------------------------------------------------------
    navigation = build_navigation(service_by_alias, dev_docs_by_service, output_dir)

    docs_json = {
        "$schema": "https://mintlify.com/docs.json",
        "theme": "mint",
        "name": "Ace Data Cloud",
        "description": "Unified API platform for AI services — LLMs, image generation, video generation, music, search, and more.",
        "colors": {
            "primary": "#6366F1",
            "light": "#818CF8",
            "dark": "#4F46E5",
        },
        "favicon": "/favicon.svg",
        "logo": {
            "light": "/logo/light.svg",
            "dark": "/logo/dark.svg",
            "href": "https://acedata.cloud",
        },
        "navbar": {
            "links": [
                {"type": "github", "href": "https://github.com/AceDataCloud"},
                {"label": "Platform", "href": "https://platform.acedata.cloud"},
            ],
            "primary": {
                "type": "button",
                "label": "Get API Key",
                "href": "https://platform.acedata.cloud",
            },
        },
        "navigation": navigation,
        "footer": {
            "socials": {
                "github": "https://github.com/AceDataCloud",
                "x": "https://x.com/AceDataCloud",
            },
        },
        "api": {
            "playground": {"mode": "simple"},
            "auth": {
                "method": "bearer",
                "name": "Authorization",
            },
        },
        "variables": {
            "BASE_URL": "https://api.acedata.cloud",
        },
    }

    with open(output_dir / "docs.json", "w") as f:
        json.dump(docs_json, f, indent=2, ensure_ascii=False)
    print("Generated docs.json")

    # ---------------------------------------------------------------------------
    # 7. Cleanup: remove old starter template files
    # ---------------------------------------------------------------------------
    starter_files = [
        "development.mdx",
        "essentials/settings.mdx",
        "essentials/markdown.mdx",
        "essentials/code.mdx",
        "essentials/navigation.mdx",
        "essentials/images.mdx",
        "essentials/reusable-snippets.mdx",
        "ai-tools/cursor.mdx",
        "ai-tools/claude-code.mdx",
        "ai-tools/windsurf.mdx",
        "snippets/snippet-intro.mdx",
        "api-reference/openapi.json",
        "api-reference/endpoint/create.mdx",
        "api-reference/endpoint/get.mdx",
        "api-reference/endpoint/delete.mdx",
        "api-reference/endpoint/webhook.mdx",
        "index.mdx",
    ]
    for f in starter_files:
        p = output_dir / f
        if p.exists():
            p.unlink()
            print(f"  Removed starter file: {f}")

    # Remove empty dirs
    for d in ["essentials", "ai-tools", "snippets", "api-reference/endpoint"]:
        dp = output_dir / d
        if dp.exists() and not any(dp.iterdir()):
            dp.rmdir()

    print("\nSync complete!")
    print(f"  OpenAPI specs: {len(generated_specs)}")
    print(f"  Guide pages:   {sum(len(v) for v in dev_docs_by_service.values())}")
    print(f"  MCP pages:     {mcp_count}")


if __name__ == "__main__":
    main()
