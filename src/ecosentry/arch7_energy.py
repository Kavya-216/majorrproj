from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any

from .arch8_network import lora_time_on_air_ms
from .config import CanonicalConfig


@dataclass(frozen=True)
class EnergyScenario:
    name: str
    latitude_deg: float
    avg_alerts_per_day: float
    cloud_cover_mean: float
    cloud_cover_std: float


@dataclass(frozen=True)
class EnergyModel:
    quiescent_mw: float
    inference_mw: float
    encryption_mw: float
    transmission_mw: float
    audio_mw: float
    spike_mw: float
    inference_duration_s: float
    encryption_duration_s: float
    audio_duration_s: float
    spike_duration_s: float
    battery_mah: int
    battery_voltage: float
    solar_panel_peak_w: float
    payload_bytes: int

    @property
    def battery_wh(self) -> float:
        return (self.battery_mah / 1000.0) * self.battery_voltage


def default_energy_model(config: CanonicalConfig, sf: int) -> EnergyModel:
    tx_profile = config.data["power"]["tx_power_profile"]
    tx_mw = float(tx_profile["default_mw"])
    tx_dbm = int(tx_profile["default_dbm"])
    if tx_dbm == int(tx_profile["fallback_dbm"]):
        tx_mw = float(tx_profile["fallback_mw"])

    toa_s = lora_time_on_air_ms(payload_bytes=config.payload_target_bytes, sf=sf) / 1000.0

    return EnergyModel(
        quiescent_mw=float(config.data["power"]["quiescent_mw"]),
        inference_mw=30.0,
        encryption_mw=5.0,
        transmission_mw=tx_mw,
        audio_mw=2.0,
        spike_mw=1.0,
        inference_duration_s=max(0.02, float(config.data["power"]["inference_window_seconds"])),
        encryption_duration_s=0.008,
        audio_duration_s=0.10,
        spike_duration_s=0.015,
        battery_mah=int(config.data["power"]["battery_mah_default"]),
        battery_voltage=float(config.data["power"]["battery_voltage"]),
        solar_panel_peak_w=0.5,
        payload_bytes=int(config.payload_target_bytes),
    )


def scenario_definitions() -> dict[str, EnergyScenario]:
    return {
        "corbett": EnergyScenario("Corbett", 29.2, 5.0, 0.35, 0.18),
        "seshachalam": EnergyScenario("Seshachalam", 13.2, 3.0, 0.30, 0.15),
        "sundarbans": EnergyScenario("Sundarbans", 21.9, 8.0, 0.55, 0.20),
    }


def _solar_profile_w(latitude_deg: float, day_of_year: int, cloud_cover: float, peak_w: float) -> list[float]:
    profile: list[float] = []
    seasonal = 1.0 + 0.10 * math.sin((2 * math.pi * (day_of_year - 80)) / 365.0)

    for h in range(24):
        if h < 6 or h > 18:
            profile.append(0.0)
            continue
        hour_angle = (h - 12) / 6.0
        clear_sky = max(0.0, 1.0 - hour_angle * hour_angle)
        latitude_penalty = max(0.75, 1.0 - abs(latitude_deg - 20.0) * 0.01)
        irradiance = peak_w * clear_sky * seasonal * latitude_penalty
        profile.append(max(0.0, irradiance * (1.0 - cloud_cover)))
    return profile


def _event_energy_wh(model: EnergyModel, alerts_in_hour: int, sf: int) -> dict[str, float]:
    toa_s = lora_time_on_air_ms(payload_bytes=model.payload_bytes, sf=sf) / 1000.0

    inference_wh = ((model.audio_mw * model.audio_duration_s) + (model.spike_mw * model.spike_duration_s) + (
        model.inference_mw * model.inference_duration_s
    )) * alerts_in_hour / 1000.0 / 3600.0
    encryption_wh = (model.encryption_mw * model.encryption_duration_s * alerts_in_hour) / 1000.0 / 3600.0
    transmission_wh = (model.transmission_mw * toa_s * alerts_in_hour) / 1000.0 / 3600.0
    return {
        "inference_wh": inference_wh,
        "encryption_wh": encryption_wh,
        "transmission_wh": transmission_wh,
    }


