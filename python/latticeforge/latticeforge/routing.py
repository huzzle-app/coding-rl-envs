from __future__ import annotations

from typing import Dict, Iterable, List



def choose_ground_station(
    stations: Iterable[str],
    latency_ms: Dict[str, int],
    blackout: Iterable[str],
) -> str:
    blackout_set = set(blackout)
    candidates = [station for station in stations if station not in blackout_set]
    if not candidates:
        raise ValueError("no available station")

    
    return max(candidates, key=lambda station: (latency_ms.get(station, 10_000), station))


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
