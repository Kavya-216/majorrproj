from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CanonicalConfig:
    data: dict[str, Any]

    @property
    def encryption_mode(self) -> str:
        return str(self.data["encryption"]["mode"])

    @property
    def payload_max_bytes(self) -> int:
        return int(self.data["encryption"]["max_payload_bytes_hard"])

    @property
    def payload_target_bytes(self) -> int:
        return int(self.data["encryption"]["payload_bytes_engineering_target"])


def load_canonical_config(config_path: str | Path = "config/canonical_config.json") -> CanonicalConfig:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Canonical config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return CanonicalConfig(data=data)
