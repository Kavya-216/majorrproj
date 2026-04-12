from __future__ import annotations

from ecosentry.arch8_network import build_topology_seshachalam, run_campaign
from ecosentry.config import load_canonical_config


def test_arch8_campaign_outputs_metrics() -> None:
    cfg = load_canonical_config("config/canonical_config.json")
    topology = build_topology_seshachalam(int(cfg.data["network"]["queue_limit"]))

    result = run_campaign(
        topology=topology,
        config=cfg,
        payload_bytes=116,
        sf=9,
        messages=120,
        interference_probability=0.05,
        congestion_multiplier=1.0,
        relay_failure_probability=0.01,
        seed=777,
    )

    assert 0.0 <= result.delivery_rate <= 1.0
    assert 0.0 <= result.packet_loss_rate <= 1.0
    assert result.latency_p95_ms is None or result.latency_p95_ms >= 0.0
    assert isinstance(result.recommendations, list) and len(result.recommendations) >= 1
