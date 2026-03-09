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
import sys
import time as _time
from pathlib import Path
from typing import Optional

_T0 = _time.time()


def log(msg: str = ""):
    """Log with elapsed time — flushed immediately for CI visibility."""
    elapsed = _time.time() - _T0
    print(f"[{elapsed:6.1f}s] {msg}", flush=True)


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
    docs_dir = backend_dir / "docs" / "zh-CN"

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


def _t_key_to_title(key: str) -> str:
    """Convert a $t() translation key to a clean, concise display title."""
    # Strip common prefixes that add no value
    for prefix in (
        "api_description_",
        "service_title_",
        "service_description_",
    ):
        if key.startswith(prefix):
            key = key[len(prefix) :]
            break
    return key.replace("_", " ").title()


def resolve_t_keys(obj):
    """Replace $t(key) translation markers with the key itself as a readable title."""
    if isinstance(obj, str):
        return re.sub(r"\$t\(([^)]+)\)", lambda m: _t_key_to_title(m.group(1)), obj)
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


_MAX_SUMMARY_LEN = 80


def _path_to_short_title(path: str, method: str) -> str:
    """Generate a concise title from an API path.

    Example: POST /face/analyze → 'Face Analyze'
             POST /identity/phone/check-3e → 'Phone Check 3E'
    """
    segments = [s for s in path.strip("/").split("/") if s]
    # Drop generic first segments that match the service name prefix
    if len(segments) > 1:
        segments = segments[1:]  # e.g. /face/analyze → ['analyze']
    title = " ".join(s.replace("-", " ").replace("_", " ") for s in segments).title()
    return title or f"{method.upper()} {path}"


def _clean_verbose_summaries(spec: dict):
    """Ensure all operation summaries are concise.

    If a summary exceeds _MAX_SUMMARY_LEN characters, move the full text to
    ``description`` (if not already set) and replace the summary with a short
    title derived from the path.
    """
    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            summary = op.get("summary", "")
            if len(summary) > _MAX_SUMMARY_LEN:
                # Preserve full text as description
                if not op.get("description"):
                    op["description"] = summary
                op["summary"] = _path_to_short_title(path, method)


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
    # Clean verbose summaries — move long text to description, generate short title
    _clean_verbose_summaries(merged)
    # Clean for strict OpenAPI 3.0 compliance (Mintlify validation)
    merged = clean_openapi_spec(merged)
    return merged


def _sanitize_html_for_mdx(content: str) -> str:
    """Sanitize HTML in markdown content so it is valid JSX for MDX.

    Fixes:
    - ``class=`` → ``className=`` (reserved word in JSX)
    - Self-close void elements: ``<img ...>`` → ``<img ... />``
    - Angle-bracket URLs: ``<https://...>`` → ``[https://...](https://...)``
    """
    # Only transform HTML outside of fenced code blocks
    parts = re.split(r"(^```.*?^```)", content, flags=re.MULTILINE | re.DOTALL)
    for i, part in enumerate(parts):
        if part.startswith("```"):
            continue  # skip code blocks
        # class → className in HTML tags
        part = re.sub(
            r"(<[a-zA-Z][^>]*)\bclass=",
            r"\1className=",
            part,
        )
        # Self-close void elements that aren't already self-closed
        for tag in ("img", "br", "hr", "input", "source", "meta", "link"):
            part = re.sub(
                rf"(<{tag}\b[^>]*?)(?<!/)>",
                rf"\1 />",
                part,
            )
        # Angle-bracket URLs → markdown links
        part = re.sub(
            r"<(https?://[^>]+)>",
            r"[\1](\1)",
            part,
        )
        # Escape bare < that don't start valid HTML/JSX tags (e.g. <= in tables)
        part = re.sub(
            r"<(?![a-zA-Z/!])",
            r"&lt;",
            part,
        )
        parts[i] = part
    return "".join(parts)


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

    # Sanitize HTML for MDX/JSX compatibility
    content = _sanitize_html_for_mdx(content)

    # Build frontmatter
    frontmatter = f"""---
title: "{title}"
description: "{service_name} 集成指南 - Ace Data Cloud"
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
    content = _sanitize_html_for_mdx(content)

    return f"""---
title: "{title}"
description: "{mcp_name} MCP 服务器集成"
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
    content = _sanitize_html_for_mdx(content)

    return f"""---
title: "{title}"
---

{content.strip()}
"""


def _build_tutorials_nav(output_dir: Path) -> list:
    """Auto-discover tutorial pages and group by service."""
    tut_dir = output_dir / "tutorials"
    if not tut_dir.is_dir():
        return []
    groups: dict[str, list[str]] = {}
    for f in sorted(tut_dir.rglob("*.mdx")):
        rel = f.relative_to(tut_dir)
        parts = rel.parts
        if len(parts) == 2:
            svc = parts[0]
            groups.setdefault(svc, []).append(f"tutorials/{svc}/{rel.stem}")
        elif len(parts) == 1:
            groups.setdefault("_root", []).append(f"tutorials/{rel.stem}")
    nav = []
    for svc, pages in groups.items():
        if svc == "_root":
            nav.extend(pages)
        elif len(pages) == 1:
            nav.append(pages[0])
        else:
            nav.append({"group": svc.replace("-", " ").title(), "pages": pages})
    return nav


