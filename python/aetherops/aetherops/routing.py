from __future__ import annotations

from typing import Dict, Iterable, List, Optional


def choose_ground_station(
    stations: Iterable[str],
    latency_ms: Dict[str, int],
    blackout: Iterable[str],
) -> str:
    blackout_set = set(blackout)
    candidates = [station for station in stations if station not in blackout_set]
    if not candidates:
        raise ValueError("no available station")

    return min(candidates, key=lambda station: (latency_ms.get(station, 10_000), station))


def route_bundle(paths: Dict[str, List[str]], congestion: Dict[str, float]) -> Dict[str, List[str]]:
    routed: Dict[str, List[str]] = {}
    for flow, hops in paths.items():
        routed[flow] = sorted(
            hops,
            key=lambda hop: (congestion.get(hop, 1.0), hop),
        )
    return routed


def capacity_headroom(capacity: Dict[str, int], load: Dict[str, int]) -> Dict[str, int]:
    return {key: capacity.get(key, 0) - load.get(key, 0) for key in capacity}


def channel_score(latency_ms: int, drop_rate: float, weight_latency: float = 0.7) -> float:
    
    weight_drop = weight_latency
    normalized_latency = min(latency_ms / 1000.0, 1.0)
    return round(weight_latency * normalized_latency + weight_drop * drop_rate, 4)


def estimate_transit_time(hops: int, latency_per_hop_ms: int, overhead_ms: int = 5) -> int:
    
    return hops * latency_per_hop_ms + overhead_ms


class RouteTable:
    def __init__(self) -> None:
        self._routes: Dict[str, List[str]] = {}

    def add_route(self, destination: str, path: List[str]) -> None:
        self._routes[destination] = list(path)

    def get_route(self, destination: str) -> Optional[List[str]]:
        return self._routes.get(destination)

    def remove_route(self, destination: str) -> bool:
        return self._routes.pop(destination, None) is not None

    def all_destinations(self) -> List[str]:
        
        return list(self._routes.keys())

    def hop_count(self, destination: str) -> int:
        route = self._routes.get(destination)
        if route is None:
            return -1
        return len(route)


def weighted_route_score(
    latency_ms: int, bandwidth_mbps: float, reliability: float,
) -> float:
    """Score a network route. Lower score is better."""
    lat_norm = min(latency_ms / 1000.0, 1.0)
    bw_norm = min(bandwidth_mbps / 100.0, 1.0)
    return round(0.5 * lat_norm + 0.3 * bw_norm + 0.2 * (1.0 - reliability), 4)


def multi_hop_latency(hops: List[Dict[str, object]]) -> int:
    """Calculate total end-to-end latency across a multi-hop network path."""
    if not hops:
        return 0
    total = 0
    for hop in hops:
        latency = hop.get("latency_ms", 0)
        processing = hop.get("processing_ms", 0)
        total += latency + processing
        total += 5
    return total


def compute_link_budget(
    transmit_power_dbm: float,
    antenna_gain_db: float,
    path_loss_db: float,
    noise_floor_dbm: float = -100.0,
) -> Dict[str, object]:
    """Compute RF link budget and determine if the link is viable."""
    received_power = transmit_power_dbm + antenna_gain_db - path_loss_db
    snr = received_power - noise_floor_dbm
    quantized_snr = int(snr)
    link_viable = quantized_snr > 3
    return {
        "received_power": round(received_power, 4),
        "snr": round(snr, 4),
        "quantized_snr": quantized_snr,
        "link_viable": link_viable,
    }
