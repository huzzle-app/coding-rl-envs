import unittest

from aetherops.models import MissionLedger
from aetherops.orbit import allocate_burns
from tests.test_helper import sample_incidents, sample_windows


class ModelsTest(unittest.TestCase):
    def test_mission_ledger(self) -> None:
        ledger = MissionLedger()
        burn = allocate_burns(sample_windows(), 0.4)[0]
        ledger.append_burn(burn)
        ledger.incidents.extend(sample_incidents())
        self.assertEqual(len(ledger.executed_burns), 1)
        self.assertEqual(ledger.unresolved_incidents(), 1)


if __name__ == "__main__":
    unittest.main()