def _copy_seo_pages(docs_dir: Path, output_dir: Path):
    """Copy pre-generated SEO content from PlatformBackend/docs to Mintlify output.

    Source files:  tutorial_{service}_{lang}.md, comparison_{slug}.md,
                   use_case_{slug}.md, blog_{slug}.md
    Destination:   tutorials/{service}/{lang}.mdx, comparisons/{slug}.mdx,
                   use-cases/{slug}.mdx, blog/{slug}.mdx
    """
    if not docs_dir.is_dir():
        log(f"  WARNING: {docs_dir} not found, skipping SEO pages")
        return

    counts: dict[str, int] = {
        "tutorials": 0,
        "comparisons": 0,
        "use-cases": 0,
        "blog": 0,
    }

    for src in sorted(docs_dir.glob("*.md")):
        name = src.stem  # e.g. tutorial_claude_python

        if name.startswith("tutorial_"):
            # tutorial_{service}_{lang}.md → tutorials/{service}/{lang}.mdx
            rest = name[len("tutorial_") :]  # e.g. claude_python or nano-banana_curl
            # Find the last _ that separates service from lang
            for lang in ("python", "javascript", "curl"):
                suffix = f"_{lang}"
                if rest.endswith(suffix):
                    service = rest[: -len(suffix)]
                    dst = output_dir / "tutorials" / service / f"{lang}.mdx"
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    _write_seo_mdx(src, dst)
                    counts["tutorials"] += 1
                    break

        elif name.startswith("comparison_"):
            slug = name[len("comparison_") :]
            dst = output_dir / "comparisons" / f"{slug}.mdx"
            dst.parent.mkdir(parents=True, exist_ok=True)
            _write_seo_mdx(src, dst)
            counts["comparisons"] += 1

        elif name.startswith("use_case_"):
            slug = name[len("use_case_") :]
            dst = output_dir / "use-cases" / f"{slug}.mdx"
            dst.parent.mkdir(parents=True, exist_ok=True)
            _write_seo_mdx(src, dst)
            counts["use-cases"] += 1

        elif name.startswith("blog_"):
            slug = name[len("blog_") :]
            dst = output_dir / "blog" / f"{slug}.mdx"
            dst.parent.mkdir(parents=True, exist_ok=True)
            _write_seo_mdx(src, dst)
            counts["blog"] += 1

    for cat, n in counts.items():
        log(f"  {cat}: {n} files")
    log(f"  Total: {sum(counts.values())} SEO pages copied")


def _write_seo_mdx(src: Path, dst: Path):
    """Read a Markdown source and write as MDX with frontmatter.

    If the source already has frontmatter (---), keep it.
    Otherwise, extract the first H1 as the title and generate frontmatter.
    """
    content = src.read_text(encoding="utf-8")

    if content.startswith("---"):
        # Already has frontmatter — still sanitize HTML for MDX
        content = _sanitize_html_for_mdx(content)
        dst.write_text(content, encoding="utf-8")
        return

    # Extract title from first H1
    title = ""
    lines = content.split("\n")
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body_start = i + 1
            break

    if not title:
        title = src.stem.replace("_", " ").replace("-", " ").title()

    body = "\n".join(lines[body_start:]).strip()
    body = _sanitize_html_for_mdx(body)
    mdx = f"""---
title: "{title}"
---

{body}
"""
    dst.write_text(mdx, encoding="utf-8")


def _build_simple_nav(directory: str, output_dir: Path) -> list[str]:
    """Auto-discover MDX pages in a flat directory."""
    d = output_dir / directory
    if not d.is_dir():
        return []
    return sorted(f"{directory}/{f.stem}" for f in d.iterdir() if f.suffix == ".mdx")


def build_navigation(
    categories: dict[str, dict],
    service_names: dict[str, str],
    dev_docs_by_service: dict,
    output_dir: Path,
) -> dict:
    """Build the Mintlify navigation structure from dynamic data."""
    tabs = []

    # Tab 1: 指南 (入门 + 集成指南)
    guide_groups = [
        {
            "group": "入门",
            "pages": ["introduction", "quickstart", "authentication"],
        }
    ]

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

    special_pages = []
    if (output_dir / "guides" / "x402.mdx").exists():
        special_pages.append("guides/x402")
    if special_pages:
        guide_groups.append({"group": "高级", "pages": special_pages})

    tabs.append({"tab": "指南", "groups": guide_groups})

    # Tab 2: API 参考 (paired with integration guides per service)
    api_groups = [
        {
            "group": "概览",
            "pages": ["api-reference/introduction"],
        }
    ]
    for cat_name, cat_info in categories.items():
        cat_pages = []
        for svc_alias in cat_info["services"]:
            openapi_path = f"openapi/{svc_alias}.json"
            if not (output_dir / openapi_path).exists():
                continue
            svc_name = service_names.get(svc_alias, svc_alias)

            cat_pages.append(
                {
                    "group": svc_name,
                    "openapi": {
                        "source": f"/{openapi_path}",
                        "directory": f"api-reference/{svc_alias}",
                    },
                }
            )
        if cat_pages:
            api_groups.extend(cat_pages)

    tabs.append({"tab": "API 参考", "groups": api_groups})

    # Tab 3: 教程
    tut_pages = _build_tutorials_nav(output_dir)
    if tut_pages:
        tabs.append({"tab": "教程", "groups": [{"group": "教程", "pages": tut_pages}]})

    # Tab 4: 对比
    cmp_pages = _build_simple_nav("comparisons", output_dir)
    if cmp_pages:
        tabs.append(
            {"tab": "对比", "groups": [{"group": "服务对比", "pages": cmp_pages}]}
        )

    # Tab 5: 用例
    uc_pages = _build_simple_nav("use-cases", output_dir)
    if uc_pages:
        tabs.append(
            {"tab": "用例", "groups": [{"group": "应用场景", "pages": uc_pages}]}
        )

    # Tab 6: 博客
    blog_pages = _build_simple_nav("blog", output_dir)
    if blog_pages:
        tabs.append({"tab": "博客", "groups": [{"group": "博客", "pages": blog_pages}]})

    # Tab 7: MCP 服务器
    mcp_pages = []
    mcp_dir = output_dir / "mcp"
    if mcp_dir.exists():
        for f in sorted(mcp_dir.iterdir()):
            if f.suffix == ".mdx" and f.stem != "overview":
                mcp_pages.append(f"mcp/{f.stem}")
    if mcp_pages:
        all_mcp = (
            ["mcp/overview"] + mcp_pages
            if (output_dir / "mcp" / "overview.mdx").exists()
            else mcp_pages
        )
        tabs.append(
            {"tab": "MCP 服务器", "groups": [{"group": "MCP 服务器", "pages": all_mcp}]}
        )

    # Tab 8: 资源
    resource_pages = []
    if (output_dir / "resources" / "privacy.mdx").exists():
        resource_pages.append("resources/privacy")
    if (output_dir / "resources" / "terms.mdx").exists():
        resource_pages.append("resources/terms")
    if (output_dir / "resources" / "support.mdx").exists():
        resource_pages.append("resources/support")
    if resource_pages:
        tabs.append(
            {"tab": "资源", "groups": [{"group": "资源", "pages": resource_pages}]}
        )

    return {
        "tabs": tabs,
        "global": {
            "anchors": [
                {
                    "anchor": "平台",
                    "href": "https://platform.acedata.cloud",
                    "icon": "browser",
                },
                {
                    "anchor": "API 状态",
                    "href": "https://status.acedata.cloud",
                    "icon": "signal",
                },
            ]
        },
    }


