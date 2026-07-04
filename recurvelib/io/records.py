"""Run records and evidence receipts — the loop's dataset.

A run record is one cycle's structured result; a receipt is one verdict,
pinned (probe hash, tree identity, oracle versions, timestamp) and
hash-chained so the evidence trail is tamper-evident. Both schemas are
versioned and shipped with the engine; they are the stable table every later
ambition (triage priors, cost prediction, dashboards, signing) consumes.

Validation here is a deliberate structural subset of JSON Schema (types,
required, enum, additionalProperties, numeric minimum, $defs/$ref within the
shipped schemas) — enough to make a malformed record a loud error with no
third-party dependency.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from recurvelib import resource_dir

RECORD_SCHEMA_VERSION = "1.0.0"
RECEIPT_SCHEMA_VERSION = "1.0.0"

_SCHEMA_DIR = resource_dir("schema")


class RecordError(ValueError):
    """A run record or receipt failed structural validation."""


def _schema(name: str) -> dict:
    return json.loads((_SCHEMA_DIR / name).read_text())


_TYPES = {
    "object": dict, "array": list, "string": str,
    "integer": int, "number": (int, float), "boolean": bool, "null": type(None),
}


def _check(obj: Any, schema: dict, root: dict, where: str) -> None:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            raise RecordError(f"{where}: unsupported $ref {ref!r}")
        _check(obj, root["$defs"][ref.split("/")[-1]], root, where)
        return

    typ = schema.get("type")
    if typ is not None:
        types = typ if isinstance(typ, list) else [typ]
        py = tuple(_TYPES[t] for t in types)
        if not isinstance(obj, py) or (isinstance(obj, bool) and "boolean" not in types):
            raise RecordError(f"{where}: expected {'|'.join(types)}, got {type(obj).__name__}")

    if "enum" in schema and obj not in schema["enum"]:
        raise RecordError(f"{where}: {obj!r} not in {schema['enum']}")
    if "minimum" in schema and isinstance(obj, (int, float)) and obj < schema["minimum"]:
        raise RecordError(f"{where}: {obj} below minimum {schema['minimum']}")

    if isinstance(obj, dict):
        props = schema.get("properties", {})
        for req in schema.get("required", []):
            if req not in obj:
                raise RecordError(f"{where}: missing required '{req}'")
        addl = schema.get("additionalProperties", True)
        for k, v in obj.items():
            if k in props:
                _check(v, props[k], root, f"{where}.{k}")
            elif addl is False:
                raise RecordError(f"{where}: unknown field '{k}'")
            elif isinstance(addl, dict):
                _check(v, addl, root, f"{where}.{k}")
    elif isinstance(obj, list) and "items" in schema:
        for i, v in enumerate(obj):
            _check(v, schema["items"], root, f"{where}[{i}]")


def validate_run_record(record: dict) -> None:
    schema = _schema("run-record.schema.json")
    _check(record, schema, schema, "run-record")


def validate_receipt(receipt: dict) -> None:
    schema = _schema("receipt.schema.json")
    _check(receipt, schema, schema, "receipt")
    if receipt_hash(receipt) != receipt["self_sha256"]:
        raise RecordError("receipt: self_sha256 does not match canonical content — chain broken")


def receipt_hash(receipt: dict) -> str:
    """SHA-256 over canonical JSON with self_sha256, the countersignature over it,
    and any signer-added fields absent — the signer runs after the hash is fixed,
    so nothing it produces can be inside the hash it signs."""
    body = {k: v for k, v in receipt.items()
            if k not in ("self_sha256", "signature", "signer", "signer_fields")}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode()).hexdigest()


def make_receipt(
    *,
    gap: str,
    suite: str,
    verdict: str,
    exit_code: int | None,
    detail: str,
    probe_path: Path | None,
    tree_kind: str,
    tree_value: str,
    oracle_versions: dict[str, str],
    observed_at: str,
    prev: str | None,
) -> dict:
    probe_sha = ""
    if probe_path is not None and probe_path.exists():
        probe_sha = hashlib.sha256(probe_path.read_bytes()).hexdigest()
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "gap": gap,
        "suite": suite,
        "verdict": verdict,
        "exit_code": exit_code,
        "detail": detail,
        "probe_sha256": probe_sha,
        "tree": {"kind": tree_kind, "value": tree_value},
        "oracle_versions": oracle_versions,
        "observed_at": observed_at,
        "prev": prev,
    }
    receipt["self_sha256"] = receipt_hash(receipt)
    return receipt
