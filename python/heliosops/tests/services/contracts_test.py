import unittest

from shared.contracts.contracts import CONTRACTS


class ContractTests(unittest.TestCase):
    def test_contracts_expose_required_keys(self) -> None:
        self.assertEqual(CONTRACTS["gateway"]["id"], "gateway")
        self.assertIsInstance(CONTRACTS["routing"]["port"], int)


if __name__ == "__main__":
    unittest.main()
