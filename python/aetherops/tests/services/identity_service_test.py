import unittest

from services.identity.service import (
    OperatorContext,
    derive_context,
    authorize_intent,
    has_role,
    validate_session,
    list_permissions,
)


class IdentityServiceTest(unittest.TestCase):
    def test_authorize_intent_exact_match(self) -> None:
        ctx = OperatorContext(
            operator_id="op1", name="Alice", roles=["operator"],
            clearance=3, mfa_verified=False,
        )
        # Clearance 3 should pass required_clearance 3 (>= not >)
        self.assertTrue(authorize_intent(ctx, required_clearance=3))

    def test_has_role_case_sensitivity(self) -> None:
        ctx = OperatorContext(
            operator_id="op1", name="Alice",
            roles=["Operator", "Engineer"],
            clearance=3,
        )
        # Should match case-insensitively: "operator" should match "Operator"
        self.assertTrue(has_role(ctx, "operator"))

    def test_validate_session(self) -> None:
        # Operator with no roles should fail validation
        ctx = OperatorContext(
            operator_id="op1", name="Alice", roles=[], clearance=1,
        )
        result = validate_session(ctx, max_idle_s=300, idle_s=100)
        self.assertFalse(result)

    def test_list_permissions_dedup(self) -> None:
        ctx = OperatorContext(
            operator_id="op1", name="Alice",
            roles=["admin", "operator"],
            clearance=5,
        )
        perms = list_permissions(ctx)
        # Should contain no duplicates
        self.assertEqual(len(perms), len(set(perms)))


if __name__ == "__main__":
    unittest.main()
