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
import os
import re
import shutil
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config: display order + icons for categories, docs to skip.
# Everything else is data-driven from service_api_mapping.json.
# ---------------------------------------------------------------------------
CATEGORY_ORDER = [
    "AI Chat",
    "AI Image",
    "AI Video",
    "AI Audio",
    "Web & Data",
    "CAPTCHA",
    "Identity",
    "Proxy",
]

CATEGORY_ICONS: dict[str, str] = {
    "AI Chat": "comments",
    "AI Image": "image",
    "AI Video": "video",
    "AI Audio": "music",
    "Web & Data": "globe",
    "CAPTCHA": "shield-halved",
    "Identity": "id-card",
    "Proxy": "network-wired",
}

# Doc keys that should never appear in the docs site.
SKIP_DOC_KEYS = {
    "acedataext",
    "application_remaining_amount",
    "nexior_vercel_deployment",
    "acedatacloud_chat_api_integration_article",
    "tw_comments",
    "tw_posts",
    "tw_users",
    # Private services without public documentation yet
    "pika_tasks",
    "pika_videos",
    "pixverse_character",
    "pixverse_tasks",
    "pixverse_videos",
    "riffusion_audios",
    "riffusion_tasks",
    "riffusion_upload",
    "udio_audios",
    "udio_tasks",
}

# Private services to exclude entirely from docs (OpenAPI + guides).
EXCLUDE_FROM_DOCS: set[str] = {
    "pika",
    "pixverse",
    "riffusion",
    "udio",
    "chatdoc",
}


def _normalize(s: str) -> str:
    """Normalize for fuzzy matching: lowercase, strip hyphens and underscores."""
    return s.lower().replace("-", "").replace("_", "")


def build_service_names(service_by_alias: dict[str, dict]) -> dict[str, str]:
    """Build alias → display_name map from enriched mapping data."""
    names: dict[str, str] = {}
    for alias, svc in service_by_alias.items():
        # Prefer display_name from enriched mapping, fall back to alias title-case
        names[alias] = (
            svc.get("display_name") or alias.replace("-", " ").replace("_", " ").title()
        )
    return names


def build_categories(
    service_by_alias: dict[str, dict],
) -> dict[str, dict]:
    """
    Build category → {icon, services} from the mapping's ``category`` field.
    Returns categories in CATEGORY_ORDER, with any extras appended.
    """
    cat_services: dict[str, list[str]] = {}  # category name → [alias, ...]
    for alias, svc in service_by_alias.items():
        cat = svc.get("category")
        if not cat:
            continue
        cat_services.setdefault(cat, []).append(alias)

    # Sort services within each category by rank (lower = first)
    for cat, aliases in cat_services.items():
        aliases.sort(key=lambda a: service_by_alias[a].get("rank", 0))

    ordered: dict[str, dict] = {}
    for cat_name in CATEGORY_ORDER:
        if cat_name in cat_services:
            ordered[cat_name] = {
                "icon": CATEGORY_ICONS.get(cat_name, "circle"),
                "services": cat_services.pop(cat_name),
            }
    # Append any new categories not yet in CATEGORY_ORDER
    for cat_name, aliases in sorted(cat_services.items()):
        ordered[cat_name] = {
            "icon": CATEGORY_ICONS.get(cat_name, "circle"),
            "services": aliases,
        }
    return ordered


