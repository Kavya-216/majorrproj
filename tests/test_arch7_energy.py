from __future__ import annotations

from ecosentry.arch7_energy import default_energy_model, run_sensitivity, scenario_definitions, simulate_24h, simulate_30d
from ecosentry.config import load_canonical_config


def test_arch7_daily_and_30d_outputs() -> None:
    cfg = load_canonical_config("config/canonical_config.json")
    scenario = scenario_definitions()["corbett"]
    model = default_energy_model(cfg, sf=9)

    daily = simulate_24h(scenario, model, sf=9, seed=123)
    mission = simulate_30d(scenario, model, sf=9, seed=456)

    assert len(daily["hourly_breakdown"]) == 24
    assert len(mission["battery_trajectory"]) == 30
    assert 0.0 <= mission["final_soc_percent"] <= 100.0


def test_arch7_sensitivity_includes_required_axes() -> None:
    cfg = load_canonical_config("config/canonical_config.json")
    scenario = scenario_definitions()["sundarbans"]
    studies = run_sensitivity(scenario, cfg, baseline_sf=9, seed=789)

    labels = {s["study"] for s in studies}
    assert {"alert_rate_x2", "heavy_cloud", "battery_3000mah", "sf12", "sf7"}.issubset(labels)
