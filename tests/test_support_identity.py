from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from check_support_identity import KNOWN_MINTS, TOKEN_FIELD, main  # noqa: E402


class SupportIdentityTest(unittest.TestCase):
    def test_token_field_patterns_are_rejected(self) -> None:
        self.assertIsNotNone(TOKEN_FIELD.search("**CA**: address"))
        self.assertIsNotNone(TOKEN_FIELD.search("Contract address: value"))
        self.assertIsNotNone(TOKEN_FIELD.search("Mint：value"))

    def test_both_known_mints_are_guarded(self) -> None:
        self.assertEqual(len(KNOWN_MINTS), 2)
        self.assertTrue(all(mint.endswith("pump") for mint in KNOWN_MINTS))

    def test_repository_support_pages_are_contact_only(self) -> None:
        self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