def build_doc_service_map(
    service_by_alias: dict[str, dict], backend_dir: Path
) -> dict[str, Optional[str]]:
    """
    Auto-derive development doc_key → service_alias by matching against
    API paths and service aliases.  Returns None values for skipped docs.
    """
    # normalized API path → alias  (e.g. "captcharecognitionrecaptcha2" → "recaptcha")
    path_to_alias: dict[str, str] = {}
    for alias, svc in service_by_alias.items():
        for api in svc.get("apis", []):
            path = api.get("path", "")
            norm = _normalize(path.strip("/").replace("/", "_"))
            if norm:
                path_to_alias[norm] = alias

    # normalized alias → original alias (longer first for prefix matching)
    alias_norms = sorted(
        ((alias, _normalize(alias)) for alias in service_by_alias),
        key=lambda t: -len(t[1]),
    )

    doc_map: dict[str, Optional[str]] = {}
    docs_dir = backend_dir / "docs"

    for md_file in sorted(docs_dir.glob("development_*.md")):
        doc_key = md_file.stem.removeprefix("development_")

        # Strip _title suffix variants used for Translation titles
        if doc_key.endswith("_title"):
            continue

        if doc_key in SKIP_DOC_KEYS:
            doc_map[doc_key] = None
            continue

        norm_key = _normalize(doc_key)

        # Strategy 1: exact match on normalized API path
        if norm_key in path_to_alias:
            doc_map[doc_key] = path_to_alias[norm_key]
            continue

        # Strategy 2: doc key starts with a normalized API path (longest first)
        matched = False
        for path_norm, alias in sorted(path_to_alias.items(), key=lambda x: -len(x[0])):
            if norm_key.startswith(path_norm):
                doc_map[doc_key] = alias
                matched = True
                break
        if matched:
            continue

        # Strategy 2b: long common prefix between doc key and API path (≥80% match)
        best_match = None
        best_overlap = 0
        for path_norm, alias in path_to_alias.items():
            # Compute common prefix length
            common = 0
            for a, b in zip(norm_key, path_norm):
                if a == b:
                    common += 1
                else:
                    break
            min_len = min(len(norm_key), len(path_norm))
            if min_len > 0 and common / min_len >= 0.8 and common > best_overlap:
                best_overlap = common
                best_match = alias
        if best_match:
            doc_map[doc_key] = best_match
            continue

        # Strategy 3: doc key starts with a service alias (longest first)
        for alias_orig, alias_norm in alias_norms:
            if norm_key.startswith(alias_norm):
                doc_map[doc_key] = alias_orig
                matched = True
                break
        if matched:
            continue

        print(f"  WARNING: unmapped doc '{doc_key}', skipping")
        doc_map[doc_key] = None

    return doc_map


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
        return re.sub(
            r"\$t\(([^)]+)\)", lambda m: m.group(1).replace("_", " ").title(), obj
        )
    if isinstance(obj, dict):
        return {k: resolve_t_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve_t_keys(item) for item in obj]
    return obj


# Valid keywords for OpenAPI 3.0 Schema Objects
_VALID_SCHEMA_KEYS = {
    "type",
    "format",
    "description",
    "default",
    "example",
    "examples",
    "enum",
    "const",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "items",
    "properties",
    "required",
    "additionalProperties",
    "oneOf",
    "allOf",
    "anyOf",
    "not",
    "discriminator",
    "nullable",
    "readOnly",
    "writeOnly",
    "deprecated",
    "title",
    "$ref",
}


def _clean_schema(obj: dict) -> dict:
    """Clean a JSON Schema for OpenAPI 3.0 compliance."""
    if not isinstance(obj, dict):
        return obj
    cleaned = {}
    for k, v in obj.items():
        if k not in _VALID_SCHEMA_KEYS and not k.startswith("x-"):
            continue
        if k == "type" and v == "float":
            cleaned["type"] = "number"
            cleaned.setdefault("format", "float")
            continue
        if k == "type" and v == "int":
            cleaned["type"] = "integer"
            continue
        if k == "const":
            cleaned["enum"] = [v]
            continue
        if k in ("items", "additionalProperties", "not") and isinstance(v, dict):
            cleaned[k] = _clean_schema(v)
        elif k == "properties" and isinstance(v, dict):
            cleaned[k] = {pk: _clean_schema(pv) for pk, pv in v.items()}
        elif k in ("oneOf", "allOf", "anyOf") and isinstance(v, list):
            cleaned[k] = [_clean_schema(item) for item in v]
        else:
            cleaned[k] = v
    if "type" in cleaned and "example" in cleaned:
        t, ex = cleaned["type"], cleaned["example"]
        if t == "object" and isinstance(ex, str):
            cleaned["type"] = "string"
        elif t == "object" and isinstance(ex, (int, float)):
            cleaned["type"] = "number"
    if (
        "required" in cleaned
        and isinstance(cleaned["required"], list)
        and not cleaned["required"]
    ):
        del cleaned["required"]
    return cleaned


