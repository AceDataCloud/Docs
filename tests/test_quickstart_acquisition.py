from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from check_quickstart_acquisition import (  # noqa: E402
    ACQUISITION_URL,
    main,
    quickstart_navigation_paths,
)


class QuickstartAcquisitionTest(unittest.TestCase):
    def test_campaign_is_stable(self) -> None:
        self.assertEqual(
            ACQUISITION_URL,
            "https://platform.acedata.cloud/?utm_source=docs&utm_medium=quickstart&utm_campaign=docs-quickstart",
        )

    def test_navigation_path_extraction(self) -> None:
        self.assertEqual(
            quickstart_navigation_paths({"pages": ["en/quickstart", "en/introduction"]}),
            {"en/quickstart"},
        )

    def test_repository_quickstarts_are_attributed(self) -> None:
        self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