# Target languages matching PlatformBackend/docs/ subdirectories
TARGET_LANGUAGES = [
    "en",
    "zh-tw",
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

# Mintlify expects specific language codes (may differ from directory names)
_LANG_DIR_TO_MINTLIFY = {
    "zh-tw": "zh-TW",
}


def _mintlify_lang(lang_dir: str) -> str:
    """Map PlatformBackend language directory name to Mintlify output directory."""
    return _LANG_DIR_TO_MINTLIFY.get(lang_dir, lang_dir)


# ---------------------------------------------------------------------------
# Mintlify language enum codes (used in docs.json "language" field)
# ---------------------------------------------------------------------------
_LANG_TO_MINTLIFY_CODE: dict[str, str] = {
    "zh-tw": "zh-Hant",
}

# Languages NOT supported by Mintlify's language enum — content is synced
# but they cannot appear in the language switcher.
_UNSUPPORTED_MINTLIFY_LANGS: set[str] = {"fi", "el", "sr"}


def _mintlify_code(lang_dir: str) -> str:
    """Map language directory name to Mintlify language enum value."""
    return _LANG_TO_MINTLIFY_CODE.get(lang_dir, lang_dir)


# ---------------------------------------------------------------------------
# Translated navigation labels for secondary languages
# ---------------------------------------------------------------------------
_NAV_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "指南": "Guides",
        "入门": "Getting Started",
        "高级": "Advanced",
        "API 参考": "API Reference",
        "概览": "Overview",
        "API 端点": "API Endpoints",
        "集成指南": "Integration Guides",
        "教程": "Tutorials",
        "对比": "Comparisons",
        "服务对比": "Service Comparisons",
        "用例": "Use Cases",
        "应用场景": "Use Cases",
        "博客": "Blog",
        "MCP 服务器": "MCP Servers",
        "资源": "Resources",
    },
    "ja": {
        "指南": "ガイド",
        "入门": "はじめに",
        "高级": "上級",
        "API 参考": "API リファレンス",
        "概览": "概要",
        "API 端点": "API エンドポイント",
        "集成指南": "統合ガイド",
        "教程": "チュートリアル",
        "对比": "比較",
        "服务对比": "サービス比較",
        "用例": "ユースケース",
        "应用场景": "ユースケース",
        "博客": "ブログ",
        "MCP 服务器": "MCP サーバー",
        "资源": "リソース",
    },
    "ko": {
        "指南": "가이드",
        "入门": "시작하기",
        "高级": "고급",
        "API 参考": "API 레퍼런스",
        "概览": "개요",
        "API 端点": "API 엔드포인트",
        "集成指南": "통합 가이드",
        "教程": "튜토리얼",
        "对比": "비교",
        "服务对比": "서비스 비교",
        "用例": "사용 사례",
        "应用场景": "사용 사례",
        "博客": "블로그",
        "MCP 服务器": "MCP 서버",
        "资源": "리소스",
    },
    "es": {
        "指南": "Guías",
        "入门": "Primeros pasos",
        "高级": "Avanzado",
        "API 参考": "Referencia API",
        "概览": "Descripción general",
        "API 端点": "Endpoints API",
        "集成指南": "Guías de integración",
        "教程": "Tutoriales",
        "对比": "Comparaciones",
        "服务对比": "Comparación de servicios",
        "用例": "Casos de uso",
        "应用场景": "Casos de uso",
        "博客": "Blog",
        "MCP 服务器": "Servidores MCP",
        "资源": "Recursos",
    },
    "fr": {
        "指南": "Guides",
        "入门": "Démarrage",
        "高级": "Avancé",
        "API 参考": "Référence API",
        "概览": "Aperçu",
        "API 端点": "Points d'accès API",
        "集成指南": "Guides d'intégration",
        "教程": "Tutoriels",
        "对比": "Comparaisons",
        "服务对比": "Comparaison de services",
        "用例": "Cas d'utilisation",
        "应用场景": "Cas d'utilisation",
        "博客": "Blog",
        "MCP 服务器": "Serveurs MCP",
        "资源": "Ressources",
    },
    "de": {
        "指南": "Anleitungen",
        "入门": "Erste Schritte",
        "高级": "Erweitert",
        "API 参考": "API-Referenz",
        "概览": "Übersicht",
        "API 端点": "API-Endpunkte",
        "集成指南": "Integrationsleitfäden",
        "教程": "Tutorials",
        "对比": "Vergleiche",
        "服务对比": "Servicevergleiche",
        "用例": "Anwendungsfälle",
        "应用场景": "Anwendungsfälle",
        "博客": "Blog",
        "MCP 服务器": "MCP-Server",
        "资源": "Ressourcen",
    },
    "pt": {
        "指南": "Guias",
        "入门": "Primeiros passos",
        "高级": "Avançado",
        "API 参考": "Referência API",
        "概览": "Visão geral",
        "API 端点": "Endpoints API",
        "集成指南": "Guias de integração",
        "教程": "Tutoriais",
        "对比": "Comparações",
        "服务对比": "Comparação de serviços",
        "用例": "Casos de uso",
        "应用场景": "Casos de uso",
        "博客": "Blog",
        "MCP 服务器": "Servidores MCP",
        "资源": "Recursos",
    },
    "ru": {
        "指南": "Руководства",
        "入门": "Начало работы",
        "高级": "Продвинутый",
        "API 参考": "Справочник API",
        "概览": "Обзор",
        "API 端点": "Конечные точки API",
        "集成指南": "Руководства по интеграции",
        "教程": "Учебники",
        "对比": "Сравнения",
        "服务对比": "Сравнение сервисов",
        "用例": "Примеры использования",
        "应用场景": "Примеры использования",
        "博客": "Блог",
        "MCP 服务器": "MCP-серверы",
        "资源": "Ресурсы",
    },
    "ar": {
        "指南": "الأدلة",
        "入门": "البداية",
        "高级": "متقدم",
        "API 参考": "مرجع API",
        "概览": "نظرة عامة",
        "API 端点": "نقاط نهاية API",
        "集成指南": "أدلة التكامل",
        "教程": "دروس",
        "对比": "مقارنات",
        "服务对比": "مقارنة الخدمات",
        "用例": "حالات الاستخدام",
        "应用场景": "حالات الاستخدام",
        "博客": "مدونة",
        "MCP 服务器": "خوادم MCP",
        "资源": "الموارد",
    },
    "it": {
        "指南": "Guide",
        "入门": "Inizia",
        "高级": "Avanzato",
        "API 参考": "Riferimento API",
        "概览": "Panoramica",
        "API 端点": "Endpoint API",
        "集成指南": "Guide all'integrazione",
        "教程": "Tutorial",
        "对比": "Confronti",
        "服务对比": "Confronto servizi",
        "用例": "Casi d'uso",
        "应用场景": "Casi d'uso",
        "博客": "Blog",
        "MCP 服务器": "Server MCP",
        "资源": "Risorse",
    },
    "zh-tw": {
        "指南": "指南",
        "入门": "入門",
        "高级": "進階",
        "API 参考": "API 參考",
        "概览": "概覽",
        "API 端点": "API 端點",
        "集成指南": "整合指南",
        "教程": "教學",
        "对比": "比較",
        "服务对比": "服務比較",
        "用例": "應用案例",
        "应用场景": "應用案例",
        "博客": "部落格",
        "MCP 服务器": "MCP 伺服器",
        "资源": "資源",
    },
}


