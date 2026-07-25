"""Deterministic hashing of calculation inputs + model versions.

A ResultRecord is immutable and identified by a SHA-256 over the canonical JSON of
(inputs, model versions). This underpins reproducibility (ADR 0001) and the regression
requirement (OPZ §9.1 Poziom B).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Stable JSON: sorted keys, no insignificant whitespace, fixed separators."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def result_hash(inputs: dict[str, Any], model_versions: dict[str, str]) -> str:
    """SHA-256 fingerprint of a calculation (inputs + engine/model versions)."""
    envelope = {"inputs": inputs, "model_versions": dict(sorted(model_versions.items()))}
    digest = hashlib.sha256(canonical_json(envelope).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
