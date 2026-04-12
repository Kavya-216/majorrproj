from __future__ import annotations

from dataclasses import dataclass


CLASS_MAP = {
    0: "gunshot",
    1: "chainsaw",
    2: "vehicle",
}


@dataclass(frozen=True)
class Arch5Result:
    class_id: int
    confidence: float
    timestamp_ms: int

    def validate(self) -> None:
        if self.class_id not in CLASS_MAP:
            raise ValueError(f"Invalid class_id {self.class_id}; expected one of {list(CLASS_MAP)}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")
        if self.timestamp_ms <= 0:
            raise ValueError("timestamp_ms must be positive unix epoch milliseconds")


@dataclass(frozen=True)
class StrictThresholds:
    default_threshold: float
    per_class: dict[str, float]

    def threshold_for_class_id(self, class_id: int) -> float:
        class_name = CLASS_MAP[class_id]
        return float(self.per_class.get(class_name, self.default_threshold))


def should_emit_alert(result: Arch5Result, thresholds: StrictThresholds) -> bool:
    result.validate()
    return result.confidence >= thresholds.threshold_for_class_id(result.class_id)
