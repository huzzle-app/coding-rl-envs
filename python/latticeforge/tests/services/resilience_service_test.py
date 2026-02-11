import unittest

from services.resilience.service import adaptive_backoff_schedule, build_replay_plan, partition_replay_batches


class ResilienceServiceTest(unittest.TestCase):
    def test_plan_avoids_degraded_failover_region(self) -> None:
        plan = build_replay_plan(
            events=120,
            timeout_s=30,
            primary_region="us-east",
            candidate_regions=["us-east", "us-west", "eu-central"],
            degraded_regions=["us-west"],
        )
        self.assertEqual(plan.region, "eu-central")

    def test_backoff_schedule_and_partition(self) -> None:
        schedule = adaptive_backoff_schedule(retries=4, cap_ms=800)
        self.assertEqual(len(schedule), 4)
        self.assertLessEqual(schedule[-1], 800)

        batches = partition_replay_batches(["a", "b", "c", "d", "e"], batch_size=2)
        self.assertEqual(batches, [["a", "b"], ["c", "d"], ["e"]])


if __name__ == "__main__":
    unittest.main()