def _t(lang: str, label: str) -> str:
    """Translate a Chinese navigation label. Falls back to English, then original."""
    tr = _NAV_TRANSLATIONS.get(lang)
    if tr and label in tr:
        return tr[label]
    en = _NAV_TRANSLATIONS.get("en", {})
    return en.get(label, label)


def _build_tutorials_nav_for(tut_dir: Path, lang_prefix: str) -> list:
    """Auto-discover tutorial pages for a language directory."""
    if not tut_dir.is_dir():
        return []
    groups: dict[str, list[str]] = {}
    for f in sorted(tut_dir.rglob("*.mdx")):
        rel = f.relative_to(tut_dir)
        parts = rel.parts
        if len(parts) == 2:
            svc = parts[0]
            groups.setdefault(svc, []).append(
                f"{lang_prefix}/tutorials/{svc}/{rel.stem}"
            )
        elif len(parts) == 1:
            groups.setdefault("_root", []).append(f"{lang_prefix}/tutorials/{rel.stem}")
    nav = []
    for svc, pages in groups.items():
        if svc == "_root":
            nav.extend(pages)
        elif len(pages) == 1:
            nav.append(pages[0])
        else:
            nav.append({"group": svc.replace("-", " ").title(), "pages": pages})
    return nav


def build_language_navigation(
    lang: str,
    categories: dict[str, dict],
    service_names: dict[str, str],
    dev_docs_by_service: dict,
    output_dir: Path,
) -> list[dict] | None:
    """Build Mintlify tabs for a secondary language.

    Returns a list of tab dicts, or None if no content exists for this language.
    Mirrors the structure of build_navigation() but prefixes all page paths
    with the Mintlify output directory (e.g. ``en/``, ``zh-TW/``) and uses
    translated labels.
    """
    lang_out = _mintlify_lang(lang)  # output directory name
    lang_dir = output_dir / lang_out

    if not lang_dir.is_dir():
        return None

    tabs: list[dict] = []

    # --- Guides tab ---
    guide_groups: list[dict] = []
    intro_path = lang_dir / "introduction.mdx"
    qs_path = lang_dir / "quickstart.mdx"
    auth_path = lang_dir / "authentication.mdx"
    getting_started_pages = []
    if intro_path.exists():
        getting_started_pages.append(f"{lang_out}/introduction")
    if qs_path.exists():
        getting_started_pages.append(f"{lang_out}/quickstart")
    if auth_path.exists():
        getting_started_pages.append(f"{lang_out}/authentication")
    if getting_started_pages:
        guide_groups.append({"group": _t(lang, "入门"), "pages": getting_started_pages})

    for cat_name, cat_info in categories.items():
        pages: list = []
        for svc_alias in cat_info["services"]:
            if svc_alias not in dev_docs_by_service:
                continue
            docs = dev_docs_by_service[svc_alias]
            existing = [
                d
                for d in docs
                if (lang_dir / "guides" / svc_alias / f"{d}.mdx").exists()
            ]
            if not existing:
                continue
            if len(existing) == 1:
                pages.append(f"{lang_out}/guides/{svc_alias}/{existing[0]}")
            else:
                svc_pages = [f"{lang_out}/guides/{svc_alias}/{d}" for d in existing]
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

    special_pages = []
    if (lang_dir / "guides" / "x402.mdx").exists():
        special_pages.append(f"{lang_out}/guides/x402")
    if special_pages:
        guide_groups.append({"group": _t(lang, "高级"), "pages": special_pages})

    if guide_groups:
        tabs.append({"tab": _t(lang, "指南"), "groups": guide_groups})

    # --- API Reference tab ---
    api_groups: list[dict] = []
    api_intro = lang_dir / "api-reference" / "introduction.mdx"
    if api_intro.exists():
        api_groups.append(
            {
                "group": _t(lang, "概览"),
                "pages": [f"{lang_out}/api-reference/introduction"],
            }
        )
    for cat_name, cat_info in categories.items():
        for svc_alias in cat_info["services"]:
            openapi_path = f"openapi/{svc_alias}.json"
            if not (output_dir / openapi_path).exists():
                continue
            svc_name = service_names.get(svc_alias, svc_alias)

            api_groups.append(
                {
                    "group": svc_name,
                    "openapi": {
                        "source": f"/{openapi_path}",
                        "directory": f"{lang_out}/api-reference/{svc_alias}",
                    },
                }
            )
    if api_groups:
        tabs.append({"tab": _t(lang, "API 参考"), "groups": api_groups})

    # --- Tutorials tab (Chinese-only content may exist in translations) ---
    tut_pages = _build_tutorials_nav_for(lang_dir / "tutorials", lang_out)
    if tut_pages:
        tabs.append(
            {
                "tab": _t(lang, "教程"),
                "groups": [{"group": _t(lang, "教程"), "pages": tut_pages}],
            }
        )

    # --- Comparisons tab ---
    cmp_dir = lang_dir / "comparisons"
    if cmp_dir.is_dir():
        cmp_pages = sorted(
            f"{lang_out}/comparisons/{f.stem}"
            for f in cmp_dir.iterdir()
            if f.suffix == ".mdx"
        )
        if cmp_pages:
            tabs.append(
                {
                    "tab": _t(lang, "对比"),
                    "groups": [{"group": _t(lang, "服务对比"), "pages": cmp_pages}],
                }
            )

    # --- Use Cases tab ---
    uc_dir = lang_dir / "use-cases"
    if uc_dir.is_dir():
        uc_pages = sorted(
            f"{lang_out}/use-cases/{f.stem}"
            for f in uc_dir.iterdir()
            if f.suffix == ".mdx"
        )
        if uc_pages:
            tabs.append(
                {
                    "tab": _t(lang, "用例"),
                    "groups": [{"group": _t(lang, "应用场景"), "pages": uc_pages}],
                }
            )

    # --- Blog tab ---
    blog_dir = lang_dir / "blog"
    if blog_dir.is_dir():
        blog_pages = sorted(
            f"{lang_out}/blog/{f.stem}"
            for f in blog_dir.iterdir()
            if f.suffix == ".mdx"
        )
        if blog_pages:
            tabs.append(
                {
                    "tab": _t(lang, "博客"),
                    "groups": [{"group": _t(lang, "博客"), "pages": blog_pages}],
                }
            )

    # --- MCP Servers tab ---
    mcp_dir = lang_dir / "mcp"
    if mcp_dir.is_dir():
        mcp_pages = sorted(
            f"{lang_out}/mcp/{f.stem}"
            for f in mcp_dir.iterdir()
            if f.suffix == ".mdx" and f.stem != "overview"
        )
        if mcp_pages:
            all_mcp = (
                [f"{lang_out}/mcp/overview"] + mcp_pages
                if (mcp_dir / "overview.mdx").exists()
                else mcp_pages
            )
            tabs.append(
                {
                    "tab": _t(lang, "MCP 服务器"),
                    "groups": [{"group": _t(lang, "MCP 服务器"), "pages": all_mcp}],
                }
            )

    # --- Resources tab ---
    resource_pages = []
    for slug in ("privacy", "terms", "support"):
        if (lang_dir / "resources" / f"{slug}.mdx").exists():
            resource_pages.append(f"{lang_out}/resources/{slug}")
    if resource_pages:
        tabs.append(
            {
                "tab": _t(lang, "资源"),
                "groups": [{"group": _t(lang, "资源"), "pages": resource_pages}],
            }
        )

    if not tabs:
        return None

    return tabs


