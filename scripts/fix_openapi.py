#!/usr/bin/env python3
"""Clean OpenAPI specs to pass strict validation (Mintlify, openapi-spec-validator)."""

import json
import os

# Valid keywords for OpenAPI 3.0 Schema Objects (JSON Schema subset)
VALID_SCHEMA_KEYS = {
    'type', 'format', 'description', 'default', 'example', 'examples',
    'enum', 'const',
    'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf',
    'minLength', 'maxLength', 'pattern',
    'minItems', 'maxItems', 'uniqueItems',
    'minProperties', 'maxProperties',
    'items', 'properties', 'required', 'additionalProperties',
    'oneOf', 'allOf', 'anyOf', 'not', 'discriminator',
    'nullable', 'readOnly', 'writeOnly', 'deprecated',
    'title', '$ref',
}

# Valid non-schema keys at various OpenAPI levels
VALID_OPERATION_KEYS = {
    'summary', 'description', 'operationId', 'tags', 'parameters',
    'requestBody', 'responses', 'callbacks', 'deprecated', 'security',
    'servers', 'externalDocs',
}
VALID_RESPONSE_KEYS = {'description', 'headers', 'content', 'links'}
VALID_REQUESTBODY_KEYS = {'description', 'content', 'required'}
VALID_MEDIA_TYPE_KEYS = {'schema', 'example', 'examples', 'encoding'}
VALID_PARAMETER_KEYS = {
    'name', 'in', 'description', 'required', 'deprecated', 'allowEmptyValue',
    'style', 'explode', 'allowReserved', 'schema', 'example', 'examples',
    'content',
}


def clean_schema(obj):
    """Recursively clean a JSON Schema object for OpenAPI 3.0 compliance."""
    if not isinstance(obj, dict):
        return obj

    cleaned = {}
    for k, v in obj.items():
        # Skip non-standard keys
        if k not in VALID_SCHEMA_KEYS and not k.startswith('x-'):
            continue

        # Fix 'type': 'float' -> 'type': 'number'
        if k == 'type' and v == 'float':
            cleaned['type'] = 'number'
            cleaned.setdefault('format', 'float')
            continue

        # Replace 'const' with 'enum' (const not in OpenAPI 3.0)
        if k == 'const':
            cleaned['enum'] = [v]
            continue

        # Recurse into nested schemas
        if k in ('items', 'additionalProperties', 'not') and isinstance(v, dict):
            cleaned[k] = clean_schema(v)
        elif k == 'properties' and isinstance(v, dict):
            cleaned[k] = {pk: clean_schema(pv) for pk, pv in v.items()}
        elif k in ('oneOf', 'allOf', 'anyOf') and isinstance(v, list):
            cleaned[k] = [clean_schema(item) for item in v]
        else:
            cleaned[k] = v

    # Fix type-example mismatches
    if 'type' in cleaned and 'example' in cleaned:
        t = cleaned['type']
        ex = cleaned['example']
        if t == 'object' and isinstance(ex, str):
            cleaned['type'] = 'string'
        elif t == 'object' and isinstance(ex, (int, float)):
            cleaned['type'] = 'number'

    # Remove empty required arrays (invalid in OpenAPI 3.0 JSON Schema)
    if 'required' in cleaned and isinstance(cleaned['required'], list) and len(cleaned['required']) == 0:
        del cleaned['required']

    return cleaned


def clean_media_type(obj):
    """Clean a Media Type Object."""
    if not isinstance(obj, dict):
        return obj
    cleaned = {}
    for k, v in obj.items():
        if k == 'schema':
            cleaned[k] = clean_schema(v)
        elif k in VALID_MEDIA_TYPE_KEYS or k.startswith('x-'):
            cleaned[k] = v
    return cleaned


