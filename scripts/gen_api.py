"""
scripts/gen_api.py — One-Command OpenAPI 3.1 to TypeScript Client & Schema Generator.

Reads docs/openapi.json, generates strongly-typed TypeScript interfaces, DTOs,
and endpoint maps, and synchronizes to:
  - packages/shared/src/generated-api.ts
  - mobile/src/api/generated.ts
  - frontend/src/types/generated-api.ts
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
OPENAPI_JSON = ROOT_DIR / "docs" / "openapi.json"
SHARED_OUTPUT = ROOT_DIR / "packages" / "shared" / "src" / "generated-api.ts"
MOBILE_OUTPUT = ROOT_DIR / "mobile" / "src" / "api" / "generated.ts"
FRONTEND_OUTPUT = ROOT_DIR / "frontend" / "src" / "types" / "generated-api.ts"


def ensure_openapi_json() -> dict[str, Any]:
    """Ensure docs/openapi.json exists, exporting if missing."""
    if not OPENAPI_JSON.exists():
        print(f"[gen_api] {OPENAPI_JSON} missing. Exporting from backend...")
        try:
            from backend.app.main import app  # type: ignore

            spec = app.openapi()
            OPENAPI_JSON.parent.mkdir(parents=True, exist_ok=True)
            OPENAPI_JSON.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"[gen_api] Failed to export openapi directly: {exc}")
            sys.exit(1)

    with open(OPENAPI_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_ident(name: str) -> str:
    """Sanitize identifier for TypeScript."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def sanitize_prop_name(name: str) -> str:
    """Quote property name if it contains hyphens, spaces, or non-identifier chars."""
    if re.match(r"^[a-zA-Z_$][a-zA-Z0-9_$]*$", name):
        return name
    return json.dumps(name)


def resolve_type(schema: dict[str, Any] | None, schemas: dict[str, Any]) -> str:
    """Resolve JSON Schema to TypeScript type."""
    if not schema or not isinstance(schema, dict):
        return "unknown"

    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        return sanitize_ident(ref_name)

    if "anyOf" in schema:
        sub_types = [resolve_type(sub, schemas) for sub in schema["anyOf"]]
        concrete = [t for t in sub_types if t != "unknown"]
        if concrete:
            sub_types = concrete
        return " | ".join(list(dict.fromkeys(sub_types))) if sub_types else "unknown"

    if "oneOf" in schema:
        sub_types = [resolve_type(sub, schemas) for sub in schema["oneOf"]]
        concrete = [t for t in sub_types if t != "unknown"]
        if concrete:
            sub_types = concrete
        return " | ".join(list(dict.fromkeys(sub_types))) if sub_types else "unknown"

    if "allOf" in schema:
        sub_types = [resolve_type(sub, schemas) for sub in schema["allOf"]]
        return " & ".join(list(dict.fromkeys(sub_types))) if sub_types else "unknown"

    if "enum" in schema:
        enum_vals = schema["enum"]
        return " | ".join(json.dumps(val) for val in enum_vals)

    stype = schema.get("type")
    if stype == "null":
        return "null"

    if isinstance(stype, list):
        types_resolved = []
        for t in stype:
            if t == "null":
                types_resolved.append("null")
            elif t in ("integer", "number"):
                types_resolved.append("number")
            elif t == "string":
                types_resolved.append("string")
            elif t == "boolean":
                types_resolved.append("boolean")
            elif t == "array":
                item_type = resolve_type(schema.get("items"), schemas)
                types_resolved.append(f"{item_type}[]")
            elif t == "object":
                types_resolved.append("Record<string, unknown>")
            else:
                types_resolved.append("unknown")
        return " | ".join(list(dict.fromkeys(types_resolved)))

    if stype == "string":
        fmt = schema.get("format")
        if fmt in ("date", "date-time"):
            return "string"
        return "string"

    if stype in ("integer", "number"):
        return "number"

    if stype == "boolean":
        return "boolean"

    if stype == "array":
        item_schema = schema.get("items")
        item_t = resolve_type(item_schema, schemas)
        if " | " in item_t or " & " in item_t:
            return f"({item_t})[]"
        return f"{item_t}[]"

    if stype == "object" or "properties" in schema:
        props = schema.get("properties", {})
        if not props:
            return "Record<string, unknown>"
        required = set(schema.get("required", []))
        fields = []
        for prop_name, prop_schema in props.items():
            prop_ident = sanitize_prop_name(prop_name)
            opt = "" if prop_name in required else "?"
            prop_t = resolve_type(prop_schema, schemas)
            desc = prop_schema.get("description")
            doc = f"  /** {desc} */\n" if desc else ""
            fields.append(f"{doc}  {prop_ident}{opt}: {prop_t};")
        return "{\n" + "\n".join(fields) + "\n}"

    return "unknown"


