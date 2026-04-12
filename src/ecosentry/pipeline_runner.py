from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .arch6_payload import AlertPayloadCodec, DeviceMetadata
from .arch7_energy import default_energy_model, run_sensitivity, scenario_definitions, simulate_24h, simulate_30d
from .arch8_network import (
    build_topology_corbett,
    build_topology_seshachalam,
    build_topology_sundarbans,
    campaign_to_dict,
    run_campaign,
)
from .config import load_canonical_config
from .contracts import Arch5Result, StrictThresholds, should_emit_alert


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def run_arch6(config_path: str = "config/canonical_config.json", out_dir: str = "artifacts") -> dict[str, Any]:
    cfg = load_canonical_config(config_path)
    thresholds = StrictThresholds(
        default_threshold=float(cfg.data["detection"]["default_threshold"]),
        per_class={k: float(v) for k, v in cfg.data["detection"]["thresholds"].items()},
    )

    arch5 = Arch5Result(class_id=0, confidence=0.91, timestamp_ms=1_765_000_000_000)
    eligible = should_emit_alert(arch5, thresholds)
    if not eligible:
        raise RuntimeError("ARCH_6 run aborted: ARCH_5 output did not pass threshold gate")

    enc_key = os.urandom(32)
    mac_key = os.urandom(32)
    codec = AlertPayloadCodec(cfg, enc_key, mac_key)
    meta = DeviceMetadata(device_id="SENTRY_01", location_hash="19.8N_74.5E_625m", firmware_version="1.0.0")

    encoded = codec.encode(arch5, meta)
    decoded = codec.decode(encoded.encrypted_payload_bytes)

    result = {
        "field_dictionary": [asdict(x) for x in codec.compact_field_dictionary()],
        "input_arch5": asdict(arch5),
        "size_report": asdict(encoded.size_report),
        "envelope_metadata": asdict(encoded.envelope_metadata),
        "decoded": decoded,
        "pass_criteria": {
            "valid": True,
            "decryptable": decoded["class_id"] == arch5.class_id,
            "within_size_limit": encoded.size_report.enveloped_bytes <= cfg.payload_max_bytes,
        },
    }

    _write_json(Path(out_dir) / "arch6_report.json", result)
    return result


def run_arch7(config_path: str = "config/canonical_config.json", out_dir: str = "artifacts") -> dict[str, Any]:
    cfg = load_canonical_config(config_path)
    scenarios = scenario_definitions()

    results: dict[str, Any] = {"scenarios": {}, "sensitivity": {}}
    for name, scenario in scenarios.items():
        sf = int(cfg.data["network"]["lora_sf_default"])
        model = default_energy_model(cfg, sf=sf)

        daily = simulate_24h(scenario, model, sf=sf, seed=101)
        mission = simulate_30d(scenario, model, sf=sf, seed=202)
        sensitivity = run_sensitivity(scenario, cfg, baseline_sf=sf, seed=303)

        results["scenarios"][name] = {
            "daily": daily,
            "mission_30d": mission,
            "power_breakdown_daily_wh": {
                "quiescent": sum(h["quiescent_wh"] for h in daily["hourly_breakdown"]),
                "inference": sum(h["inference_wh"] for h in daily["hourly_breakdown"]),
                "encryption": sum(h["encryption_wh"] for h in daily["hourly_breakdown"]),
                "transmission": sum(h["transmission_wh"] for h in daily["hourly_breakdown"]),
                "harvested": sum(h["harvested_wh"] for h in daily["hourly_breakdown"]),
            },
        }
        results["sensitivity"][name] = sensitivity

    _write_json(Path(out_dir) / "arch7_report.json", results)
    return results


def run_arch8(config_path: str = "config/canonical_config.json", out_dir: str = "artifacts") -> dict[str, Any]:
    cfg = load_canonical_config(config_path)
    queue_limit = int(cfg.data["network"]["queue_limit"])

    topologies = {
        "corbett": build_topology_corbett(queue_limit),
        "seshachalam": build_topology_seshachalam(queue_limit),
        "sundarbans": build_topology_sundarbans(queue_limit),
    }

    results: dict[str, Any] = {"campaigns": {}}
    for name, topology in topologies.items():
        baseline = run_campaign(
            topology=topology,
            config=cfg,
            payload_bytes=int(cfg.payload_target_bytes),
            sf=int(cfg.data["network"]["lora_sf_default"]),
            messages=400,
            interference_probability=0.08 if name != "sundarbans" else 0.16,
            congestion_multiplier=1.0 if name != "sundarbans" else 1.4,
            relay_failure_probability=0.02 if name != "sundarbans" else 0.06,
            seed=42,
        )

        failure_mode = run_campaign(
            topology=topology,
            config=cfg,
            payload_bytes=int(cfg.payload_target_bytes),
            sf=11,
            messages=400,
            interference_probability=0.25,
            congestion_multiplier=2.0,
            relay_failure_probability=0.15,
            seed=84,
        )

        results["campaigns"][name] = {
            "baseline": campaign_to_dict(baseline),
            "failure_mode": campaign_to_dict(failure_mode),
        }

    _write_json(Path(out_dir) / "arch8_report.json", results)
    return results


def run_all(config_path: str = "config/canonical_config.json", out_dir: str = "artifacts") -> dict[str, Any]:
    arch6 = run_arch6(config_path=config_path, out_dir=out_dir)
    arch7 = run_arch7(config_path=config_path, out_dir=out_dir)
    arch8 = run_arch8(config_path=config_path, out_dir=out_dir)

    combined = {"arch6": arch6, "arch7": arch7, "arch8": arch8}
    _write_json(Path(out_dir) / "pipeline_summary.json", combined)
    return combined
