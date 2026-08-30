import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NavigationOpenApiTests(unittest.TestCase):
    def test_local_openapi_navigation_sources_exist(self) -> None:
        config = json.loads((ROOT / "docs.json").read_text())
        missing: list[str] = []

        def walk(value: object) -> None:
            if isinstance(value, dict):
                openapi = value.get("openapi")
                if isinstance(openapi, dict):
                    source = openapi.get("source")
                    if isinstance(source, str) and source.startswith("/openapi/"):
                        relative = source.split("#", 1)[0].lstrip("/")
                        if not (ROOT / relative).is_file():
                            missing.append(source)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(config)
        self.assertEqual(sorted(set(missing)), [])


if __name__ == "__main__":
    unittest.main()
