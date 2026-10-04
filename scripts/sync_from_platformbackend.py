#!/usr/bin/env python3
"""Sync generated Docs content from PlatformBackend.

This script keeps the post-restructure Docs IA intact. It refreshes generated
OpenAPI specs and localized guide/MCP pages, but it does not regenerate the
whole site or overwrite docs.json.
"""

from __future__ import annotations

import argparse
import copy
import html
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

START = time.time()

BASE_URL = "https://api.acedata.cloud"
PUBLICATION_URL = "https://platform.acedata.cloud/api/v1/documents/publication/"
SHARED_GUIDE_ALIASES = {"kling_assets": ("kling_elements", "kling_voices")}
TRANSACTION_FILE = ".docs-sync-transaction.json"
BACKUP_DIR = ".docs-sync-backup"
EXACT_MAP_PATH = Path(__file__).parent / "data" / "coding-docs-map.json"
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
    "el": "el",
    "fi": "fi",
    "sr": "sr",
}

EXCLUDED_SERVICES = {
    "chatdoc",
    "pika",
    "pixverse",
    "riffusion",
    "udio",
}
DOC_ONLY_SERVICES = {"coding"}

# Hold these operations even when the Backend mapping has not yet refreshed.
PRIVATE_API_PATHS = {
    "/kling/apparel",
    "/kling/virtual-try-on",
    "/kling/voices",
    "/kling/elements",
}

