from __future__ import annotations

import hashlib
import json
from typing import Dict


def compute_policy_hash(policy: Dict[str, object]) -> str:
    payload = {key: value for key, value in policy.items() if key != "policy_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ensure_policy_metadata(
    policy: Dict[str, object],
    default_version: str = "v1",
) -> Dict[str, object]:
    normalized = dict(policy)
    normalized.setdefault("policy_version", default_version)
    if "policy_hash" not in normalized:
        normalized["policy_hash"] = compute_policy_hash(normalized)
    return normalized
