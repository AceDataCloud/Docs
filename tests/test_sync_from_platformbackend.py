import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "sync_from_platformbackend.py"
SPEC = importlib.util.spec_from_file_location("sync_from_platformbackend", SCRIPT_PATH)
assert SPEC and SPEC.loader
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class SyncFromPlatformBackendTests(unittest.TestCase):
    def test_build_doc_service_map_reads_flattened_docs_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            backend_dir = Path(temporary_directory)
            docs_dir = backend_dir / "docs"
            docs_dir.mkdir()
            (docs_dir / "development_gemini_videos.md").write_text("# Gemini", encoding="utf-8")

            services = [
                {
                    "alias": "gemini",
                    "apis": [{"path": "/gemini/videos"}],
                }
            ]

            self.assertEqual(sync.build_doc_service_map(services, backend_dir), {"gemini_videos": "gemini"})

    def test_index_localized_guides_maps_alias_and_api_path(self) -> None:
        payload = {
            "items": [
                {
                    "alias": "gemini-videos",
                    "api": {"path": "/gemini/videos"},
                    "sibling": {
                        "alias": "gemini-videos-integration",
                        "title": "Gemini Video API Integration Guide",
                        "content": "# Gemini Video\n\nLocalized body",
                    },
                }
            ]
        }

        guides = sync.index_localized_guides(payload, "en")

        self.assertEqual(guides["geminivideos"]["title"], "Gemini Video API Integration Guide")
        self.assertIn("Localized body", guides["geminivideos"]["content"])

    def test_index_localized_guides_rejects_empty_feed(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "No localized guides"):
            sync.index_localized_guides({"items": []}, "en")

    def test_index_localized_guides_rejects_collisions(self) -> None:
        payload = {
            "items": [
                {"alias": "same-key", "sibling": {"title": "One", "content": "One"}},
                {"alias": "same_key", "sibling": {"title": "Two", "content": "Two"}},
            ]
        }

        with self.assertRaisesRegex(RuntimeError, "Conflicting localized guide key"):
            sync.index_localized_guides(payload, "en")

    def test_index_localized_guides_does_not_overwrite_alias_with_shared_api_path(self) -> None:
        payload = {
            "items": [
                {
                    "alias": "fish-model",
                    "api": {"path": "/fish/model"},
                    "sibling": {"title": "Fish Model", "content": "Model"},
                },
                {
                    "alias": "fish-model-query",
                    "api": {"path": "/fish/model"},
                    "sibling": {"title": "Fish Model Query", "content": "Query"},
                },
            ]
        }

        guides = sync.index_localized_guides(payload, "en")

        self.assertEqual(guides["fishmodel"]["content"], "Model")
        self.assertEqual(guides["fishmodelquery"]["content"], "Query")

    def test_guide_description_uses_output_language(self) -> None:
        self.assertEqual(sync.guide_description("zh-Hans", "Gemini"), "Gemini 集成指南 - Ace Data Cloud")
        self.assertEqual(sync.guide_description("en", "Gemini"), "Gemini integration guide - Ace Data Cloud")
        self.assertEqual(sync.guide_description("ja", "Gemini"), "Gemini API guide - Ace Data Cloud")


if __name__ == "__main__":
    unittest.main()
