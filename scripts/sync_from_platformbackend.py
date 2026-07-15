#!/usr/bin/env python3
"""Sync generated Docs content from PlatformBackend.

This script keeps the post-restructure Docs IA intact. It refreshes generated
OpenAPI specs and localized guide/MCP pages, but it does not regenerate the
whole site or overwrite docs.json.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

START = time.time()

BASE_URL = "https://api.acedata.cloud"
DOCUMENTS_URL = "https://platform.acedata.cloud/api/v1/documents/?limit=1000"
GUIDE_DESCRIPTIONS = {
    "zh-Hans": "{service} 集成指南 - Ace Data Cloud",
    "zh-Hant": "{service} 整合指南 - Ace Data Cloud",
    "en": "{service} integration guide - Ace Data Cloud",
}

LANGUAGE_SOURCE_DIRS: dict[str, str] = {
    "zh-Hans": "zh-CN",
    "zh-Hant": "zh-tw",
    "en": "en",
    "ja": "ja",
    "ko": "ko",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "pt": "pt",
    "ru": "ru",
    "ar": "ar",
    "it": "it",
    "sv": "sv",
    "uk": "uk",
    "pl": "pl",
}

EXCLUDED_SERVICES = {
    "chatdoc",
    "pika",
    "pixverse",
    "riffusion",
    "udio",
}

SKIP_DOC_KEYS = {
    "acedataext",
    "application_remaining_amount",
    "nexior_vercel_deployment",
    "acedatacloud_chat_api_integration_article",
    "tw_comments",
    "tw_posts",
    "tw_users",
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

VALID_SCHEMA_KEYS = {
    "$ref",
    "additionalProperties",
    "allOf",
    "anyOf",
    "const",
    "default",
    "deprecated",
    "description",
    "discriminator",
    "enum",
    "example",
    "examples",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "format",
    "items",
    "maximum",
    "maxItems",
    "maxLength",
    "maxProperties",
    "minimum",
    "minItems",
    "minLength",
    "minProperties",
    "multipleOf",
    "not",
    "nullable",
    "oneOf",
    "pattern",
    "properties",
    "readOnly",
    "required",
    "title",
    "type",
    "uniqueItems",
    "writeOnly",
}


def log(message: str) -> None:
    elapsed = time.time() - START
    print(f"[{elapsed:6.1f}s] {message}", flush=True)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(value: str) -> str:
    return value.lower().replace("-", "").replace("_", "")


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def title_from_t_key(key: str) -> str:
    for prefix in ("api_description_", "service_title_", "service_description_"):
        if key.startswith(prefix):
            key = key[len(prefix) :]
            break
    return key.replace("_", " ").title()


def resolve_t_keys(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\$t\(([^)]+)\)", lambda match: title_from_t_key(match.group(1)), value)
    if isinstance(value, dict):
        return {key: resolve_t_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_t_keys(item) for item in value]
    return value


def clean_schema(value: Any) -> Any:
    if isinstance(value, list):
        return [clean_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if key not in VALID_SCHEMA_KEYS and not key.startswith("x-"):
            continue
        if key == "type" and item == "float":
            cleaned["type"] = "number"
            cleaned.setdefault("format", "float")
        elif key == "type" and item == "int":
            cleaned["type"] = "integer"
        elif key == "const":
            cleaned["enum"] = [item]
        elif key in {"items", "additionalProperties", "not"}:
            cleaned[key] = clean_schema(item)
        elif key == "properties" and isinstance(item, dict):
            cleaned[key] = {name: clean_schema(schema) for name, schema in item.items()}
        elif key in {"oneOf", "allOf", "anyOf"}:
            cleaned[key] = clean_schema(item)
        else:
            cleaned[key] = item

    if cleaned.get("required") == []:
        cleaned.pop("required")
    return cleaned


def clean_openapi_spec(spec: dict[str, Any]) -> dict[str, Any]:
    response_keys = {"description", "headers", "content", "links"}
    request_body_keys = {"description", "content", "required"}
    media_type_keys = {"schema", "example", "examples", "encoding"}
    cleaned = dict(spec)
    cleaned_paths: dict[str, Any] = {}

    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            cleaned_paths[path] = path_item
            continue
        next_path_item: dict[str, Any] = {}
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                next_path_item[method] = operation
                continue
            next_operation = dict(operation)

            request_body = next_operation.get("requestBody")
            if isinstance(request_body, dict):
                next_request_body = {
                    key: item for key, item in request_body.items() if key in request_body_keys or key.startswith("x-")
                }
                if isinstance(next_request_body.get("content"), dict):
                    next_request_body["content"] = {
                        content_type: {
                            key: clean_schema(item) if key == "schema" else item
                            for key, item in media_type.items()
                            if key in media_type_keys
                        }
                        for content_type, media_type in next_request_body["content"].items()
                        if isinstance(media_type, dict)
                    }
                next_operation["requestBody"] = next_request_body

            responses = next_operation.get("responses")
            if isinstance(responses, dict):
                next_responses: dict[str, Any] = {}
                for status_code, response in responses.items():
                    if not isinstance(response, dict):
                        next_responses[status_code] = response
                        continue
                    next_response = {key: item for key, item in response.items() if key in response_keys or key.startswith("x-")}
                    next_response.setdefault("description", "Response")
                    if isinstance(next_response.get("content"), dict):
                        next_response["content"] = {
                            content_type: {
                                key: clean_schema(item) if key == "schema" else item
                                for key, item in media_type.items()
                                if key in media_type_keys
                            }
                            for content_type, media_type in next_response["content"].items()
                            if isinstance(media_type, dict)
                        }
                    next_responses[status_code] = next_response
                next_operation["responses"] = next_responses

            parameters = next_operation.get("parameters")
            if isinstance(parameters, list):
                next_operation["parameters"] = [
                    {key: clean_schema(item) if key == "schema" else item for key, item in parameter.items()}
                    for parameter in parameters
                    if isinstance(parameter, dict)
                ]

            next_path_item[method] = next_operation
        cleaned_paths[path] = next_path_item

    cleaned["paths"] = cleaned_paths
    return inline_path_refs(cleaned)


def inline_path_refs(spec: dict[str, Any]) -> dict[str, Any]:
    """Inline any ``$ref`` that points into ``#/paths/...``.

    Such cross-operation refs (e.g. one model's requestBody reusing another's
    schema) are non-idiomatic targets that Mintlify's OpenAPI validator rejects,
    failing the entire docs build. A single bad spec silently froze the whole
    site for weeks. Resolving these refs to self-contained schemas keeps every
    generated spec valid no matter how the upstream source was authored. No-op
    for specs without such refs.
    """

    def resolve(ref: str) -> Any:
        cur: Any = spec
        for token in unquote(ref)[2:].split("/"):
            cur = cur[token.replace("~1", "/").replace("~0", "~")]
        return cur

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/paths/"):
                try:
                    return walk(copy.deepcopy(resolve(ref)))
                except (KeyError, TypeError):
                    return node
            return {key: walk(value) for key, value in node.items()}
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(spec)


def path_short_title(path: str, method: str) -> str:
    segments = [segment for segment in path.strip("/").split("/") if segment]
    if len(segments) > 1:
        segments = segments[1:]
    title = " ".join(segment.replace("-", " ").replace("_", " ") for segment in segments).title()
    return title or f"{method.upper()} {path}"


def clean_verbose_summaries(spec: dict[str, Any]) -> None:
    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue
            summary = operation.get("summary", "")
            if isinstance(summary, str) and len(summary) > 80:
                operation.setdefault("description", summary)
                operation["summary"] = path_short_title(path, method)


def collect_page_paths(value: Any, result: list[str]) -> None:
    if isinstance(value, str):
        result.append(value)
    elif isinstance(value, list):
        for item in value:
            collect_page_paths(item, result)
    elif isinstance(value, dict):
        for item in value.values():
            collect_page_paths(item, result)


def get_documented_service_aliases(output_dir: Path) -> set[str]:
    aliases = {path.stem for path in (output_dir / "openapi").glob("*.json")}
    docs_json = load_json(output_dir / "docs.json")
    page_paths: list[str] = []
    collect_page_paths(docs_json.get("navigation", {}), page_paths)
    for page_path in page_paths:
        parts = page_path.split("/")
        if "guides" not in parts:
            continue
        index = parts.index("guides")
        if index + 1 < len(parts) and len(parts) > index + 2:
            aliases.add(parts[index + 1])
    return aliases


def load_services(backend_dir: Path, documented_aliases: set[str]) -> list[dict[str, Any]]:
    services = load_json(backend_dir / "cost" / "service_api_mapping.json")
    return [
        service
        for service in services
        if service.get("alias") not in EXCLUDED_SERVICES
        and (not service.get("private") or service.get("alias") in documented_aliases)
    ]


def load_openapi_spec(backend_dir: Path, api_id: str) -> dict[str, Any] | None:
    path = backend_dir / "openapi" / f"{api_id}.json"
    if not path.exists():
        return None
    return load_json(path)


def merge_openapi_specs(backend_dir: Path, service: dict[str, Any]) -> dict[str, Any] | None:
    apis = service.get("apis") or []
    if not apis:
        return None

    display_name = service.get("display_name") or service.get("alias", "API")
    merged: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {
            "title": display_name,
            "version": "1.0.0",
            "description": f"API reference for {display_name} on Ace Data Cloud.",
        },
        "servers": [{"url": BASE_URL, "description": "Ace Data Cloud API"}],
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
            log(f"  WARNING: missing OpenAPI spec for {api.get('id')} ({service.get('alias')})")
            continue
        merged["paths"].update(spec.get("paths", {}))
        for key in ("schemas", "requestBodies", "responses", "parameters"):
            values = spec.get("components", {}).get(key)
            if values:
                merged["components"].setdefault(key, {}).update(values)

    if not merged["paths"]:
        return None

    merged = resolve_t_keys(merged)
    clean_verbose_summaries(merged)
    return clean_openapi_spec(merged)


def build_doc_service_map(services: list[dict[str, Any]], backend_dir: Path) -> dict[str, str | None]:
    path_to_alias: dict[str, str] = {}
    for service in services:
        alias = service["alias"]
        for api in service.get("apis") or []:
            path = api.get("path") or ""
            normalized = normalize(path.strip("/").replace("/", "_"))
            if normalized:
                path_to_alias[normalized] = alias

    alias_norms = sorted(((service["alias"], normalize(service["alias"])) for service in services), key=lambda item: -len(item[1]))
    result: dict[str, str | None] = {}
    zh_docs = backend_dir / "docs"

    markdown_files = sorted(zh_docs.glob("development_*.md"))
    if not markdown_files:
        raise RuntimeError(f"No development docs found in {zh_docs}")

    for markdown_file in markdown_files:
        doc_key = markdown_file.stem.removeprefix("development_")
        if doc_key.endswith("_title"):
            continue
        if doc_key in SKIP_DOC_KEYS:
            result[doc_key] = None
            continue

        normalized_key = normalize(doc_key)
        if normalized_key in path_to_alias:
            result[doc_key] = path_to_alias[normalized_key]
            continue

        matched_alias: str | None = None
        for normalized_path, alias in sorted(path_to_alias.items(), key=lambda item: -len(item[0])):
            if normalized_key.startswith(normalized_path):
                matched_alias = alias
                break
        if matched_alias:
            result[doc_key] = matched_alias
            continue

        best_alias: str | None = None
        best_overlap = 0
        for normalized_path, alias in path_to_alias.items():
            common = 0
            for left, right in zip(normalized_key, normalized_path):
                if left != right:
                    break
                common += 1
            min_length = min(len(normalized_key), len(normalized_path))
            if min_length and common / min_length >= 0.8 and common > best_overlap:
                best_overlap = common
                best_alias = alias
        if best_alias:
            result[doc_key] = best_alias
            continue

        for alias, normalized_alias in alias_norms:
            if normalized_key.startswith(normalized_alias):
                matched_alias = alias
                break
        if matched_alias:
            result[doc_key] = matched_alias
            continue

        log(f"  WARNING: unmapped development doc {doc_key}, skipping")
        result[doc_key] = None

    return result


def index_localized_guides(payload: Any, language: str) -> dict[str, dict[str, str]]:
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise RuntimeError(f"Invalid document feed for {language}")

    guides: dict[str, dict[str, str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        sibling = item.get("sibling")
        if not isinstance(sibling, dict) or not sibling.get("content"):
            continue

        candidates = [item.get("alias", ""), sibling.get("alias", "").removesuffix("-integration")]
        api = item.get("api")
        api_path = (api.get("path") or "").strip("/").replace("/", "_") if isinstance(api, dict) else ""

        guide = {
            "content": sibling["content"],
            "title": sibling.get("title") or sibling.get("name") or "",
        }
        for candidate in candidates:
            if candidate:
                key = normalize(candidate)
                existing = guides.get(key)
                if existing and existing != guide:
                    raise RuntimeError(f"Conflicting localized guide key {candidate!r} for {language}")
                guides[key] = guide
        if api_path:
            guides.setdefault(normalize(api_path), guide)

    if not guides:
        raise RuntimeError(f"No localized guides found for {language}")
    return guides


def load_localized_guides(language: str) -> dict[str, dict[str, str]]:
    request = Request(DOCUMENTS_URL, headers={"Accept-Language": language})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=60) as response:
                payload = json.load(response)
            return index_localized_guides(payload, language)
        except (HTTPError, URLError, OSError, RuntimeError, json.JSONDecodeError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def guide_description(output_language: str, service_name: str) -> str:
    template = GUIDE_DESCRIPTIONS.get(output_language, "{service} API guide - Ace Data Cloud")
    return template.format(service=service_name)


def sanitize_html_for_mdx(content: str) -> str:
    parts = re.split(r"(^```.*?^```)", content, flags=re.MULTILINE | re.DOTALL)
    for index, part in enumerate(parts):
        if part.startswith("```"):
            continue
        part = re.sub(r"(<[a-zA-Z][^>]*)\bclass=", r"\1className=", part)
        for tag in ("img", "br", "hr", "input", "source", "meta", "link"):
            part = re.sub(rf"(<{tag}\b[^>]*?)(?<!/)>", rf"\1 />", part)
        part = re.sub(r"<(https?://[^>]+)>", r"[\1](\1)", part)
        part = re.sub(r"<(?![a-zA-Z/!])", r"&lt;", part)
        parts[index] = part
    return "".join(parts)


def convert_markdown_to_mdx(content: str, fallback_title: str, description: str | None = None) -> str:
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else fallback_title
    if title_match:
        content = content[: title_match.start()] + content[title_match.end() :]

    content = re.sub(r"\$t\(([^)]+)\)", lambda match: title_from_t_key(match.group(1)), content)
    content = sanitize_html_for_mdx(content).strip()

    frontmatter = ["---", f"title: {yaml_quote(title)}"]
    if description:
        frontmatter.append(f"description: {yaml_quote(description)}")
    frontmatter.append("---")
    return "\n".join(frontmatter) + "\n\n" + content + "\n"


def sync_openapi(backend_dir: Path, output_dir: Path, services: list[dict[str, Any]]) -> None:
    log("Syncing OpenAPI specs")
    openapi_dir = output_dir / "openapi"
    openapi_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    for service in services:
        spec = merge_openapi_specs(backend_dir, service)
        if not spec:
            continue
        write_json(openapi_dir / f"{service['alias']}.json", spec)
        generated += 1
    log(f"  wrote {generated} OpenAPI specs")


def sync_guides(
    backend_dir: Path,
    output_dir: Path,
    services_by_alias: dict[str, dict[str, Any]],
    doc_service_map: dict[str, str | None],
    languages: list[str],
) -> None:
    log("Syncing localized guides")
    total = 0
    source_dir = backend_dir / "docs"
    markdown_files = sorted(source_dir.glob("development_*.md"))
    if not markdown_files:
        raise RuntimeError(f"No development docs found in {source_dir}")

    for output_language in languages:
        source_language = LANGUAGE_SOURCE_DIRS.get(output_language, output_language)
        localized_guides = None if output_language == "zh-Hans" else load_localized_guides(source_language)
        language_total = 0
        missing_guides: list[str] = []

        for markdown_file in markdown_files:
            doc_key = markdown_file.stem.removeprefix("development_")
            if doc_key.endswith("_title") or doc_key in SKIP_DOC_KEYS:
                continue
            service_alias = doc_service_map.get(doc_key)
            if not service_alias:
                continue
            service = services_by_alias.get(service_alias, {})
            service_name = service.get("display_name") or service_alias.replace("-", " ").title()
            localized_guide = localized_guides.get(normalize(doc_key)) if localized_guides else None
            if localized_guides and not localized_guide:
                missing_guides.append(doc_key)
                continue
            content = localized_guide["content"] if localized_guide else markdown_file.read_text(encoding="utf-8")
            fallback_title = localized_guide["title"] if localized_guide else doc_key.replace("_", " ").title()
            mdx = convert_markdown_to_mdx(
                content,
                fallback_title,
                guide_description(output_language, service_name),
            )
            write_text(output_dir / output_language / "guides" / service_alias / f"{doc_key}.mdx", mdx)
            total += 1
            language_total += 1

        if language_total == 0:
            raise RuntimeError(f"No guide pages generated for {output_language}")
        if missing_guides:
            log(f"  WARNING: {output_language} missing {len(missing_guides)} localized guides: {', '.join(missing_guides)}")
        log(f"  {output_language}: wrote {language_total} guide pages")

        x402_path = source_dir / "x402_integration_guide.md" if output_language == "zh-Hans" else None
        if x402_path and x402_path.exists():
            mdx = convert_markdown_to_mdx(x402_path.read_text(encoding="utf-8"), "X402 Integration Guide")
            write_text(output_dir / output_language / "guides" / "x402.mdx", mdx)
            total += 1

        # OAuth "Sign in with Ace Data Cloud" is a platform-level guide (no service alias),
        # so the loop above skips it — emit it explicitly like x402.
        oauth_path = source_dir / "development_oauth_apps.md" if output_language == "zh-Hans" else None
        if oauth_path and oauth_path.exists():
            mdx = convert_markdown_to_mdx(oauth_path.read_text(encoding="utf-8"), "OAuth Integration Guide")
            write_text(output_dir / output_language / "guides" / "oauth.mdx", mdx)
            total += 1

    log(f"  wrote {total} guide pages")


def sync_mcp_docs(backend_dir: Path, output_dir: Path, languages: list[str]) -> None:
    log("Syncing localized MCP docs")
    total = 0
    for output_language in languages:
        if output_language != "zh-Hans":
            continue
        source_dir = backend_dir / "docs"
        for markdown_file in sorted(source_dir.glob("mcp_*.md")):
            mcp_name = markdown_file.stem.removeprefix("mcp_")
            mdx = convert_markdown_to_mdx(
                markdown_file.read_text(encoding="utf-8"),
                f"{mcp_name.replace('-', ' ').title()} MCP Server",
                f"{mcp_name} MCP server integration",
            )
            write_text(output_dir / output_language / "mcp" / f"{mcp_name}.mdx", mdx)
            total += 1
    log(f"  wrote {total} MCP pages")


def get_docs_languages(output_dir: Path) -> list[str]:
    docs_json = load_json(output_dir / "docs.json")
    languages = [entry["language"] for entry in docs_json.get("navigation", {}).get("languages", [])]
    return [language for language in languages if language in LANGUAGE_SOURCE_DIRS]


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Docs generated content from PlatformBackend")
    parser.add_argument("--backend-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    backend_dir = args.backend_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not (backend_dir / "cost" / "service_api_mapping.json").exists():
        raise SystemExit(f"Invalid PlatformBackend directory: {backend_dir}")
    if not (output_dir / "docs.json").exists():
        raise SystemExit(f"Invalid Docs output directory: {output_dir}")

    documented_aliases = get_documented_service_aliases(output_dir)
    services = load_services(backend_dir, documented_aliases)
    services_by_alias = {service["alias"]: service for service in services}
    doc_service_map = build_doc_service_map(services, backend_dir)
    languages = get_docs_languages(output_dir)
    log(f"Languages: {', '.join(languages)}")

    sync_openapi(backend_dir, output_dir, services)
    sync_guides(backend_dir, output_dir, services_by_alias, doc_service_map, languages)
    sync_mcp_docs(backend_dir, output_dir, languages)
    log("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
