from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from latticeforge.models import BurnWindow, IncidentTicket, OrbitalSnapshot
from latticeforge.orbit import allocate_burns, compute_delta_v
from latticeforge.policy import evaluate_risk, requires_hold
from latticeforge.resilience import replay_budget, retry_backoff
from latticeforge.routing import choose_ground_station
from latticeforge.scheduler import schedule_operations
from latticeforge.security import requires_mfa
from latticeforge.statistics import percentile
from latticeforge.workflow import orchestrate_cycle

TOTAL_CASES = 9800


def _make_case(idx: int) -> None:
    snapshot = OrbitalSnapshot(
        satellite_id=f"sat-{idx % 97}",
        fuel_kg=160.0 + float(idx % 20),
        power_kw=5.2,
        temperature_c=20.0 + float((idx % 11) - 5),
        altitude_km=540.0 + float(idx % 25),
        epoch=datetime(2026, 1, 1, 12, 0, 0),
    )
    now = datetime(2026, 1, 1, 12, 0, 0)
    windows = [
        BurnWindow("w1", now + timedelta(minutes=5), now + timedelta(minutes=12), 0.52, 2),
        BurnWindow("w2", now + timedelta(minutes=18), now + timedelta(minutes=27), 0.84, 3),
        BurnWindow("w3", now + timedelta(minutes=35), now + timedelta(minutes=46), 0.43, 1),
    ]
    incidents = [IncidentTicket(f"i-{idx}", severity=(idx % 5) + 1, subsystem="comms", description="packet loss")]

    required = compute_delta_v(distance_km=abs(snapshot.altitude_km - 540.0), mass_kg=max(snapshot.fuel_kg, 1.0) * 4.8)
    burns = allocate_burns(windows, required)
    risk = evaluate_risk(snapshot, burns, incidents)

    expected_hold_risk = 62.0 if idx % 2 == 0 else 75.0
    assert requires_hold(expected_hold_risk, comms_degraded=False) is True
    if idx % 5 == 0:
        assert requires_hold(50.0, comms_degraded=True) is True

    station = choose_ground_station(["sg-1", "sg-2", "sg-3"], {"sg-1": 95, "sg-2": 70, "sg-3": 120}, blackout=[])
    assert station == "sg-2"

    if idx % 4 == 0:
        baseline = min((idx % 500) + 10, ((idx % 15) + 1) * 12)
        expected_budget = max(int(baseline * 0.9), 1)
        budget = replay_budget(events=(idx % 500) + 10, timeout_s=(idx % 15) + 1)
        assert budget == expected_budget

    delay = retry_backoff((idx % 8) + 1, cap_ms=1000)
    assert delay <= 1000

    sched = schedule_operations(windows, incidents, now)
    assert len(sched) == 3

    pct = percentile([idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11], 50)
    assert isinstance(pct, float)

    assert requires_mfa("operator", (idx % 5) + 1) is ((idx % 5) + 1 >= 4)

    cycle = orchestrate_cycle(snapshot, windows, incidents, {"sg-1": 95, "sg-2": 70}, now)
    assert cycle["station"] == "sg-2"
    assert float(cycle["risk_score"]) >= 0.0
    assert risk >= 0.0


class HyperMatrixTest(unittest.TestCase):
    pass


def _add_case(i: int) -> None:
    def test_fn(self: unittest.TestCase) -> None:
        _make_case(i)

    setattr(HyperMatrixTest, f"test_hyper_matrix_{i:05d}", test_fn)


for _i in range(TOTAL_CASES):
    _add_case(_i)


if __name__ == "__main__":
    unittest.main()