def generate_typescript_code(spec: dict[str, Any]) -> str:
    """Generate complete TypeScript file contents."""
    lines: list[str] = [
        "/**",
        " * AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.",
        " * Generated from docs/openapi.json via scripts/gen_api.py.",
        " * Run 'npm run gen:api' in mobile/ or 'python scripts/gen_api.py' to regenerate.",
        " */",
        "",
        "/* eslint-disable @typescript-eslint/no-explicit-any */",
        "",
    ]

    schemas = spec.get("components", {}).get("schemas", {})
    paths = spec.get("paths", {})

    # 1. Generate Schema Interfaces
    lines.append("// ============================================================================")
    lines.append("// 1. OpenAPI Components & DTOs")
    lines.append("// ============================================================================")
    lines.append("")

    for schema_name, schema_body in sorted(schemas.items()):
        ident = sanitize_ident(schema_name)
        desc = schema_body.get("description", "")
        if desc:
            lines.append(f"/** {desc} */")

        if schema_body.get("type") == "object" or "properties" in schema_body:
            required = set(schema_body.get("required", []))
            lines.append(f"export interface {ident} {{")
            for prop_name, prop_schema in schema_body.get("properties", {}).items():
                opt = "" if prop_name in required else "?"
                prop_t = resolve_type(prop_schema, schemas)
                prop_desc = prop_schema.get("description")
                if prop_desc:
                    lines.append(f"  /** {prop_desc} */")
                lines.append(f"  {prop_name}{opt}: {prop_t};")
            lines.append("}")
            lines.append("")
        elif "enum" in schema_body:
            enum_vals = schema_body["enum"]
            union_t = " | ".join(json.dumps(val) for val in enum_vals)
            lines.append(f"export type {ident} = {union_t};")
            lines.append("")
        else:
            resolved_t = resolve_type(schema_body, schemas)
            lines.append(f"export type {ident} = {resolved_t};")
            lines.append("")

    # 2. Generate Typed Path Operations Map
    lines.append("// ============================================================================")
    lines.append("// 2. Typed API Endpoint Registry & Operation Definitions")
    lines.append("// ============================================================================")
    lines.append("")

    endpoint_entries: list[str] = []

    for path, methods in sorted(paths.items()):
        for method, op in sorted(methods.items()):
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue
            method_upper = method.upper()
            op_id = op.get("operation_id", f"{method.lower()}_{sanitize_ident(path)}")
            summary = op.get("summary") or op.get("description") or f"{method_upper} {path}"

            # Request Body type
            req_body_t = "undefined"
            req_body = op.get("requestBody")
            if req_body and "content" in req_body:
                json_content = req_body["content"].get("application/json")
                if json_content and "schema" in json_content:
                    req_body_t = resolve_type(json_content["schema"], schemas)

            # Response type
            resp_t = "unknown"
            responses = op.get("responses", {})
            for code in ("200", "201", "202", "204", "default"):
                if code in responses:
                    resp_obj = responses[code]
                    if "content" in resp_obj:
                        json_resp = resp_obj["content"].get("application/json")
                        if json_resp and "schema" in json_resp:
                            resp_t = resolve_type(json_resp["schema"], schemas)
                    elif code == "204":
                        resp_t = "void";
                    break

            # Query/Path parameters
            params = op.get("parameters", [])
            query_params: list[str] = []
            for p in params:
                p_name = p.get("name")
                if not p_name:
                    continue
                p_ident = sanitize_prop_name(p_name)
                p_req = p.get("required", False)
                p_schema = p.get("schema")
                p_type = resolve_type(p_schema, schemas) if p_schema else "string"
                opt = "" if p_req else "?"
                query_params.append(f"{p_ident}{opt}: {p_type}")

            params_t = f"{{ {'; '.join(query_params)} }}" if query_params else "undefined"

            endpoint_entries.append(
                f"  /** {summary} */\n"
                f"  '{method_upper} {path}': {{\n"
                f"    operationId: '{op_id}';\n"
                f"    parameters: {params_t};\n"
                f"    requestBody: {req_body_t};\n"
                f"    response: {resp_t};\n"
                f"  }};"
            )

    lines.append("export interface ApiOperations {")
    lines.extend(endpoint_entries)
    lines.append("}")
    lines.append("")

    # 3. Export typed helper signatures
    lines.append("// ============================================================================")
    lines.append("// 3. Typed API Client Contract")
    lines.append("// ============================================================================")
    lines.append("""
export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

export interface ApiClientContract {
  get<T = unknown>(path: string, params?: Record<string, unknown>): Promise<T>;
  post<T = unknown>(path: string, body?: unknown, params?: Record<string, unknown>): Promise<T>;
  put<T = unknown>(path: string, body?: unknown): Promise<T>;
  delete<T = unknown>(path: string, params?: Record<string, unknown>): Promise<T>;
  uploadMultipart<T = unknown>(path: string, formData: any, onProgress?: (pct: number) => void): Promise<T>;
}
""")

    return "\n".join(lines)


