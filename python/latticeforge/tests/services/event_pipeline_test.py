import unittest

from services.audit.service import EventPipeline


class EventPipelineTest(unittest.TestCase):
    def test_happy_path(self) -> None:
        p = EventPipeline()
        p.receive("e1", {"trace_id": "t1", "service": "gw"})
        self.assertTrue(p.validate("e1"))
        self.assertTrue(p.enrich("e1", {"region": "us-east"}))
        self.assertTrue(p.persist("e1"))
        self.assertTrue(p.acknowledge("e1"))
        self.assertEqual(p.get_stage("e1"), "acknowledged")

    def test_validation_rejects_missing_fields(self) -> None:
        p = EventPipeline()
        p.receive("e2", {"trace_id": "t2"})
        self.assertFalse(p.validate("e2"))
        self.assertEqual(p.get_stage("e2"), "received")

    def test_retry_resets_pipeline_state(self) -> None:
        p = EventPipeline()
        p.receive("e3", {"trace_id": "t3", "service": "gw"})
        p.validate("e3")
        p.enrich("e3", {"region": "us-east", "priority": "high"})
        p.retry("e3", {"trace_id": "t3", "service": "updated-gw"})
        enrichment = p.get_enrichment("e3")
        self.assertEqual(enrichment, {})

    def test_retry_then_full_pipeline(self) -> None:
        p = EventPipeline()
        p.receive("e4", {"trace_id": "t4", "service": "gw", "version": "1"})
        p.validate("e4")
        p.enrich("e4", {"region": "us-east", "source_version": "1"})
        p.retry("e4", {"trace_id": "t4", "service": "gw", "version": "2"})
        self.assertEqual(p.get_stage("e4"), "received")
        self.assertEqual(p.get_enrichment("e4"), {})
        p.validate("e4")
        p.enrich("e4", {"region": "eu-west", "source_version": "2"})
        enrichment = p.get_enrichment("e4")
        self.assertEqual(enrichment["source_version"], "2")
        self.assertEqual(enrichment["region"], "eu-west")

    def test_retry_blocked_for_acknowledged(self) -> None:
        p = EventPipeline()
        p.receive("e5", {"trace_id": "t5", "service": "gw"})
        p.validate("e5")
        p.enrich("e5", {"region": "us-west"})
        p.persist("e5")
        p.acknowledge("e5")
        self.assertFalse(p.retry("e5", {"trace_id": "t5", "service": "new"}))

    def test_retry_sequence_data_isolation(self) -> None:
        p = EventPipeline()
        p.receive("e6", {"trace_id": "t6", "service": "s1"})
        p.validate("e6")
        p.enrich("e6", {"env": "prod", "ttl": "3600"})
        p.retry("e6", {"trace_id": "t6", "service": "s2"})
        p.validate("e6")
        stale = p.get_enrichment("e6")
        self.assertNotIn("env", stale)
        self.assertNotIn("ttl", stale)

    def test_persist_requires_enrichment(self) -> None:
        p = EventPipeline()
        p.receive("e7", {"trace_id": "t7", "service": "gw"})
        p.validate("e7")
        self.assertFalse(p.persist("e7"))

    def test_stage_progression(self) -> None:
        p = EventPipeline()
        p.receive("e8", {"trace_id": "t8", "service": "gw"})
        self.assertEqual(p.get_stage("e8"), "received")
        p.validate("e8")
        self.assertEqual(p.get_stage("e8"), "validated")
        p.enrich("e8", {"k": "v"})
        self.assertEqual(p.get_stage("e8"), "enriched")
        p.persist("e8")
        self.assertEqual(p.get_stage("e8"), "persisted")


if __name__ == "__main__":
    unittest.main()