def clean_response(obj):
    """Clean a Response Object."""
    if not isinstance(obj, dict):
        return obj
    cleaned = {}
    # Ensure description exists
    if 'description' not in obj:
        cleaned['description'] = 'Response'
    for k, v in obj.items():
        if k == 'content' and isinstance(v, dict):
            cleaned[k] = {ct: clean_media_type(mv) for ct, mv in v.items()}
        elif k in VALID_RESPONSE_KEYS or k.startswith('x-'):
            cleaned[k] = v
    return cleaned


def clean_request_body(obj):
    """Clean a Request Body Object."""
    if not isinstance(obj, dict):
        return obj
    cleaned = {}
    for k, v in obj.items():
        if k == 'content' and isinstance(v, dict):
            cleaned[k] = {ct: clean_media_type(mv) for ct, mv in v.items()}
        elif k in VALID_REQUESTBODY_KEYS or k.startswith('x-'):
            cleaned[k] = v
    return cleaned


def clean_parameter(obj):
    """Clean a Parameter Object."""
    if not isinstance(obj, dict):
        return obj
    cleaned = {}
    for k, v in obj.items():
        if k == 'schema':
            cleaned[k] = clean_schema(v)
        elif k in VALID_PARAMETER_KEYS or k.startswith('x-'):
            cleaned[k] = v
    return cleaned


def clean_operation(obj):
    """Clean an Operation Object."""
    if not isinstance(obj, dict):
        return obj
    cleaned = {}
    for k, v in obj.items():
        if k == 'parameters' and isinstance(v, list):
            cleaned[k] = [clean_parameter(p) for p in v]
        elif k == 'requestBody':
            cleaned[k] = clean_request_body(v)
        elif k == 'responses' and isinstance(v, dict):
            cleaned[k] = {code: clean_response(resp) for code, resp in v.items()}
        elif k in VALID_OPERATION_KEYS or k.startswith('x-'):
            cleaned[k] = v
    return cleaned


def clean_spec(spec):
    """Clean an entire OpenAPI 3.0 spec."""
    cleaned = {}
    for k, v in spec.items():
        if k == 'paths' and isinstance(v, dict):
            cleaned_paths = {}
            for path, path_item in v.items():
                if not isinstance(path_item, dict):
                    cleaned_paths[path] = path_item
                    continue
                cleaned_item = {}
                for method, op in path_item.items():
                    if method in ('get', 'post', 'put', 'delete', 'patch', 'options', 'head', 'trace'):
                        cleaned_item[method] = clean_operation(op)
                    elif method == 'parameters':
                        cleaned_item[method] = [clean_parameter(p) for p in op] if isinstance(op, list) else op
                    else:
                        cleaned_item[method] = op
                cleaned_paths[path] = cleaned_item
            cleaned[k] = cleaned_paths
        else:
            cleaned[k] = v
    return cleaned


def main():
    openapi_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'openapi')

    count = 0
    for fname in sorted(os.listdir(openapi_dir)):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(openapi_dir, fname)
        with open(fpath) as f:
            spec = json.load(f)
        cleaned = clean_spec(spec)
        with open(fpath, 'w') as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)
            f.write('\n')
        count += 1
        print(f"Fixed: {fname}")

    print(f"\nCleaned {count} files")

    try:
        from openapi_spec_validator import validate
        errors = 0
        for fname in sorted(os.listdir(openapi_dir)):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(openapi_dir, fname)
            with open(fpath) as f:
                spec = json.load(f)
            try:
                validate(spec)
                print(f"  VALID: {fname}")
            except Exception as e:
                errors += 1
                msg = e.message if hasattr(e, 'message') else str(e)
                path = ' -> '.join(str(p) for p in e.absolute_path) if hasattr(e, 'absolute_path') else ''
                print(f"  INVALID: {fname}")
                print(f"    Path: {path}")
                print(f"    Error: {msg[:300]}")
        print(f"\n{errors} validation errors remaining")
    except ImportError:
        print("openapi-spec-validator not installed, skipping validation")


if __name__ == '__main__':
    main()
