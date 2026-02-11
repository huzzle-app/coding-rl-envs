import hashlib
import unittest

from heliosops.models import DispatchOrder
from heliosops.dispatch import plan_dispatch
from heliosops.routing import choose_route
from heliosops.policy import next_policy
from heliosops.queue import should_shed
from heliosops.resilience import replay_events
from heliosops.statistics import percentile
from heliosops.workflow import can_transition
from heliosops.security import verify_signature

TOTAL_CASES = 9200


def _make_case(idx: int) -> None:
    severity_a = (idx % 7) + 1
    severity_b = ((idx * 3) % 7) + 1
    sla_a = 20 + (idx % 90)
    sla_b = 20 + ((idx * 2) % 90)

    a = DispatchOrder(f"a-{idx}", severity_a, sla_a)
    b = DispatchOrder(f"b-{idx}", severity_b, sla_b)

    orders = [
        {"id": a.id, "urgency": a.urgency_score(), "eta": f"0{idx % 9}:1{idx % 6}"},
        {"id": b.id, "urgency": b.urgency_score(), "eta": f"0{(idx + 3) % 9}:2{idx % 6}"},
        {"id": f"c-{idx}", "urgency": (idx % 50) + 2, "eta": f"1{idx % 4}:0{idx % 6}"},
    ]

    planned = plan_dispatch(orders, 2)
    assert len(planned) > 0 and len(planned) <= 2
    if len(planned) == 2:
        assert planned[0]["urgency"] >= planned[1]["urgency"]

    blocked = {"beta"} if idx % 5 == 0 else set()
    route = choose_route(
        [
            {"channel": "alpha", "latency": 2 + (idx % 9)},
            {"channel": "beta", "latency": idx % 3},
            {"channel": "gamma", "latency": 4 + (idx % 4)},
        ],
        blocked,
    )
    assert route is not None
    if "beta" in blocked:
        assert route["channel"] != "beta"

    from_st = "queued" if idx % 2 == 0 else "allocated"
    to_st = "allocated" if from_st == "queued" else "departed"
    assert can_transition(from_st, to_st) is True
    assert can_transition("arrived", "queued") is False

    pol = next_policy("normal" if idx % 2 == 0 else "watch", 2 + (idx % 2))
    assert pol in ("watch", "restricted", "halted")

    queue_depth = (idx % 30) + 1
    assert should_shed(queue_depth, 40, False) is False
    assert should_shed(41, 40, False) is True

    replayed = replay_events(
        [
            {"id": f"k-{idx % 17}", "sequence": 1},
            {"id": f"k-{idx % 17}", "sequence": 2},
            {"id": f"z-{idx % 13}", "sequence": 1},
        ]
    )
    assert len(replayed) >= 2
    assert replayed[-1]["sequence"] >= 1

    p = percentile(
        [idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11], 50
    )
    assert isinstance(p, (int, float))

    if idx % 17 == 0:
        payload = f"manifest:{idx}"
        digest = hashlib.sha256(payload.encode()).hexdigest()
        assert verify_signature(payload, digest, digest) is True
        assert verify_signature(payload, digest[1:], digest) is False


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
