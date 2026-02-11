import unittest

from services.identity.service import authorize_intent, derive_context, least_privilege_roles


class IdentityServiceTest(unittest.TestCase):
    def test_authorize_allows_exact_clearance_match(self) -> None:
        context = derive_context(
            {
                "operator_id": "op-1",
                "org_id": "orbital",
                "roles": ["planner"],
                "mfa_level": 2,
            }
        )
        self.assertTrue(authorize_intent(context, "orbit-adjust", severity=3))

    def test_authorize_requires_mfa_for_high_risk(self) -> None:
        context = derive_context(
            {
                "operator_id": "op-2",
                "org_id": "orbital",
                "roles": ["flight-director"],
                "mfa_level": 1,
            }
        )
        self.assertFalse(authorize_intent(context, "failover-region", severity=4))

    def test_least_privilege_roles_sorted(self) -> None:
        roles = least_privilege_roles("replay-window", severity=2)
        self.assertIn("planner", roles)
        self.assertLessEqual(roles.index("planner"), roles.index("security"))


if __name__ == "__main__":
    unittest.main()
