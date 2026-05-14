"""人才库 bundle 同步模型和哈希工具。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

BUNDLE_SCHEMA_VERSION = 1
CONFIRM_SYNC_TEXT = "确认同步人才库"


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def record_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BundleManifest:
    bundle_schema_version: int
    export_mode: str
    source_node_id: str
    export_id: str
    created_at: str
    db_schema: str = "talent-agent-sqlite"
    tables: dict[str, int] = field(default_factory=dict)
    attachments: dict[str, bool] = field(default_factory=dict)