def get_shared_code() -> str:
    """Read and concatenate packages/shared enums, errors, events, and types for standalone mobile bundling."""
    shared_files = ["enums.ts", "errors.ts", "events.ts", "types.ts"]
    blocks: list[str] = []
    for sf in shared_files:
        p = ROOT_DIR / "packages" / "shared" / "src" / sf
        if p.exists():
            content = p.read_text(encoding="utf-8")
            # Strip relative imports like `from './enums'`
            cleaned = re.sub(r"^import\s+.*?from\s+['\"].*?['\"];?\r?\n", "", content, flags=re.MULTILINE)
            blocks.append(
                f"// ============================================================================\n"
                f"// Shared Domain Module: {sf}\n"
                f"// ============================================================================\n"
                + cleaned.strip()
            )
    return "\n\n".join(blocks)


def main() -> None:
    print("[gen_api] Starting OpenAPI 3.1 TypeScript code generation...")
    spec = ensure_openapi_json()
    ts_code = generate_typescript_code(spec)
    shared_code = get_shared_code()

    # 1. Output to packages/shared
    SHARED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SHARED_OUTPUT.write_text(ts_code, encoding="utf-8")
    print(f"  ✓ Synchronized: {SHARED_OUTPUT} ({len(ts_code)} bytes)")

    # 2. Output to mobile/src/api with all shared types and enums embedded for zero-symlink Metro compatibility
    MOBILE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    mobile_bundle = (
        "/**\n"
        " * AUTO-GENERATED MOBILE API & DOMAIN DEFINITIONS\n"
        " * Generated from docs/openapi.json and packages/shared/src/ via scripts/gen_api.py.\n"
        " * Contains all API operations and shared domain enums/types.\n"
        " */\n\n"
        f"{shared_code}\n\n"
        f"{ts_code}\n"
    )
    MOBILE_OUTPUT.write_text(mobile_bundle, encoding="utf-8")
    print(f"  ✓ Synchronized: {MOBILE_OUTPUT} ({len(mobile_bundle)} bytes with embedded domain schemas)")

    # 3. Output to frontend/src/types
    FRONTEND_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_OUTPUT.write_text(ts_code, encoding="utf-8")
    print(f"  ✓ Synchronized: {FRONTEND_OUTPUT} ({len(ts_code)} bytes)")

    print("[gen_api] Schema & typed client generation complete!")


if __name__ == "__main__":
    main()