def clean_openapi_spec(spec: dict) -> dict:
    """Clean an OpenAPI spec for strict validation compliance."""
    if "paths" not in spec:
        return spec
    cleaned = dict(spec)
    cleaned_paths = {}
    _resp_keys = {"description", "headers", "content", "links"}
    _rb_keys = {"description", "content", "required"}
    _mt_keys = {"schema", "example", "examples", "encoding"}
    for path, path_item in spec["paths"].items():
        if not isinstance(path_item, dict):
            cleaned_paths[path] = path_item
            continue
        ci = {}
        for method, op in path_item.items():
            if method not in (
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "options",
                "head",
                "trace",
            ):
                ci[method] = op
                continue
            if not isinstance(op, dict):
                ci[method] = op
                continue
            cop = dict(op)
            if "requestBody" in cop and isinstance(cop["requestBody"], dict):
                rb = {
                    k: v
                    for k, v in cop["requestBody"].items()
                    if k in _rb_keys or k.startswith("x-")
                }
                if "content" in rb:
                    rb["content"] = {
                        ct: {
                            k: (_clean_schema(v) if k == "schema" else v)
                            for k, v in mt.items()
                            if k in _mt_keys
                        }
                        for ct, mt in rb["content"].items()
                        if isinstance(mt, dict)
                    }
                cop["requestBody"] = rb
            if "responses" in cop and isinstance(cop["responses"], dict):
                new_resps = {}
                for code, resp in cop["responses"].items():
                    if not isinstance(resp, dict):
                        new_resps[code] = resp
                        continue
                    cr = {
                        k: v
                        for k, v in resp.items()
                        if k in _resp_keys or k.startswith("x-")
                    }
                    if "description" not in cr:
                        cr["description"] = "Response"
                    if "content" in cr:
                        cr["content"] = {
                            ct: {
                                k: (_clean_schema(v) if k == "schema" else v)
                                for k, v in mt.items()
                                if k in _mt_keys
                            }
                            for ct, mt in cr["content"].items()
                            if isinstance(mt, dict)
                        }
                    new_resps[code] = cr
                cop["responses"] = new_resps
            if "parameters" in cop and isinstance(cop["parameters"], list):
                cop["parameters"] = [
                    {
                        k: (_clean_schema(v) if k == "schema" else v)
                        for k, v in p.items()
                    }
                    for p in cop["parameters"]
                    if isinstance(p, dict)
                ]
            ci[method] = cop
        cleaned_paths[path] = ci
    cleaned["paths"] = cleaned_paths
    return cleaned