SKIP_DOC_KEYS = {
    "acedataext",
    # These endpoints are private pending successful production acceptance.
    "kling_apparel",
    "kling_virtual_try_on",
    "kling_assets",
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


def load_denylist(*, required: bool = False) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    groups: dict[str, list[str]] = {"identifier": [], "host": [], "term": []}
    for raw in os.environ.get("PUBLIC_EXAMPLE_DENYLIST", "").splitlines():
        kind, separator, value = raw.strip().partition(":")
        if separator and kind in groups and value.strip():
            groups[kind].append(value.strip().casefold().removeprefix("*."))
    result = tuple(groups["identifier"]), tuple(groups["host"]), tuple(groups["term"])
    if required and any(not values for values in result):
        raise RuntimeError("PUBLIC_EXAMPLE_DENYLIST is required")
    return result


def decode_layers(value: str, limit: int = 3) -> str:
    decoded = value
    for _ in range(limit):
        next_value = html.unescape(unquote(decoded))
        if next_value == decoded:
            return decoded
        decoded = next_value
    if html.unescape(unquote(decoded)) != decoded:
        raise ValueError("encoding depth exceeds limit")
    return decoded


def response_blocks(content: str) -> list[str]:
    blocks: list[str] = []
    fence_re = re.compile(r"^(?P<prefix>(?:\s*>\s?|\s*(?:[-+*]|\d+[.)])\s+)*\s{0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
    opened = None
    body: list[str] = []
    offset = 0
    for line in content.splitlines(keepends=True):
        match = fence_re.match(line.rstrip("\r\n"))
        if opened is None:
            if match:
                opened = (match.group("fence")[0], len(match.group("fence")), offset, match.group("prefix"))
                body = []
        else:
            marker, length, start, prefix = opened
            continuation = line[: len(prefix)]
            same = not prefix or continuation == prefix or continuation.isspace()
            if match and same and match.group("fence")[0] == marker and len(match.group("fence")) >= length and not match.group("info").strip():
                context = content[max(0, start - 200) : start]
                if re.search(r"(?:response|result|output|返回|响应|结果)", context, re.IGNORECASE):
                    blocks.append("".join(body))
                opened = None
                body = []
            else:
                body.append(line[len(prefix) :] if prefix and (line.startswith(prefix) or continuation.isspace()) else line)
        offset += len(line)
    return blocks


def contains_host(content: str, hosts: tuple[str, ...]) -> bool:
    for url in re.findall(r"https?://[^\s\"'<>]+", content, re.IGNORECASE):
        try:
            hostname = (urlsplit(url).hostname or "").rstrip(".").casefold()
        except ValueError:
            continue
        if any(hostname == host or hostname.endswith(f".{host}") for host in hosts):
            return True
    return False


def sanitize_artifact_values(value: Any, counters: dict[str, int], field: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_artifact_values(item, counters, key) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_artifact_values(item, counters, field) for item in value]
    if not isinstance(value, str) or not field or not invalid_artifact_urls(value, field):
        return value
    lowered = field.casefold()
    kind = "video" if "video" in lowered else "audio" if "audio" in lowered or "voice" in lowered else "image"
    counters[kind] += 1
    bases = {
        "image": "https://cdn.acedata.cloud/e724d7f13d.png",
        "video": "https://cdn.acedata.cloud/assets/examples/gemini/04a043bd-6b23-4b4e-945c-ce48158c3eee-3a89912507c7.mp4",
        "audio": "https://cdn.acedata.cloud/assets/examples/fish/5ade0339-5f11-487e-aacc-06a908271706-8e3fcb0e5547.mp3",
    }
    return f"{bases[kind]}?example={kind}-{counters[kind]:03d}"


def neutralize_response_terms(content: str, terms: tuple[str, ...], sanitize_artifacts: bool = True) -> str:
    pattern = re.compile(r"^(`{3,}|~{3,})[^\n]*\n(.*?)^\1\s*$", re.MULTILINE | re.DOTALL)
    pieces: list[str] = []
    cursor = 0
    for match in pattern.finditer(content):
        context = content[max(0, match.start() - 200) : match.start()]
        body = match.group(2)
        if re.search(r"(?:response|result|output|返回|响应|结果)", context, re.IGNORECASE):
            for term in terms:
                body = re.sub(re.escape(term), "model service", body, flags=re.IGNORECASE)
            if sanitize_artifacts:
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    pass
                else:
                    payload = sanitize_artifact_values(payload, {"image": 0, "video": 0, "audio": 0})
                    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        pieces.extend((content[cursor : match.start(2)], body))
        cursor = match.end(2)
    pieces.append(content[cursor:])
    return "".join(pieces)


RETIRED_PUBLIC_ASSETS = {
    "https://platform2.cdn.acedata.cloud/fish/64adc04b-c196-4a0f-9070-222ba101ce6c.wav":
        "https://cdn.acedata.cloud/assets/examples/fish/64adc04b-c196-4a0f-9070-222ba101ce6c-fc50de38c165.wav",
}


def neutralize_generated_tree(root: Path, denylist: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]) -> None:
    terms = denylist[2]
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.casefold() in {".md", ".mdx"}:
            content = path.read_text(encoding="utf-8")
            for old_url, new_url in RETIRED_PUBLIC_ASSETS.items():
                content = content.replace(old_url, new_url)
            relative = str(path.relative_to(root))
            content_result = any(name in relative for name in ("serp_google", "tw_comments", "tw_posts", "tw_users"))
            updated = neutralize_response_terms(content, terms, sanitize_artifacts=not content_result)
            if updated != content:
                path.write_text(updated, encoding="utf-8")


def invalid_artifact_urls(value: Any, field: str | None = None) -> bool:
    if isinstance(value, dict):
        return any(invalid_artifact_urls(item, key) for key, item in value.items())
    if isinstance(value, list):
        return any(invalid_artifact_urls(item, field) for item in value)
    if not isinstance(value, str) or not field or not field.casefold().endswith(("_url", "_urls")):
        return False
    if field.casefold() in {"callback_url", "webhook_url", "payment_url", "expanded_url", "display_url", "site_url"} or not value.strip():
        return False
    try:
        parsed = urlsplit(decode_layers(value))
    except ValueError:
        return True
    host = (parsed.hostname or "").rstrip(".").casefold()
    if parsed.scheme.casefold() != "https" or host not in {"cdn.acedata.cloud", "platform.cdn.acedata.cloud", "suro.id"}:
        return True
    path = parsed.path.casefold()
    return path.startswith("/examples/") and not path.startswith("/assets/examples/")


def invalid_openapi_response_artifact_urls(spec: Any) -> bool:
    if not isinstance(spec, dict):
        return True
    for path_item in spec.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if isinstance(operation, dict) and invalid_artifact_urls(operation.get("responses", {})):
                return True
    return False


def find_generated_tree_violations(root: Path, denylist: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in {".json", ".md", ".mdx"}:
            continue
        relative = str(path.relative_to(root))
        try:
            raw_content = path.read_text(encoding="utf-8")
            content = decode_layers(raw_content).casefold()
        except ValueError:
            findings.append(f"{relative} [undecodable]")
            continue
        identifiers, hosts, terms = denylist
        categories: list[str] = []
        if any(re.search(rf"(?<![\w-]){re.escape(value)}(?![\w-])", content) for value in identifiers):
            categories.append("identifier")
        if contains_host(content, hosts):
            categories.append("host")
        if path.suffix.casefold() == ".json" and relative.startswith("openapi/"):
            has_term = any(term in content for term in terms)
        else:
            has_term = any(term in block.casefold() for block in response_blocks(content) for term in terms)
        if has_term:
            categories.append("term")
        invalid_url = False
        if path.suffix.casefold() == ".json" and relative.startswith("openapi/"):
            try:
                invalid_url = invalid_openapi_response_artifact_urls(json.loads(raw_content))
            except json.JSONDecodeError:
                invalid_url = True
        elif not any(name in relative for name in ("serp_google", "tw_comments", "tw_posts", "tw_users")):
            for block in response_blocks(raw_content):
                try:
                    payload = json.loads(block)
                except json.JSONDecodeError:
                    continue
                invalid_url = invalid_url or invalid_artifact_urls(payload)
        if invalid_url:
            categories.append("artifact-url")
        if categories:
            findings.append(f"{relative} [{','.join(categories)}]")
    return findings


def validate_generated_tree(root: Path, denylist: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]) -> None:
    findings = find_generated_tree_violations(root, denylist)
    if findings:
        details = "\n".join(f"  - {finding}" for finding in findings)
        raise RuntimeError(f"Generated customer-facing tree contains managed values in {len(findings)} file(s):\n{details}")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fsync_dir(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_json(path: Path, data: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)
    fsync_dir(path.parent)


def transaction_paths(output_dir: Path) -> tuple[Path, Path]:
    return output_dir.parent / TRANSACTION_FILE, output_dir.parent / BACKUP_DIR


def validate_manifest(manifest: Any) -> None:
    phases = {"initializing", "publishing", "committed"}
    states = {"pending", "backing_up", "backed_up", "publishing", "published", "restoring", "restored"}
    if not isinstance(manifest, dict) or manifest.get("phase") not in phases or not isinstance(manifest.get("items"), list):
        raise RuntimeError("Invalid Docs sync transaction manifest")
    seen: set[str] = set()
    for item in manifest["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("relative"), str) or not isinstance(item.get("had_target"), bool) or item.get("state") not in states:
            raise RuntimeError("Invalid Docs sync transaction item")
        relative = Path(item["relative"])
        parts = relative.parts
        allowed = relative in {Path("openapi"), Path("docs.json")} or (len(parts) == 2 and parts[0] in LANGUAGE_SOURCE_DIRS and parts[1] in {"guides", "mcp"})
        if relative.is_absolute() or ".." in parts or not allowed or item["relative"] in seen:
            raise RuntimeError("Unsafe Docs sync transaction path")
        seen.add(item["relative"])


def restore_transaction(output_dir: Path) -> None:
    manifest_path, backup_root = transaction_paths(output_dir)
    if not manifest_path.exists():
        if backup_root.exists():
            if any(backup_root.iterdir()):
                raise RuntimeError("Docs sync recovery found backup without manifest")
            backup_root.rmdir()
        return
    manifest = load_json(manifest_path)
    validate_manifest(manifest)
    if manifest.get("phase") == "committed":
        shutil.rmtree(backup_root, ignore_errors=True)
        fsync_dir(backup_root.parent)
        manifest_path.unlink(missing_ok=True)
        fsync_dir(manifest_path.parent)
        return
    errors: list[str] = []
    for item in reversed(manifest.get("items", [])):
        target = output_dir / item["relative"]
        backup = backup_root / item["relative"]
        try:
            if item.get("had_target"):
                if backup.exists():
                    item["state"] = "restoring"
                    atomic_write_json(manifest_path, manifest)
                    if target.exists():
                        shutil.rmtree(target) if target.is_dir() else target.unlink()
                        fsync_dir(target.parent)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(backup, target)
                    fsync_dir(target.parent)
                elif item.get("state") == "restoring" and target.exists():
                    pass
                elif item.get("state") in {"backed_up", "publishing", "published", "restoring"}:
                    raise FileNotFoundError(str(backup))
                elif not target.exists():
                    raise FileNotFoundError(str(target))
            elif item.get("state") in {"publishing", "published", "restoring"} and target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
                fsync_dir(target.parent)
            item["state"] = "restored"
            atomic_write_json(manifest_path, manifest)
        except (OSError, ValueError) as exc:
            errors.append(type(exc).__name__)
    if errors:
        raise RuntimeError(f"Docs sync recovery incomplete for {len(errors)} item(s)")
    shutil.rmtree(backup_root, ignore_errors=True)
    fsync_dir(backup_root.parent)
    manifest_path.unlink(missing_ok=True)
    fsync_dir(manifest_path.parent)


def publish_generated_tree(staging_dir: Path, output_dir: Path, managed: list[Path]) -> None:
    restore_transaction(output_dir)
    manifest_path, backup_root = transaction_paths(output_dir)
    manifest = {
        "phase": "initializing",
        "items": [
            {"relative": str(path), "had_target": (output_dir / path).exists(), "state": "pending"}
            for path in managed
        ]
    }
    atomic_write_json(manifest_path, manifest)
    backup_root.mkdir(parents=True, exist_ok=False)
    fsync_dir(backup_root.parent)
    manifest["phase"] = "publishing"
    atomic_write_json(manifest_path, manifest)
    try:
        for item in manifest["items"]:
            relative = Path(item["relative"])
            target = output_dir / relative
            staged = staging_dir / relative
            backup = backup_root / relative
            if item["had_target"]:
                backup.parent.mkdir(parents=True, exist_ok=True)
                fsync_dir(backup.parent.parent if backup.parent != backup_root else backup_root)
                item["state"] = "backing_up"
                atomic_write_json(manifest_path, manifest)
                os.replace(target, backup)
                fsync_dir(target.parent)
                fsync_dir(backup.parent)
                item["state"] = "backed_up"
                atomic_write_json(manifest_path, manifest)
            if staged.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                item["state"] = "publishing"
                atomic_write_json(manifest_path, manifest)
                os.replace(staged, target)
                fsync_dir(staged.parent)
                fsync_dir(target.parent)
                item["state"] = "published"
                atomic_write_json(manifest_path, manifest)
        manifest["phase"] = "committed"
        atomic_write_json(manifest_path, manifest)
        shutil.rmtree(backup_root)
        fsync_dir(backup_root.parent)
        manifest_path.unlink()
        fsync_dir(manifest_path.parent)
    except BaseException:
        restore_transaction(output_dir)
        raise


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
        elif key in {"exclusiveMinimum", "exclusiveMaximum"} and isinstance(item, (int, float)) and not isinstance(item, bool):
            bound = "minimum" if key == "exclusiveMinimum" else "maximum"
            cleaned[bound] = item
            cleaned[key] = True
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


def clean_media_type(media_type: dict[str, Any], valid_keys: set[str]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    has_examples = isinstance(media_type.get("examples"), dict)
    for key, item in media_type.items():
        if key not in valid_keys or (key == "example" and has_examples):
            continue
        if key == "schema":
            cleaned[key] = clean_schema(item)
        elif key == "examples" and isinstance(item, dict):
            cleaned[key] = {
                name: example
                if isinstance(example, dict) and any(field in example for field in ("value", "$ref", "externalValue", "summary", "description"))
                else {"value": example}
                for name, example in item.items()
            }
        else:
            cleaned[key] = item
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
                        content_type: clean_media_type(media_type, media_type_keys)
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
                            content_type: clean_media_type(media_type, media_type_keys)
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
    components = cleaned.get("components")
    if isinstance(components, dict) and isinstance(components.get("schemas"), dict):
        cleaned["components"] = dict(components)
        cleaned["components"]["schemas"] = {
            name: clean_schema(schema) for name, schema in components["schemas"].items()
        }
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
        if api.get("private"):
            continue
        spec = load_openapi_spec(backend_dir, api["id"])
        if not spec:
            raise RuntimeError(f"Missing public OpenAPI spec for {api.get('id')} ({service.get('alias')})")
        if spec.get("x-private"):
            continue
        merged["paths"].update({path: operation for path, operation in spec.get("paths", {}).items()
                                if path not in PRIVATE_API_PATHS})
        for key in ("schemas", "requestBodies", "responses", "parameters"):
            values = spec.get("components", {}).get(key)
            if values:
                merged["components"].setdefault(key, {}).update(values)

    if not merged["paths"]:
        return None

    merged = resolve_t_keys(merged)
    clean_verbose_summaries(merged)
    return clean_openapi_spec(merged)


def load_exact_doc_records(
    backend_dir: Path,
    services: list[dict[str, Any]],
    path: Path = EXACT_MAP_PATH,
) -> dict[str, dict[str, str]]:
    bundle = load_json(path)
    records = bundle.get("records") if isinstance(bundle, dict) else None
    if bundle.get("schema_version") != 1 or not isinstance(records, list):
        raise RuntimeError("Invalid Coding document map")

    aliases = {service["alias"] for service in services} | DOC_ONLY_SERVICES
    result: dict[str, dict[str, str]] = {}
    output_paths: set[str] = set()
    for record in records:
        source_key = record.get("source_doc_key")
        service_alias = record.get("service_alias")
        output_path = record.get("output_path")
        if not all(isinstance(value, str) and value for value in (source_key, service_alias, output_path)):
            raise RuntimeError("Invalid Coding exact-map record")
        doc_key = source_key.removeprefix("development_")
        source = backend_dir / "docs" / f"{source_key}.md"
        relative = Path(output_path)
        expected_prefix = Path("guides") / service_alias
        if source_key in result or doc_key in result:
            raise RuntimeError(f"Duplicate Coding exact-map source {source_key}")
        if service_alias not in aliases:
            raise RuntimeError(f"Unknown Coding exact-map service {service_alias}")
        if not source.is_file():
            raise RuntimeError(f"Missing Coding exact-map source {source_key}")
        if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".mdx" or not relative.is_relative_to(expected_prefix):
            raise RuntimeError(f"Unsafe Coding exact-map output {output_path}")
        if output_path in output_paths:
            raise RuntimeError(f"Duplicate Coding exact-map output {output_path}")
        output_paths.add(output_path)
        result[doc_key] = {
            "source_doc_key": source_key,
            "service_alias": service_alias,
            "output_path": output_path,
            "canonical_alias": record["canonical_alias"],
        }
    return result


def build_doc_service_map(
    services: list[dict[str, Any]],
    backend_dir: Path,
    exact_records: dict[str, dict[str, str]] | None = None,
) -> dict[str, str | None]:
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
        exact = (exact_records or {}).get(doc_key)
        if exact:
            result[doc_key] = exact["service_alias"]
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

        result[doc_key] = None

    return result


def load_publication_catalog(language: str, catalog_dir: Path | None = None) -> dict[str, Any]:
    language = language.lower()
    if catalog_dir:
        payload = load_json(catalog_dir / f"{language}.json")
    else:
        request = Request(f"{PUBLICATION_URL}?lang={language}")
        for attempt in range(3):
            try:
                with urlopen(request, timeout=60) as response:
                    payload = json.load(response)
                break
            except (HTTPError, URLError, RemoteDisconnected, OSError, json.JSONDecodeError):
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
    if (not isinstance(payload, dict) or payload.get("schema_version") != 1
            or payload.get("language") != language or payload.get("source_language") != "zh-cn"
            or not isinstance(payload.get("items"), list) or not payload["items"]
            or not isinstance(payload.get("public_api_ids"), list)
            or not re.fullmatch(r"[0-9a-f]{64}", payload.get("catalog_hash", ""))):
        raise RuntimeError(f"Invalid publication catalog for {language}")
    records = {}
    for item in payload["items"]:
        key = item.get("source_key", "")
        if (not re.fullmatch(r"(?:development_|mcp_)[a-zA-Z0-9_-]+|x402_integration_guide", key)
                or key in records or item.get("status") not in {"ready", "missing", "stale", "missing_source"}):
            raise RuntimeError(f"Invalid or duplicate publication identity for {language}")
        if item.get("source_hash") is not None and not re.fullmatch(r"[0-9a-f]{64}", item["source_hash"]):
            raise RuntimeError(f"Invalid source hash for {language}/{key}")
        if item["status"] == "ready":
            body = item.get("content")
            if not isinstance(body, str) or not body or digest(body) != item.get("content_hash"):
                raise RuntimeError(f"Invalid publication content for {language}/{key}")
        records[key] = item
    return {**payload, "records": records}


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_publication_catalogs(languages: list[str], catalog_dir: Path | None = None) -> dict[str, Any]:
    catalogs = {}
    identity = None
    for language in languages:
        catalog = load_publication_catalog(LANGUAGE_SOURCE_DIRS[language], catalog_dir)
        current = (catalog["catalog_hash"], sorted(catalog["public_api_ids"]),
                   sorted((key, item["source_hash"]) for key, item in catalog["records"].items()))
        if identity is not None and current != identity:
            raise RuntimeError("Public source catalog changed between locale reads; retry with a consistent snapshot")
        identity = current
        catalogs[language] = catalog
    return catalogs


def guide_description(output_language: str, service_name: str) -> str:
    template = GUIDE_DESCRIPTIONS.get(output_language, "{service} API guide - Ace Data Cloud")
    return template.format(service=service_name)


def sanitize_html_for_mdx(content: str) -> str:
    parts = re.split(r"(^```.*?^```|^~~~.*?^~~~)", content, flags=re.MULTILINE | re.DOTALL)
    for index, part in enumerate(parts):
        if part.startswith(("```", "~~~")):
            continue
        part = re.sub(r"(<[a-zA-Z][^>]*)\bclass=", r"\1className=", part)
        for tag in ("img", "br", "hr", "input", "source", "meta", "link"):
            part = re.sub(rf"(<{tag}\b[^>]*?)(?<!/)>", r"\1 />", part)
        part = re.sub(r"<(https?://[^>]+)>", r"[\1](\1)", part)
        part = re.sub(r"<(?![a-zA-Z/!])", r"&lt;", part)
        # These sources are Markdown, not executable JSX. Literal braces in
        # prose (including malformed translated code fences) must stay text.
        # Keep inline code unchanged, just as fenced examples are unchanged.
        escaped = []
        cursor = 0
        for match in re.finditer(r"(?P<ticks>`+).*?(?P=ticks)", part, flags=re.DOTALL):
            escaped.append(part[cursor:match.start()].replace("{", "&#123;").replace("}", "&#125;"))
            escaped.append(match[0])
            cursor = match.end()
        escaped.append(part[cursor:].replace("{", "&#123;").replace("}", "&#125;"))
        part = "".join(escaped)
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


# overview is hand-authored; every other MCP page is generated in every locale.
MANUAL_MCP_PAGES = {"overview.mdx"}
MORE_GUIDES = {
    "zh-Hans": "更多指南", "zh-Hant": "更多指南", "en": "More guides", "ja": "その他のガイド",
    "ko": "추가 가이드", "es": "Más guías", "fr": "Autres guides", "de": "Weitere Anleitungen",
    "pt": "Mais guias", "ru": "Другие руководства", "ar": "المزيد من الأدلة", "it": "Altre guide",
    "sv": "Fler guider", "uk": "Інші посібники", "pl": "Więcej przewodników",
}


def publication_routes(backend_dir: Path, catalog: dict[str, Any], doc_service_map: dict[str, str | None],
                       exact_records: dict[str, Any]) -> tuple[dict[str, Path], dict[str, str]]:
    routes = {}
    excluded = {}
    for key in catalog["records"]:
        source = backend_dir / "docs" / f"{key}.md"
        doc_key = key.removeprefix("development_")
        if not source.is_file():
            excluded[key] = "no_repository_source"
            continue
        if doc_key in SKIP_DOC_KEYS or any(key.startswith(f"development_{alias}_") for alias in EXCLUDED_SERVICES):
            excluded[key] = "publication_hold"
            continue
        if key.startswith("mcp_"):
            relative = Path("mcp") / f"{key.removeprefix('mcp_')}.mdx"
        elif key == "x402_integration_guide":
            relative = Path("guides/x402.mdx")
        elif key == "development_oauth_apps":
            relative = Path("guides/oauth.mdx")
        elif doc_key in exact_records:
            relative = Path(exact_records[doc_key]["output_path"])
        else:
            # Preserve established URLs; public standalone guides have a stable
            # platform path rather than silently disappearing from the export.
            alias = doc_service_map.get(doc_key) or "platform"
            relative = Path("guides") / alias / f"{doc_key}.mdx"
        if relative in routes.values():
            raise RuntimeError(f"Conflicting publication output: {relative}")
        routes[key] = relative
    if not routes:
        raise RuntimeError("No public source documents to publish")
    return routes, excluded


def sync_document_pages(backend_dir: Path, output_dir: Path, previous: Path,
                        catalogs: dict[str, Any], routes: dict[str, Path],
                        services_by_alias: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    results = []
    for language, catalog in catalogs.items():
        for name in MANUAL_MCP_PAGES:
            source = previous / language / "mcp" / name
            if source.is_file():
                target = output_dir / language / "mcp" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        for key, relative in routes.items():
            record = catalog["records"][key]
            source = (backend_dir / "docs" / f"{key}.md").read_text(encoding="utf-8")
            status = record["status"]
            if record["source_hash"] != digest(source):
                status = "source_not_deployed"
            target = output_dir / language / relative
            old = previous / language / relative
            retained = False
            if status == "ready":
                description = None
                if relative.parts[0] == "mcp":
                    description = f"{relative.stem} MCP server integration"
                elif len(relative.parts) == 3:
                    alias = relative.parts[1]
                    service = (services_by_alias or {}).get(alias, {})
                    name = service.get("display_name") or alias.replace("-", " ").title()
                    description = guide_description(language, name)
                write_text(target, convert_markdown_to_mdx(record["content"], key.replace("_", " ").title(), description))
            elif old.is_file():
                # Availability and freshness are separate: retain the published
                # page, but report incomplete and make the workflow fail its gate.
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old, target)
                retained = True
            results.append({"language": language, "source_key": key, "path": str(Path(language) / relative),
                            "source_hash": digest(source), "status": status, "retained_previous": retained})
    return results


def refresh_generated_navigation(root: Path, languages: list[str], exact_records: dict[str, Any]) -> None:
    config = load_json(root / "docs.json")
    for language in config["navigation"]["languages"]:
        locale = language["language"]
        if locale not in languages:
            continue
        tabs = language.get("tabs", [])
        if not tabs:
            raise RuntimeError(f"Missing guide navigation for {locale}")
        api_tab = next((tab for tab in tabs if any("openapi" in group for group in tab.get("groups", []))), None)
        if api_tab:
            api_tab["groups"] = [group for group in api_tab["groups"]
                                 if "openapi" not in group or (root / group["openapi"]["source"].lstrip("/")).is_file()]
            known_specs = {group["openapi"]["source"] for group in api_tab["groups"] if "openapi" in group}
            for spec in sorted((root / "openapi").glob("*.json")):
                source = f"/openapi/{spec.name}"
                if source not in known_specs:
                    directory = f"api-reference/{spec.stem}" if locale == "zh-Hans" else f"{locale}/api-reference/{spec.stem}"
                    api_tab["groups"].append({"group": load_json(spec)["info"]["title"],
                                               "openapi": {"source": source, "directory": directory}})
        prefixes = (f"{locale}/guides/", f"{locale}/mcp/")

        def prune(value: Any) -> None:
            if isinstance(value, dict):
                if isinstance(value.get("pages"), list):
                    value["pages"] = [p for p in value["pages"] if not isinstance(p, str)
                                      or not p.startswith(prefixes) or (root / f"{p}.mdx").is_file()]
                for child in value.values():
                    prune(child)
            elif isinstance(value, list):
                for child in value:
                    prune(child)

        prune(tabs)
        groups = tabs[0].setdefault("groups", [])
        groups[:] = [g for g in groups if g.get("group") != MORE_GUIDES[locale]]
        for group in groups:
            if group.get("group") == "Coding":
                group["pages"] = [f"{locale}/{r['output_path'].removesuffix('.mdx')}" for r in exact_records.values()
                                  if (root / locale / r["output_path"]).is_file()]
        known: list[str] = []
        collect_page_paths(tabs, known)
        additional = sorted(str(p.relative_to(root).with_suffix("")) for p in (root / locale / "guides").rglob("*.mdx")
                            if str(p.relative_to(root).with_suffix("")) not in known)
        if additional:
            groups.append({"group": MORE_GUIDES[locale], "icon": "book-open", "pages": additional})
        mcp_tab = next((t for t in tabs if "MCP" in t.get("tab", "")), None)
        if mcp_tab:
            group = mcp_tab["groups"][0]
            group["pages"] = sorted({p for p in group.get("pages", []) if isinstance(p, str)}
                                    | {str(p.relative_to(root).with_suffix("")) for p in (root / locale / "mcp").glob("*.mdx")})
    write_json(root / "docs.json", config)


def get_docs_languages(output_dir: Path) -> list[str]:
    docs_json = load_json(output_dir / "docs.json")
    languages = [entry["language"] for entry in docs_json.get("navigation", {}).get("languages", [])]
    result = [language for language in languages if language in LANGUAGE_SOURCE_DIRS]
    # Unlisted legacy locale URLs are still served by Mintlify. Existing
    # generated directories must not remain permanently stale or unparseable.
    result.extend(language for language in LANGUAGE_SOURCE_DIRS if language not in result
                  and any((output_dir / language / folder).is_dir() for folder in ("guides", "mcp")))
    return result


def managed_paths(languages: list[str]) -> list[Path]:
    paths = [Path("openapi"), Path("docs.json")]
    paths.extend(Path(language) / folder for language in languages for folder in ("guides", "mcp"))
    return paths


def clear_managed_paths(root: Path, managed: list[Path]) -> None:
    for relative in managed:
        path = root / relative
        if path.exists():
            shutil.rmtree(path) if path.is_dir() else path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Docs generated content from PlatformBackend")
    parser.add_argument("--backend-dir", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--require-denylist", action="store_true")
    parser.add_argument("--catalog-dir", type=Path, help="Read exported publication snapshots for offline verification")
    parser.add_argument("--report", type=Path, help="Write publication completeness report outside the output tree")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without publishing generated files")
    parser.add_argument("--preview-dir", type=Path, help="Save dry-run output to a new directory for review")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    if args.preview_dir and (not args.dry_run or args.preview_dir.resolve().is_relative_to(output_dir)):
        raise SystemExit("--preview-dir requires --dry-run and a directory outside the output tree")
    restore_transaction(output_dir)
    denylist = load_denylist(required=args.require_denylist or not (args.validate_only or args.dry_run))
    if args.dry_run and not all(denylist):
        log("Dry run: private-value denylist is unavailable; publication still requires it")
    if args.validate_only:
        validate_generated_tree(output_dir, denylist)
        log("Generated tree validation passed")
        return 0
    if args.backend_dir is None:
        raise SystemExit("--backend-dir is required unless --validate-only is used")
    backend_dir = args.backend_dir.resolve()
    if not (backend_dir / "cost" / "service_api_mapping.json").exists():
        raise SystemExit(f"Invalid PlatformBackend directory: {backend_dir}")
    if not (output_dir / "docs.json").exists():
        raise SystemExit(f"Invalid Docs output directory: {output_dir}")

    documented_aliases = get_documented_service_aliases(output_dir)
    services = load_services(backend_dir, documented_aliases)
    exact_records = load_exact_doc_records(backend_dir, services)
    doc_service_map = build_doc_service_map(services, backend_dir, exact_records)
    languages = get_docs_languages(output_dir)
    if not languages:
        raise RuntimeError("No supported publication languages configured")
    log(f"Languages: {', '.join(languages)}")

    catalogs = load_publication_catalogs(languages, args.catalog_dir)
    source_catalog = catalogs[languages[0]]
    routes, excluded = publication_routes(backend_dir, source_catalog, doc_service_map, exact_records)
    public_api_ids = set(source_catalog["public_api_ids"])
    public_services = [{**service, "apis": [api for api in service.get("apis", []) if api["id"] in public_api_ids]}
                       for service in services]
    managed = managed_paths(languages)
    with tempfile.TemporaryDirectory(prefix="docs-sync-", dir=output_dir.parent) as temporary_directory:
        staging_dir = Path(temporary_directory) / "output"
        shutil.copytree(output_dir, staging_dir, ignore=shutil.ignore_patterns(".git"))
        clear_managed_paths(staging_dir, managed)
        # docs.json is committed atomically with generated pages, not cleared.
        shutil.copy2(output_dir / "docs.json", staging_dir / "docs.json")
        sync_openapi(backend_dir, staging_dir, public_services)
        results = sync_document_pages(backend_dir, staging_dir, output_dir, catalogs, routes,
                                      {service["alias"]: service for service in services})
        refresh_generated_navigation(staging_dir, languages, exact_records)
        neutralize_generated_tree(staging_dir, denylist)
        validate_generated_tree(staging_dir, denylist)
        pending = [item for item in results if item["status"] != "ready"]
        report = {"schema_version": 1, "complete": not pending, "catalog_hash": source_catalog["catalog_hash"],
                  "private_value_validation": all(denylist),
                  "total": len(results), "ready": len(results) - len(pending), "pending": pending, "excluded": excluded}
        if args.report:
            write_json(args.report, report)
        if args.preview_dir:
            shutil.copytree(staging_dir, args.preview_dir)
        if not args.dry_run:
            publish_generated_tree(staging_dir, output_dir, managed)
    log(f"Publication: {report['ready']}/{report['total']} current; {len(pending)} pending")
    for item in pending[:20]:
        log(f"  PENDING {item['language']}/{item['source_key']}: {item['status']}")
    return 2 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
