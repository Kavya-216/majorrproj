from __future__ import annotations

import heapq
import math
import random
from dataclasses import asdict, dataclass
from statistics import mean
from typing import Any

from .config import CanonicalConfig

RX_SENSITIVITY_DBM = {
    7: -123,
    8: -126,
    9: -129,
    10: -132,
    11: -134,
    12: -137,
}


def lora_time_on_air_ms(payload_bytes: int, sf: int, bandwidth_hz: int = 125_000, coding_rate: int = 1) -> float:
    if sf not in RX_SENSITIVITY_DBM:
        raise ValueError(f"Unsupported spreading factor: {sf}")
    if payload_bytes <= 0:
        raise ValueError("payload_bytes must be positive")

    preamble_symbols = 8
    low_data_rate_opt = 1 if sf >= 11 else 0
    ih = 0
    crc = 1

    t_sym = (2**sf) / bandwidth_hz
    t_preamble = (preamble_symbols + 4.25) * t_sym
    payload_num = 8 * payload_bytes - 4 * sf + 28 + 16 * crc - 20 * ih
    payload_den = 4 * (sf - 2 * low_data_rate_opt)
    payload_symbols = 8 + max(math.ceil(payload_num / payload_den) * (coding_rate + 4), 0)
    t_payload = payload_symbols * t_sym

    return (t_preamble + t_payload) * 1000.0


@dataclass(frozen=True)
class Node:
    node_id: str
    lat: float
    lon: float
    node_type: str


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    distance_km: float


@dataclass(frozen=True)
class CampaignResult:
    scenario: str
    messages: int
    delivered: int
    delivery_rate: float
    packet_loss_rate: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_p99_ms: float | None
    average_hops: float | None
    queue_overflows: int
    retries_exhausted: int
    interference_events: int
    relay_failures: int
    recommendations: list[str]


