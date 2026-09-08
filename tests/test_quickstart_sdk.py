from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from check_quickstart_sdk import SDK_URL, main  # noqa: E402


class QuickstartSdkTest(unittest.TestCase):
    def test_sdk_campaign_is_stable(self) -> None:
        self.assertEqual(
            SDK_URL,
            "https://github.com/AceDataCloud/SDK?utm_source=docs&utm_medium=quickstart&utm_campaign=docs-sdk",
        )

    def test_sdk_target_is_the_canonical_repository(self) -> None:
        self.assertTrue(SDK_URL.startswith("https://github.com/AceDataCloud/SDK?"))

    def test_repository_quickstarts_link_the_sdks(self) -> None:
        self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