def simulate_24h(scenario: EnergyScenario, model: EnergyModel, sf: int, day_of_year: int = 150, seed: int = 11) -> dict[str, Any]:
    random.seed(seed)
    battery_wh = model.battery_wh
    capacity_wh = model.battery_wh

    cloud_cover = max(0.0, min(0.95, random.gauss(scenario.cloud_cover_mean, scenario.cloud_cover_std)))
    solar_w = _solar_profile_w(scenario.latitude_deg, day_of_year, cloud_cover, model.solar_panel_peak_w)

    hourly_soc = []
    hourly_breakdown = []

    for hour in range(24):
        alerts = max(0, int(round(random.gauss(scenario.avg_alerts_per_day / 24.0, 0.5))))
        quiescent_wh = (model.quiescent_mw * 3600.0) / 1000.0 / 3600.0
        events = _event_energy_wh(model, alerts, sf)
        consumed_wh = quiescent_wh + events["inference_wh"] + events["encryption_wh"] + events["transmission_wh"]

        harvested_wh = solar_w[hour]
        battery_wh = max(0.0, min(capacity_wh, battery_wh - consumed_wh + harvested_wh))

        hourly_soc.append((battery_wh / capacity_wh) * 100.0)
        hourly_breakdown.append(
            {
                "hour": hour,
                "alerts": alerts,
                "quiescent_wh": quiescent_wh,
                "inference_wh": events["inference_wh"],
                "encryption_wh": events["encryption_wh"],
                "transmission_wh": events["transmission_wh"],
                "harvested_wh": harvested_wh,
                "battery_wh": battery_wh,
            }
        )

    return {
        "scenario": scenario.name,
        "cloud_cover": cloud_cover,
        "sf": sf,
        "hourly_soc": hourly_soc,
        "hourly_breakdown": hourly_breakdown,
        "daily_consumption_wh": sum(
            b["quiescent_wh"] + b["inference_wh"] + b["encryption_wh"] + b["transmission_wh"]
            for b in hourly_breakdown
        ),
        "daily_harvest_wh": sum(b["harvested_wh"] for b in hourly_breakdown),
    }


def simulate_30d(
    scenario: EnergyScenario,
    model: EnergyModel,
    sf: int,
    start_day_of_year: int = 150,
    seed: int = 13,
) -> dict[str, Any]:
    random.seed(seed)
    capacity_wh = model.battery_wh
    battery_wh = capacity_wh

    trajectory = []
    for day in range(30):
        day_seed = seed + day
        day_res = simulate_24h(
            scenario=scenario,
            model=model,
            sf=sf,
            day_of_year=((start_day_of_year + day - 1) % 365) + 1,
            seed=day_seed,
        )
        battery_wh = max(0.0, min(capacity_wh, battery_wh - day_res["daily_consumption_wh"] + day_res["daily_harvest_wh"]))
        trajectory.append(
            {
                "day": day + 1,
                "battery_wh": battery_wh,
                "soc_percent": (battery_wh / capacity_wh) * 100.0,
                "daily_consumption_wh": day_res["daily_consumption_wh"],
                "daily_harvest_wh": day_res["daily_harvest_wh"],
            }
        )

    return {
        "scenario": scenario.name,
        "sf": sf,
        "battery_trajectory": trajectory,
        "survived_30_days": trajectory[-1]["battery_wh"] > 0,
        "final_soc_percent": trajectory[-1]["soc_percent"],
    }


def run_sensitivity(
    scenario: EnergyScenario,
    config: CanonicalConfig,
    baseline_sf: int = 9,
    seed: int = 19,
) -> list[dict[str, Any]]:
    studies = []

    for label, alert_mult, cloud_delta, battery_mah, sf in [
        ("baseline", 1.0, 0.0, int(config.data["power"]["battery_mah_default"]), baseline_sf),
        ("alert_rate_x2", 2.0, 0.0, int(config.data["power"]["battery_mah_default"]), baseline_sf),
        ("heavy_cloud", 1.0, 0.20, int(config.data["power"]["battery_mah_default"]), baseline_sf),
        ("battery_3000mah", 1.0, 0.0, 3000, baseline_sf),
        ("sf12", 1.0, 0.0, int(config.data["power"]["battery_mah_default"]), 12),
        ("sf7", 1.0, 0.0, int(config.data["power"]["battery_mah_default"]), 7),
    ]:
        tuned = EnergyScenario(
            name=scenario.name,
            latitude_deg=scenario.latitude_deg,
            avg_alerts_per_day=scenario.avg_alerts_per_day * alert_mult,
            cloud_cover_mean=max(0.0, min(0.95, scenario.cloud_cover_mean + cloud_delta)),
            cloud_cover_std=scenario.cloud_cover_std,
        )

        model = default_energy_model(config, sf=sf)
        model = EnergyModel(**{**asdict(model), "battery_mah": battery_mah})
        sim = simulate_30d(tuned, model, sf=sf, seed=seed + hash(label) % 100)

        avg_daily_net = mean(d["daily_harvest_wh"] - d["daily_consumption_wh"] for d in sim["battery_trajectory"])
        studies.append(
            {
                "study": label,
                "scenario": scenario.name,
                "sf": sf,
                "battery_mah": battery_mah,
                "final_soc_percent": sim["final_soc_percent"],
                "survived_30_days": sim["survived_30_days"],
                "avg_daily_net_wh": avg_daily_net,
            }
        )

    return studies