class MeshTopology:
    def __init__(self, name: str, queue_limit: int):
        self.name = name
        self.queue_limit = queue_limit
        self.nodes: dict[str, Node] = {}
        self.edges: dict[tuple[str, str], Edge] = {}

    def add_node(self, node: Node) -> None:
        self.nodes[node.node_id] = node

    def connect_all(self) -> None:
        ids = list(self.nodes)
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                src = self.nodes[ids[i]]
                dst = self.nodes[ids[j]]
                d = haversine_km(src.lat, src.lon, dst.lat, dst.lon)
                self.edges[(src.node_id, dst.node_id)] = Edge(src.node_id, dst.node_id, d)
                self.edges[(dst.node_id, src.node_id)] = Edge(dst.node_id, src.node_id, d)

    def base_station(self) -> str:
        base = [n.node_id for n in self.nodes.values() if n.node_type == "base"]
        if not base:
            raise ValueError("Topology has no base station")
        return base[0]

    def sensors(self) -> list[str]:
        return [n.node_id for n in self.nodes.values() if n.node_type == "sensor"]

    def relays(self) -> list[str]:
        return [n.node_id for n in self.nodes.values() if n.node_type == "relay"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(
        dlon / 2
    ) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fspl_path_loss_db(distance_km: float, frequency_mhz: float = 865.0) -> float:
    # Friis free-space path loss in dB for distance in km and frequency in MHz.
    d_km = max(distance_km, 0.001)
    return 20 * math.log10(d_km) + 20 * math.log10(frequency_mhz) + 32.45


def rx_success_probability(distance_km: float, sf: int, tx_power_dbm: float, fading_sigma_db: float, interference: bool) -> float:
    sensitivity = RX_SENSITIVITY_DBM[sf]
    path_loss = fspl_path_loss_db(distance_km)
    fading_db = random.gauss(0.0, fading_sigma_db)
    rssi = tx_power_dbm - path_loss - max(0.0, fading_db)
    margin = rssi - sensitivity

    if margin < -5:
        base = 0.0
    elif margin < 0:
        base = 0.35
    elif margin < 3:
        base = 0.75
    elif margin < 6:
        base = 0.92
    else:
        base = 0.985

    if interference:
        base *= 0.82

    return max(0.0, min(1.0, base))


def shortest_path(topology: MeshTopology, source: str, relay_failures: set[str]) -> list[str]:
    target = topology.base_station()
    dist = {node: float("inf") for node in topology.nodes}
    prev: dict[str, str | None] = {node: None for node in topology.nodes}
    dist[source] = 0.0
    pq: list[tuple[float, str]] = [(0.0, source)]

    while pq:
        current_dist, current = heapq.heappop(pq)
        if current == target:
            break
        if current_dist > dist[current]:
            continue

        for neighbor in topology.nodes:
            if neighbor == current:
                continue
            if topology.nodes[neighbor].node_type == "relay" and neighbor in relay_failures:
                continue
            edge = topology.edges.get((current, neighbor))
            if edge is None:
                continue
            cand = current_dist + edge.distance_km
            if cand < dist[neighbor]:
                dist[neighbor] = cand
                prev[neighbor] = current
                heapq.heappush(pq, (cand, neighbor))

    if dist[target] == float("inf"):
        return []

    rev = []
    cur = target
    while cur is not None:
        rev.append(cur)
        cur = prev[cur]
    return list(reversed(rev))


def build_topology_corbett(queue_limit: int) -> MeshTopology:
    t = MeshTopology("Corbett", queue_limit)
    t.add_node(Node("S1", 29.250, 79.100, "sensor"))
    t.add_node(Node("S2", 29.300, 79.150, "sensor"))
    t.add_node(Node("S3", 29.200, 79.050, "sensor"))
    t.add_node(Node("R1", 29.270, 79.120, "relay"))
    t.add_node(Node("R2", 29.220, 79.080, "relay"))
    t.add_node(Node("BASE", 29.240, 79.100, "base"))
    t.connect_all()
    return t


def build_topology_seshachalam(queue_limit: int) -> MeshTopology:
    t = MeshTopology("Seshachalam", queue_limit)
    t.add_node(Node("S1", 13.150, 79.350, "sensor"))
    t.add_node(Node("S2", 13.200, 79.400, "sensor"))
    t.add_node(Node("R1", 13.170, 79.370, "relay"))
    t.add_node(Node("BASE", 13.180, 79.380, "base"))
    t.connect_all()
    return t


def build_topology_sundarbans(queue_limit: int) -> MeshTopology:
    t = MeshTopology("Sundarbans", queue_limit)
    t.add_node(Node("S1", 21.900, 88.500, "sensor"))
    t.add_node(Node("S2", 21.950, 88.550, "sensor"))
    t.add_node(Node("S3", 21.850, 88.450, "sensor"))
    t.add_node(Node("S4", 21.880, 88.600, "sensor"))
    t.add_node(Node("R1", 21.920, 88.520, "relay"))
    t.add_node(Node("R2", 21.870, 88.570, "relay"))
    t.add_node(Node("BASE", 21.900, 88.500, "base"))
    t.connect_all()
    return t


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    idx = (len(vals) - 1) * pct
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return vals[lo]
    frac = idx - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def run_campaign(
    topology: MeshTopology,
    config: CanonicalConfig,
    payload_bytes: int,
    sf: int,
    messages: int,
    interference_probability: float,
    congestion_multiplier: float,
    relay_failure_probability: float,
    seed: int = 7,
) -> CampaignResult:
    random.seed(seed)

    tx_dbm = float(config.data["power"]["tx_power_profile"]["default_dbm"])
    max_retries = int(config.data["network"]["max_retries"])

    delivered = 0
    queue_overflows = 0
    retries_exhausted = 0
    interference_events = 0
    relay_failures_count = 0
    latencies_ms: list[float] = []
    hops: list[int] = []

    relay_failures: set[str] = set()
    for relay in topology.relays():
        if random.random() < relay_failure_probability:
            relay_failures.add(relay)
    relay_failures_count = len(relay_failures)

    queue_backlog = {node: 0 for node in topology.nodes}

    for _ in range(messages):
        src = random.choice(topology.sensors())
        route = shortest_path(topology, src, relay_failures)
        if not route or len(route) < 2:
            retries_exhausted += 1
            continue

        total_latency = 0.0
        success = True

        for i in range(len(route) - 1):
            a = route[i]
            b = route[i + 1]
            edge = topology.edges[(a, b)]
            link_interference = random.random() < interference_probability
            if link_interference:
                interference_events += 1

            p_success = rx_success_probability(
                distance_km=edge.distance_km,
                sf=sf,
                tx_power_dbm=tx_dbm,
                fading_sigma_db=4.5,
                interference=link_interference,
            )

            attempt_success = False
            for attempt in range(max_retries + 1):
                toa = lora_time_on_air_ms(payload_bytes=payload_bytes, sf=sf)
                queue_delay = queue_backlog[a] * 4.0 * congestion_multiplier
                processing_delay = random.uniform(4.0, 14.0)
                total_latency += toa + queue_delay + processing_delay

                if random.random() <= p_success:
                    attempt_success = True
                    break

                if attempt == max_retries:
                    retries_exhausted += 1

            if not attempt_success:
                success = False
                break

            queue_backlog[a] += 1
            if queue_backlog[a] > topology.queue_limit:
                queue_overflows += 1
                queue_backlog[a] = topology.queue_limit
                success = False
                break

        for node in queue_backlog:
            queue_backlog[node] = max(0, queue_backlog[node] - random.randint(0, 2))

        if success:
            delivered += 1
            latencies_ms.append(total_latency)
            hops.append(len(route) - 1)

    delivery_rate = delivered / messages if messages else 0.0
    packet_loss_rate = 1.0 - delivery_rate

    recommendations: list[str] = []
    if delivery_rate < float(config.data["network"]["delivery_target_min"]):
        recommendations.append("Increase relay density or reduce hop distance in weak links.")
    p95 = percentile(latencies_ms, 0.95)
    if p95 is not None and p95 / 1000.0 > float(config.data["network"]["latency_target_p95_seconds"]):
        recommendations.append("Reduce SF or apply traffic shaping to lower p95 latency.")
    if queue_overflows > 0:
        recommendations.append("Increase per-node queue limit or lower alert burst rate.")
    if relay_failures_count > 0:
        recommendations.append("Add redundant relay near failed corridor nodes.")
    if not recommendations:
        recommendations.append("Current topology satisfies target delivery and latency constraints.")

    return CampaignResult(
        scenario=topology.name,
        messages=messages,
        delivered=delivered,
        delivery_rate=delivery_rate,
        packet_loss_rate=packet_loss_rate,
        latency_p50_ms=percentile(latencies_ms, 0.50),
        latency_p95_ms=p95,
        latency_p99_ms=percentile(latencies_ms, 0.99),
        average_hops=mean(hops) if hops else None,
        queue_overflows=queue_overflows,
        retries_exhausted=retries_exhausted,
        interference_events=interference_events,
        relay_failures=relay_failures_count,
        recommendations=recommendations,
    )


def campaign_to_dict(result: CampaignResult) -> dict[str, Any]:
    return asdict(result)