def _build_docs_json_navigation(
    cn_navigation: dict,
    categories: dict[str, dict],
    service_names: dict[str, str],
    dev_docs_by_service: dict,
    output_dir: Path,
) -> dict:
    """Assemble the full navigation object for docs.json, including all languages."""
    languages: list[dict] = [
        {
            "language": "cn",
            "default": True,
            "tabs": cn_navigation["tabs"],
        }
    ]

    for lang in TARGET_LANGUAGES:
        if lang in _UNSUPPORTED_MINTLIFY_LANGS:
            continue
        code = _mintlify_code(lang)
        lang_tabs = build_language_navigation(
            lang, categories, service_names, dev_docs_by_service, output_dir
        )
        if lang_tabs:
            languages.append({"language": code, "tabs": lang_tabs})
            log(f"  Language nav: {code} — {len(lang_tabs)} tabs")
        else:
            log(f"  Language nav: {code} — no content, skipping")

    return {
        "global": cn_navigation.get("global", {}),
        "languages": languages,
    }


def _sync_translated_content(
    backend_dir: Path,
    output_dir: Path,
    doc_service_map: dict[str, Optional[str]],
    service_names: dict[str, str],
    categories: dict[str, dict],
    dev_docs_by_service: dict[str, list[str]],
):
    """Copy pre-translated content from PlatformBackend/docs/{lang}/ to Mintlify
    language directories.

    For each target language that has a directory in PlatformBackend/docs/,
    apply the same MD→MDX conversion as the zh-CN base, placing output into
    {output_dir}/{mintlify_lang}/guides/..., tutorials/..., etc.
    """
    total_files = 0

    for lang_dir in TARGET_LANGUAGES:
        lang_docs = backend_dir / "docs" / lang_dir
        if not lang_docs.is_dir():
            continue

        mlang = _mintlify_lang(lang_dir)
        lang_out = output_dir / mlang
        lang_count = 0

        # --- Development guides ---
        for md_file in sorted(lang_docs.glob("development_*.md")):
            doc_key = md_file.stem.removeprefix("development_")
            if doc_key.endswith("_title"):
                continue
            service_alias = doc_service_map.get(doc_key)
            if service_alias is None:
                continue
            content = md_file.read_text(encoding="utf-8")
            svc_name = service_names.get(service_alias, service_alias)
            mdx_content = convert_dev_doc_to_mdx(content, doc_key, svc_name)
            svc_dir = lang_out / "guides" / service_alias
            svc_dir.mkdir(parents=True, exist_ok=True)
            (svc_dir / f"{doc_key}.mdx").write_text(mdx_content, encoding="utf-8")
            lang_count += 1

        # --- MCP docs ---
        for md_file in sorted(lang_docs.glob("mcp_*.md")):
            mcp_name = md_file.stem.removeprefix("mcp_")
            content = md_file.read_text(encoding="utf-8")
            mdx_content = generate_mcp_doc(content, mcp_name)
            mcp_out = lang_out / "mcp"
            mcp_out.mkdir(parents=True, exist_ok=True)
            (mcp_out / f"{mcp_name}.mdx").write_text(mdx_content, encoding="utf-8")
            lang_count += 1

        # --- Extra docs (privacy, terms, support) ---
        for doc_key, out_rel in [
            ("privacy", "resources/privacy.mdx"),
            ("terms", "resources/terms.mdx"),
            ("support", "resources/support.mdx"),
        ]:
            src = lang_docs / f"{doc_key}.md"
            if src.exists():
                content = src.read_text(encoding="utf-8")
                mdx = generate_extra_doc(content, doc_key)
                dst = lang_out / out_rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(mdx, encoding="utf-8")
                lang_count += 1

        # --- X402 guide ---
        x402_src = lang_docs / "x402_integration_guide.md"
        if x402_src.exists():
            content = x402_src.read_text(encoding="utf-8")
            mdx = convert_dev_doc_to_mdx(content, "x402_integration_guide", "x402")
            guides_out = lang_out / "guides"
            guides_out.mkdir(parents=True, exist_ok=True)
            (guides_out / "x402.mdx").write_text(mdx, encoding="utf-8")
            lang_count += 1

        # --- SEO pages (tutorials, comparisons, use-cases, blog) ---
        _copy_seo_pages(lang_docs, lang_out)

        total_files += lang_count
        if lang_count > 0:
            log(f"  {mlang}: {lang_count} guide/mcp/resource pages (+ SEO pages)")

    log(
        f"  Total translated pages: {total_files} (across {len(TARGET_LANGUAGES)} languages)"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Sync PlatformBackend docs to Mintlify"
    )
    parser.add_argument("--backend-dir", required=True, help="Path to PlatformBackend")
    parser.add_argument("--output-dir", required=True, help="Path to Docs repo root")
    args = parser.parse_args()

    backend_dir = Path(args.backend_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    log(f"Backend: {backend_dir}")
    log(f"Output:  {output_dir}")
    log()

    # Load service mapping
    log("=" * 60)
    log("Step 1/8: Generate OpenAPI specs")
    log("=" * 60)
    services = load_service_mapping(backend_dir)
    log(f"Loaded {len(services)} services from mapping")
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
            log(f"  OpenAPI: {alias} ({len(spec['paths'])} endpoints)")

    log(f"Step 1 done: {len(generated_specs)} OpenAPI specs")

    # ---------------------------------------------------------------------------
    # 2. Convert development guides to MDX
    # ---------------------------------------------------------------------------
    guides_dir = output_dir / "guides"
    # Clean old guides
    if guides_dir.exists():
        shutil.rmtree(guides_dir)
    guides_dir.mkdir(parents=True, exist_ok=True)

    log()
    log("=" * 60)
    log("Step 2/8: Convert development guides to MDX")
    log("=" * 60)
    dev_docs_by_service: dict[str, list[str]] = {}  # alias → [doc_key, ...]
    docs_dir = backend_dir / "docs" / "zh-CN"

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

    log(
        f"Step 2 done: {sum(len(v) for v in dev_docs_by_service.values())} guide pages across {len(dev_docs_by_service)} services"
    )

    # ---------------------------------------------------------------------------
    # 3. MCP docs
    # ---------------------------------------------------------------------------
    log()
    log("=" * 60)
    log("Step 3/8: MCP docs")
    log("=" * 60)
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
title: "MCP 服务器"
description: "用于 AI 工具集成的 Model Context Protocol 服务器"
---

Ace Data Cloud 提供 MCP（Model Context Protocol）服务器，让 Claude、Cursor、Windsurf 等 AI 助手直接调用我们的 API。

<CardGroup cols={{2}}>
{cards_block}
</CardGroup>
"""
    (mcp_dir / "overview.mdx").write_text(mcp_overview, encoding="utf-8")
    log(f"Step 3 done: {mcp_count} MCP pages")

    # ---------------------------------------------------------------------------
    # 4. Extra docs (privacy, terms, support, x402, etc.)
    # ---------------------------------------------------------------------------
    log()
    log("=" * 60)
    log("Step 4/8: Extra docs")
    log("=" * 60)
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

    log("Step 4 done")
    log()
    log("=" * 60)
    log("Step 5/8: Generate static pages")
    log("=" * 60)

    # Introduction page
    intro = """---
title: "简介"
description: "Ace Data Cloud 提供统一 AI API 平台，一个 API Key 即可访问 LLM 聊天、图像生成、视频生成、音乐生成、网页搜索等 50+ AI 服务。"
---

## 什么是 Ace Data Cloud？

Ace Data Cloud 是一个统一 AI API 平台，通过一个 API Key 和一致的接口，访问全球领先的 AI 服务。

<CardGroup cols={2}>
  <Card title="AI 聊天" icon="comments" href="/guides/claude/claude_chat_completions">
    通过 OpenAI 兼容接口访问 Claude、GPT、Gemini、DeepSeek、Grok、Kimi 等模型。
  </Card>
  <Card title="AI 图像" icon="image" href="/guides/midjourney/midjourney_imagine">
    使用 Midjourney、Flux、DALL·E、Seedream 等生成图像。
  </Card>
  <Card title="AI 视频" icon="video" href="/guides/sora/sora_videos">
    使用 Sora、Veo、Luma、Kling、Hailuo、Seedance 等生成视频。
  </Card>
  <Card title="AI 音频" icon="music" href="/guides/suno/suno_audios">
    使用 Suno、Fish Audio、Producer 等生成音乐和音频。
  </Card>
</CardGroup>

## 核心优势

- **统一 API** — 一个 API Key 访问 50+ AI 服务
- **OpenAI 兼容** — Claude、Gemini、DeepSeek 等均可通过 OpenAI 接口直接调用
- **交互式沙盒** — 在文档中直接测试每个 API
- **按量付费** — 无订阅费，按实际使用量计费
- **MCP 服务器** — 原生支持 Cursor、Claude 等 AI 编程工具

## 快速链接

<CardGroup cols={3}>
  <Card title="获取 API Key" icon="key" href="https://platform.acedata.cloud">
    注册并获取 API Token
  </Card>
  <Card title="API 参考" icon="code" href="/api-reference/introduction">
    交互式 API 文档
  </Card>
  <Card title="MCP 服务器" icon="plug" href="/mcp/overview">
    将 AI 助手连接到我们的 API
  </Card>
</CardGroup>
"""
    (output_dir / "introduction.mdx").write_text(intro, encoding="utf-8")

    # Quickstart page
    quickstart = """---
title: "快速开始"
description: "5 分钟上手 Ace Data Cloud API"
---

## 1. 获取 API Key

在 [platform.acedata.cloud](https://platform.acedata.cloud) 注册账号并创建 API 凭证。

<Steps>
  <Step title="注册账号">
    访问 [platform.acedata.cloud](https://platform.acedata.cloud) 完成注册。
  </Step>
  <Step title="订阅服务">
    浏览可用服务，点击**获取**完成订阅。大部分服务提供免费额度。
  </Step>
  <Step title="创建凭证">
    进入服务的**凭证**页面，创建 API Token。
  </Step>
</Steps>

## 2. 发送第一个请求

所有 API 使用 Bearer Token 认证：

<CodeGroup>

```bash cURL
curl -X POST https://api.acedata.cloud/v1/chat/completions \\
  -H "Authorization: Bearer YOUR_API_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [{"role": "user", "content": "你好！"}]
  }'
```

```python Python
import requests

response = requests.post(
    "https://api.acedata.cloud/v1/chat/completions",
    headers={"Authorization": "Bearer YOUR_API_TOKEN"},
    json={
        "model": "claude-sonnet-4-20250514",
        "messages": [{"role": "user", "content": "你好！"}],
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
    messages: [{ role: "user", content: "你好！" }],
  }),
});
const data = await response.json();
console.log(data);
```

</CodeGroup>

## 3. 探索更多 API

<CardGroup cols={2}>
  <Card title="API 参考" icon="code" href="/api-reference/introduction">
    浏览并交互式测试所有 API 端点
  </Card>
  <Card title="集成指南" icon="book" href="/guides/claude/claude_chat_completions">
    每个服务的详细集成教程
  </Card>
</CardGroup>
"""
    (output_dir / "quickstart.mdx").write_text(quickstart, encoding="utf-8")

    # Authentication page
    auth_page = """---
title: "认证"
description: "如何使用 Ace Data Cloud API 进行身份认证"
---

所有 Ace Data Cloud API 使用 **Bearer Token** 认证。

## 获取 Token

1. 在 [platform.acedata.cloud](https://platform.acedata.cloud) 注册账号
2. 订阅需要的服务
3. 为每个服务创建凭证（API Token）

## 使用 Token

在每个请求的 `Authorization` 头中包含 Token：

```bash
Authorization: Bearer YOUR_API_TOKEN
```

<Note>
  每个 Token 绑定到特定的服务订阅。不同服务使用不同的 Token，或创建**全局**凭证以跨服务使用。
</Note>

## 速率限制

速率限制因服务和订阅级别而异。超出限制时，API 返回 `429 Too Many Requests`。

## 安全最佳实践

- 不要在客户端代码中暴露 API Token
- 使用环境变量存储 Token
- 定期轮换 Token
- 开发和生产环境使用不同的 Token
"""
    (output_dir / "authentication.mdx").write_text(auth_page, encoding="utf-8")

    # API Reference introduction
    api_ref_dir = output_dir / "api-reference"
    api_ref_dir.mkdir(parents=True, exist_ok=True)
    api_intro = """---
title: "API 参考"
description: "Ace Data Cloud 所有服务的交互式 API 参考文档"
---

## 基础 URL

所有 API 端点的基础地址：

```
https://api.acedata.cloud
```

## 认证

所有端点需要 Bearer Token 认证：

```
Authorization: Bearer YOUR_API_TOKEN
```

## 在线测试

本参考文档中的每个端点都包含交互式沙盒。输入 API Token 即可直接在浏览器中测试请求。

<Note>
  在 [platform.acedata.cloud](https://platform.acedata.cloud) 获取 API Token。
</Note>

## 服务分类

按类别浏览 API：

<CardGroup cols={2}>
  <Card title="AI 聊天" icon="comments">
    Claude、OpenAI、Gemini、DeepSeek、Grok、Kimi — OpenAI 兼容聊天补全接口
  </Card>
  <Card title="AI 图像" icon="image">
    Midjourney、Flux、Seedream、DALL·E、QR Art、人脸工具
  </Card>
  <Card title="AI 视频" icon="video">
    Sora、Veo、Luma、Kling、Hailuo、Seedance、Wan
  </Card>
  <Card title="AI 音频" icon="music">
    Suno、Fish Audio、Producer
  </Card>
</CardGroup>
"""
    (api_ref_dir / "introduction.mdx").write_text(api_intro, encoding="utf-8")

    log("Step 5 done")

    # ---------------------------------------------------------------------------
    # 6. Copy pre-generated SEO pages (tutorials, comparisons, use-cases, blog)
    # ---------------------------------------------------------------------------
    log()
    log("=" * 60)
    log("Step 6/8: Copy pre-generated SEO pages from PlatformBackend/docs")
    log("=" * 60)
    _copy_seo_pages(backend_dir / "docs" / "zh-CN", output_dir)
    log("Step 6 done")

    # ---------------------------------------------------------------------------
    # 6b. Copy pre-translated content from PlatformBackend/docs/{lang}/
    # ---------------------------------------------------------------------------
    log()
    log("=" * 60)
    log("Step 6b: Copy pre-translated content from PlatformBackend")
    log("=" * 60)
    _sync_translated_content(
        backend_dir,
        output_dir,
        doc_service_map,
        service_names,
        categories,
        dev_docs_by_service,
    )
    log("Step 6b done")

    # ---------------------------------------------------------------------------
    # 7. Generate docs.json
    # ---------------------------------------------------------------------------
    log()
    log("=" * 60)
    log("Step 7/8: Generate docs.json")
    log("=" * 60)
    navigation = build_navigation(
        categories, service_names, dev_docs_by_service, output_dir
    )

    docs_json = {
        "$schema": "https://mintlify.com/docs.json",
        "theme": "mint",
        "name": "Ace Data Cloud",
        "description": "统一 AI API 平台 — LLM 聊天、图像生成、视频生成、音乐、搜索等。",
        "colors": {
            "primary": "#6366F1",
            "light": "#818CF8",
            "dark": "#4F46E5",
        },
        "favicon": "/favicon.ico",
        "logo": {
            "light": "/logo/light.png",
            "dark": "/logo/dark.png",
            "href": "/",
        },
        "navbar": {
            "links": [
                {"type": "github", "href": "https://github.com/AceDataCloud"},
                {"label": "平台", "href": "https://platform.acedata.cloud"},
            ],
            "primary": {
                "type": "button",
                "label": "获取 API Key",
                "href": "https://platform.acedata.cloud",
            },
        },
        "navigation": _build_docs_json_navigation(
            navigation, categories, service_names, dev_docs_by_service, output_dir
        ),
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
    log("Step 7 done: Generated docs.json")

    # ---------------------------------------------------------------------------
    # 8. Cleanup: remove old starter template files
    # ---------------------------------------------------------------------------
    log()
    log("=" * 60)
    log("Step 8/8: Cleanup")
    log("=" * 60)
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
            log(f"  Removed starter file: {f}")

    # Remove empty dirs
    for d in ["essentials", "ai-tools", "snippets", "api-reference/endpoint"]:
        dp = output_dir / d
        if dp.exists() and not any(dp.iterdir()):
            dp.rmdir()

    log()
    log("=" * 60)
    log("Sync complete!")
    log(f"  OpenAPI specs: {len(generated_specs)}")
    log(f"  Guide pages:   {sum(len(v) for v in dev_docs_by_service.values())}")
    log(f"  MCP pages:     {mcp_count}")
    log(f"  Total time:    {_time.time() - _T0:.1f}s")
    log("=" * 60)


if __name__ == "__main__":
    main()