def merge_openapi_specs(backend_dir: Path, service: dict) -> dict | None:
    """Merge multiple per-API OpenAPI specs into one per-service spec."""
    apis = service.get("apis", [])
    if not apis:
        return None

    display = service.get("display_name") or service.get("alias", "API")

    merged = {
        "openapi": "3.0.0",
        "info": {
            "title": display,
            "version": "1.0.0",
            "description": f"API reference for {display} on Ace Data Cloud.",
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
    # Clean for strict OpenAPI 3.0 compliance (Mintlify validation)
    merged = clean_openapi_spec(merged)
    return merged


def convert_dev_doc_to_mdx(content: str, doc_key: str, service_name: str) -> str:
    """Convert a PlatformBackend development markdown doc to Mintlify MDX format."""
    # Extract a title from the first heading or generate one
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = doc_key.replace("_", " ").title()

    # Clean up the content
    # Remove the first h1 if we extracted it
    if title_match:
        content = content[: title_match.start()] + content[title_match.end() :]

    # Replace image references that use platform URLs with relative paths
    content = re.sub(
        r"!\[([^\]]*)\]\(https://cdn\.acedata\.cloud/([^)]+)\)",
        r"![\1](https://cdn.acedata.cloud/\2)",
        content,
    )

    # Replace $t() references
    content = re.sub(
        r"\$t\(([^)]+)\)", lambda m: m.group(1).replace("_", " ").title(), content
    )

    # Build frontmatter
    frontmatter = f"""---
title: "{title}"
description: "Integration guide for {service_name} on Ace Data Cloud"
---

"""
    return frontmatter + content.strip() + "\n"


def generate_mcp_doc(content: str, mcp_name: str) -> str:
    """Convert MCP doc to MDX."""
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else f"MCP {mcp_name}"
    if title_match:
        content = content[: title_match.start()] + content[title_match.end() :]
    content = re.sub(
        r"\$t\(([^)]+)\)", lambda m: m.group(1).replace("_", " ").title(), content
    )

    return f"""---
title: "{title}"
description: "MCP server for {mcp_name} integration"
---

{content.strip()}
"""


def generate_extra_doc(content: str, doc_key: str) -> str:
    """Convert extra docs (privacy, terms, etc.) to MDX."""
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = (
        title_match.group(1).strip()
        if title_match
        else doc_key.replace("_", " ").title()
    )
    if title_match:
        content = content[: title_match.start()] + content[title_match.end() :]
    content = re.sub(
        r"\$t\(([^)]+)\)", lambda m: m.group(1).replace("_", " ").title(), content
    )

    return f"""---
title: "{title}"
---

{content.strip()}
"""


def build_navigation(
    categories: dict[str, dict],
    service_names: dict[str, str],
    dev_docs_by_service: dict,
    output_dir: Path,
) -> dict:
    """Build the Mintlify navigation structure from dynamic data."""
    tabs = []

    # Tab 1: Guides (Getting Started + Integration Guides by category)
    guide_groups = [
        {
            "group": "Getting Started",
            "pages": ["introduction", "quickstart", "authentication"],
        }
    ]

    # Integration guides by category
    for cat_name, cat_info in categories.items():
        pages = []
        for svc_alias in cat_info["services"]:
            if svc_alias in dev_docs_by_service:
                docs = dev_docs_by_service[svc_alias]
                if len(docs) == 1:
                    pages.append(f"guides/{svc_alias}/{docs[0]}")
                else:
                    svc_pages = [f"guides/{svc_alias}/{d}" for d in docs]
                    pages.append(
                        {
                            "group": service_names.get(svc_alias, svc_alias),
                            "pages": svc_pages,
                        }
                    )
        if pages:
            guide_groups.append(
                {
                    "group": cat_name,
                    "icon": cat_info["icon"],
                    "pages": pages,
                }
            )

    # X402 and other special guides
    special_pages = []
    if (output_dir / "guides" / "x402.mdx").exists():
        special_pages.append("guides/x402")
    if special_pages:
        guide_groups.append(
            {
                "group": "Advanced",
                "pages": special_pages,
            }
        )

    tabs.append(
        {
            "tab": "Guides",
            "groups": guide_groups,
        }
    )

    # Tab 2: API Reference (auto-populated from OpenAPI per service category)
    api_groups = [
        {
            "group": "Overview",
            "pages": ["api-reference/introduction"],
        }
    ]
    for cat_name, cat_info in categories.items():
        cat_pages = []
        for svc_alias in cat_info["services"]:
            openapi_path = f"openapi/{svc_alias}.json"
            if (output_dir / openapi_path).exists():
                cat_pages.append(
                    {
                        "group": service_names.get(svc_alias, svc_alias),
                        "openapi": {
                            "source": f"/{openapi_path}",
                            "directory": f"api-reference/{svc_alias}",
                        },
                    }
                )
        if cat_pages:
            api_groups.extend(cat_pages)

    tabs.append(
        {
            "tab": "API Reference",
            "groups": api_groups,
        }
    )

    # Tab 3: MCP Servers
    mcp_pages = []
    mcp_dir = output_dir / "mcp"
    if mcp_dir.exists():
        for f in sorted(mcp_dir.iterdir()):
            if f.suffix == ".mdx":
                mcp_pages.append(f"mcp/{f.stem}")
    if mcp_pages:
        tabs.append(
            {
                "tab": "MCP Servers",
                "groups": [
                    {
                        "group": "MCP Servers",
                        "pages": ["mcp/overview"] + mcp_pages
                        if (output_dir / "mcp" / "overview.mdx").exists()
                        else mcp_pages,
                    }
                ],
            }
        )

    # Tab 4: Resources
    resource_pages = []
    if (output_dir / "resources" / "privacy.mdx").exists():
        resource_pages.append("resources/privacy")
    if (output_dir / "resources" / "terms.mdx").exists():
        resource_pages.append("resources/terms")
    if (output_dir / "resources" / "support.mdx").exists():
        resource_pages.append("resources/support")
    if resource_pages:
        tabs.append(
            {
                "tab": "Resources",
                "groups": [{"group": "Resources", "pages": resource_pages}],
            }
        )

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
    parser = argparse.ArgumentParser(
        description="Sync PlatformBackend docs to Mintlify"
    )
    parser.add_argument("--backend-dir", required=True, help="Path to PlatformBackend")
    parser.add_argument("--output-dir", required=True, help="Path to Docs repo root")
    args = parser.parse_args()

    backend_dir = Path(args.backend_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    print(f"Backend: {backend_dir}")
    print(f"Output:  {output_dir}")

    # Load service mapping
    services = load_service_mapping(backend_dir)
    service_by_alias: dict[str, dict] = {}

    for svc in services:
        if svc.get("alias") in EXCLUDE_FROM_DOCS:
            continue
        alias = svc.get("alias")
        if not alias:
            # Derive alias from $t(service_title_xxx) → xxx with underscores → hyphens
            title = svc.get("title", "")
            m = re.match(r"^\$t\(service_title_([^)]+)\)$", title)
            if m:
                alias = m.group(1).replace("_", "-")
                svc["alias"] = alias
        if alias:
            service_by_alias[alias] = svc

    # Build dynamic lookup tables
    service_names = build_service_names(service_by_alias)
    categories = build_categories(service_by_alias)
    doc_service_map = build_doc_service_map(service_by_alias, backend_dir)

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
        service_alias = doc_service_map.get(doc_key)
        if service_alias is None:
            continue  # skip unmapped docs

        content = md_file.read_text(encoding="utf-8")
        svc_name = service_names.get(service_alias, service_alias)
        mdx_content = convert_dev_doc_to_mdx(content, doc_key, svc_name)

        svc_dir = guides_dir / service_alias
        svc_dir.mkdir(parents=True, exist_ok=True)
        out_path = svc_dir / f"{doc_key}.mdx"
        out_path.write_text(mdx_content, encoding="utf-8")

        dev_docs_by_service.setdefault(service_alias, []).append(doc_key)

    print(
        f"Generated {sum(len(v) for v in dev_docs_by_service.values())} guide pages across {len(dev_docs_by_service)} services"
    )

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

    # MCP overview page — dynamically built from discovered MCP docs
    mcp_cards = []
    for md_file in sorted(docs_dir.glob("mcp_*.md")):
        name = md_file.stem.removeprefix("mcp_")
        display = name.replace("-", " ").replace("_", " ").title()
        mcp_cards.append(
            f'  <Card title="{display}" href="/mcp/{name}">\n'
            f"    {display} MCP server\n"
            f"  </Card>"
        )
    cards_block = "\n".join(mcp_cards) if mcp_cards else ""
    mcp_overview = f"""---
title: "MCP Servers"
description: "Model Context Protocol servers for AI tool integration"
---

Ace Data Cloud provides MCP (Model Context Protocol) servers that allow AI assistants like Claude, Cursor, and Windsurf to directly use our APIs.

<CardGroup cols={{2}}>
{cards_block}
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
    navigation = build_navigation(
        categories, service_names, dev_docs_by_service, output_dir
    )

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
            "playground": {"display": "simple"},
            "mdx": {
                "auth": {
                    "method": "bearer",
                    "name": "Authorization",
                },
            },
            "openapi": sorted(
                f"/openapi/{f.name}"
                for f in (output_dir / "openapi").iterdir()
                if f.suffix == ".json"
            ),
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
