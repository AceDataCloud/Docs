import importlib.util
import json
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

    def test_exact_records_override_heuristic_service_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            backend = root / "backend"
            docs = backend / "docs"
            docs.mkdir(parents=True)
            (docs / "development_tool_route.md").write_text("# Tool", encoding="utf-8")
            records = [
                {
                    "canonical_alias": "tool-route",
                    "source_doc_key": "development_tool_route",
                    "service_alias": "coding",
                    "output_path": "guides/coding/custom_name.mdx",
                }
            ]
            bundle = {
                "schema_version": 1,
                "records_sha256": sync.hashlib.sha256(sync.canonical_json_bytes(records)).hexdigest(),
                "records": records,
            }
            bundle_path = root / "exact.json"
            bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
            services = [{"alias": "coding", "apis": []}, {"alias": "tool", "apis": []}]

            exact = sync.load_exact_doc_records(backend, services, bundle_path)
            mapping = sync.build_doc_service_map(services, backend, exact)

            self.assertEqual(mapping["tool_route"], "coding")
            self.assertEqual(exact["tool_route"]["output_path"], "guides/coding/custom_name.mdx")

    def test_sync_guides_writes_exact_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            backend = root / "backend"
            output = root / "output"
            docs = backend / "docs"
            docs.mkdir(parents=True)
            (docs / "development_tool_route.md").write_text("# Exact tool\n\nBody", encoding="utf-8")
            exact = {
                "tool_route": {
                    "source_doc_key": "development_tool_route",
                    "service_alias": "coding",
                    "output_path": "guides/coding/exact_name.mdx",
                    "canonical_alias": "tool-route",
                }
            }

            sync.sync_guides(
                backend,
                output,
                {"coding": {"alias": "coding", "display_name": "Coding"}},
                {"tool_route": "coding"},
                ["zh-Hans"],
                exact_records=exact,
            )

            self.assertTrue((output / "zh-Hans/guides/coding/exact_name.mdx").is_file())
            self.assertFalse((output / "zh-Hans/guides/coding/tool_route.mdx").exists())

    def test_exact_records_fail_closed_on_invalid_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            backend = root / "backend"
            docs = backend / "docs"
            docs.mkdir(parents=True)
            (docs / "development_route.md").write_text("# Route", encoding="utf-8")
            services = [{"alias": "coding", "apis": []}]
            base = {
                "canonical_alias": "route",
                "source_doc_key": "development_route",
                "service_alias": "coding",
                "output_path": "guides/coding/route.mdx",
            }

            for label, mutate, error in (
                ("digest", lambda rows: rows, "digest mismatch"),
                ("service", lambda rows: [{**rows[0], "service_alias": "missing"}], "Unknown"),
                ("source", lambda rows: [{**rows[0], "source_doc_key": "development_missing"}], "Missing"),
                ("traversal", lambda rows: [{**rows[0], "output_path": "guides/coding/../route.mdx"}], "Unsafe"),
                ("duplicate", lambda rows: rows + [dict(rows[0])], "Duplicate"),
            ):
                rows = mutate([dict(base)])
                digest = "invalid" if label == "digest" else sync.hashlib.sha256(sync.canonical_json_bytes(rows)).hexdigest()
                path = root / f"{label}.json"
                path.write_text(json.dumps({"schema_version": 1, "records_sha256": digest, "records": rows}), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, error):
                    sync.load_exact_doc_records(backend, services, path)

    def test_coding_nav_manifest_covers_all_locales_and_preserves_urls(self) -> None:
        root = Path(__file__).parents[1]
        nav = json.loads((root / "scripts/data/coding-nav.generated.json").read_text(encoding="utf-8"))
        docs_json = json.loads((root / "docs.json").read_text(encoding="utf-8"))
        self.assertEqual(len(nav["locales"]), 15)
        self.assertEqual(len(nav["routes"]), 25)
        self.assertTrue(all(set(route["paths"]) == set(nav["locales"]) for route in nav["routes"]))
        raw_nav = json.dumps(docs_json)
        stable = {
            "claude_code",
            "claude_code_terminal",
            "claude_code_vscode",
            "claude_code_jetbrains",
            "claude_code_github_actions",
        }
        for locale in nav["locales"]:
            for name in stable:
                self.assertIn(f"{locale}/guides/claude-code/{name}", raw_nav)

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

    def test_response_blocks_include_commonmark_containers(self) -> None:
        content = (
            "Response:\n> ```json\n> {\"error\":\"restricted source\"}\n> ```\n"
            "Result:\n- ~~~yaml\n  error: restricted source\n  ~~~\n"
        )
        blocks = sync.response_blocks(content)
        self.assertEqual(len(blocks), 2)
        self.assertTrue(all("restricted source" in block for block in blocks))

    def test_structured_response_artifacts_are_sanitized_deterministically(self) -> None:
        content = (
            "Response:\n```json\n"
            '{"image_url":"https://media.invalid/a.png","video_urls":["https://media.invalid/a.mp4","https://media.invalid/b.mp4"]}'
            "\n```\n"
        )
        result = sync.neutralize_response_terms(content, ())
        self.assertIn("e724d7f13d.png?example=image-001", result)
        self.assertIn("04a043bd-6b23-4b4e-945c-ce48158c3eee.mp4?example=video-001", result)
        self.assertIn("04a043bd-6b23-4b4e-945c-ce48158c3eee.mp4?example=video-002", result)
        self.assertEqual(sync.neutralize_response_terms(content, (), sanitize_artifacts=False), content)

    def test_neutralize_terms_only_in_response_fence(self) -> None:
        content = (
            "Background restricted source.\n"
            "Request:\n```json\n{\"note\":\"restricted source\"}\n```\n"
            "Response:\n```json\n{\"error\":\"restricted source\"}\n```\n"
        )
        result = sync.neutralize_response_terms(content, ("restricted source",))
        self.assertEqual(result.count("restricted source"), 2)
        self.assertIn("model service", result)

    def test_validate_generated_tree_detects_nested_and_overencoded_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested = root / "en" / "guides"
            nested.mkdir(parents=True)
            target = nested / "guide.mdx"
            target.write_text("private%252Droute", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, r"en/guides/guide\.mdx \[identifier\]") as raised:
                sync.validate_generated_tree(root, (("private-route",), (), ()))
            self.assertNotIn("private-route", str(raised.exception))

            target.write_text("private%2525252Droute", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, r"en/guides/guide\.mdx \[undecodable\]"):
                sync.validate_generated_tree(root, (("private-route",), (), ()))

    def test_validate_generated_tree_reports_categories_without_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            target = root / "openapi" / "service.json"
            target.parent.mkdir(parents=True)
            target.write_text('{"description":"restricted source","url":"https://private.invalid/a"}', encoding="utf-8")

            with self.assertRaises(RuntimeError) as raised:
                sync.validate_generated_tree(root, ((), ("private.invalid",), ("restricted source",)))

            message = str(raised.exception)
            self.assertIn("openapi/service.json [host,term]", message)
            self.assertNotIn("private.invalid", message)
            self.assertNotIn("restricted source", message)

    def test_openapi_artifact_validation_only_checks_responses(self) -> None:
        request_only = {
            "paths": {
                "/items": {
                    "post": {
                        "requestBody": {"content": {"application/json": {"example": {"product_url": "https://input.example/item"}}}},
                        "responses": {"200": {"content": {"application/json": {"example": {"video_url": "https://platform2.cdn.acedata.cloud/video.mp4"}}}}},
                    }
                }
            }
        }
        self.assertFalse(sync.invalid_openapi_response_artifact_urls(request_only))

        request_only["paths"]["/items"]["post"]["responses"]["200"]["content"]["application/json"]["example"]["video_url"] = "https://media.invalid/video.mp4"
        self.assertTrue(sync.invalid_openapi_response_artifact_urls(request_only))

    def test_managed_paths_only_owns_generated_mcp_locale(self) -> None:
        paths = sync.managed_paths(["zh-Hans", "en"])
        self.assertIn(Path("zh-Hans/mcp"), paths)
        self.assertNotIn(Path("en/mcp"), paths)

    def test_clear_managed_paths_removes_stale_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            stale = root / "en" / "guides" / "stale.mdx"
            stale.parent.mkdir(parents=True)
            stale.write_text("stale", encoding="utf-8")

            sync.clear_managed_paths(root, [Path("en/guides")])

            self.assertFalse(stale.exists())

    def test_publish_cleans_manifest_and_backup_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"
            staging = root / "staging"
            for base, value in ((output, "old"), (staging, "new")):
                path = base / "openapi"
                path.mkdir(parents=True)
                (path / "value.txt").write_text(value, encoding="utf-8")

            sync.publish_generated_tree(staging, output, [Path("openapi")])

            manifest, backup = sync.transaction_paths(output)
            self.assertEqual((output / "openapi/value.txt").read_text(), "new")
            self.assertFalse(manifest.exists())
            self.assertFalse(backup.exists())

    def test_baseexception_mid_publish_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"
            staging = root / "staging"
            managed = [Path("openapi"), Path("en/guides")]
            for base, value in ((output, "old"), (staging, "new")):
                for relative in managed:
                    path = base / relative
                    path.mkdir(parents=True)
                    (path / "value.txt").write_text(value, encoding="utf-8")
            original_replace = sync.os.replace
            staged_swaps = 0

            def interrupting_replace(source, target):
                nonlocal staged_swaps
                if Path(source).is_relative_to(staging):
                    staged_swaps += 1
                    if staged_swaps == 2:
                        raise KeyboardInterrupt()
                return original_replace(source, target)

            sync.os.replace = interrupting_replace
            self.addCleanup(setattr, sync.os, "replace", original_replace)
            with self.assertRaises(KeyboardInterrupt):
                sync.publish_generated_tree(staging, output, managed)

            for relative in managed:
                self.assertEqual((output / relative / "value.txt").read_text(), "old")

    def test_next_run_recovers_unfinished_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"
            target = output / "openapi"
            target.mkdir(parents=True)
            (target / "value.txt").write_text("new", encoding="utf-8")
            manifest_path, backup_root = sync.transaction_paths(output)
            backup = backup_root / "openapi"
            backup.mkdir(parents=True)
            (backup / "value.txt").write_text("old", encoding="utf-8")
            sync.atomic_write_json(
                manifest_path,
                {"phase": "publishing", "items": [{"relative": "openapi", "had_target": True, "state": "published"}]},
            )

            sync.restore_transaction(output)

            self.assertEqual((target / "value.txt").read_text(), "old")
            self.assertFalse(manifest_path.exists())
            self.assertFalse(backup_root.exists())

    def test_orphan_empty_backup_is_cleaned_on_next_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"
            output.mkdir()
            _manifest, backup = sync.transaction_paths(output)
            backup.mkdir()
            sync.restore_transaction(output)
            self.assertFalse(backup.exists())

    def test_orphan_nonempty_backup_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"
            output.mkdir()
            _manifest, backup = sync.transaction_paths(output)
            backup.mkdir()
            (backup / "evidence").write_text("old", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                sync.restore_transaction(output)
            self.assertTrue(backup.exists())

    def test_invalid_manifest_path_and_state_fail_closed(self) -> None:
        for item in (
            {"relative": "../outside", "had_target": True, "state": "published"},
            {"relative": "openapi", "had_target": True, "state": "unknown"},
        ):
            with self.assertRaises(RuntimeError):
                sync.validate_manifest({"phase": "publishing", "items": [item]})

    def test_restoring_state_completes_after_backup_rename_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"
            target = output / "openapi"
            target.mkdir(parents=True)
            (target / "value.txt").write_text("old", encoding="utf-8")
            manifest, backup = sync.transaction_paths(output)
            backup.mkdir()
            sync.atomic_write_json(
                manifest,
                {"phase": "publishing", "items": [{"relative": "openapi", "had_target": True, "state": "restoring"}]},
            )
            sync.restore_transaction(output)
            self.assertEqual((target / "value.txt").read_text(), "old")
            self.assertFalse(manifest.exists())

    def test_published_state_without_backup_never_accepts_current_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"
            target = output / "openapi"
            target.mkdir(parents=True)
            (target / "value.txt").write_text("new", encoding="utf-8")
            manifest, backup = sync.transaction_paths(output)
            backup.mkdir()
            sync.atomic_write_json(
                manifest,
                {"phase": "publishing", "items": [{"relative": "openapi", "had_target": True, "state": "published"}]},
            )
            with self.assertRaises(RuntimeError):
                sync.restore_transaction(output)
            self.assertTrue(manifest.exists())
            self.assertEqual((target / "value.txt").read_text(), "new")

    def test_incomplete_recovery_keeps_manifest_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"
            output.mkdir()
            manifest_path, backup_root = sync.transaction_paths(output)
            backup_root.mkdir()
            sync.atomic_write_json(
                manifest_path,
                {"phase": "publishing", "items": [{"relative": "openapi", "had_target": True, "state": "published"}]},
            )

            with self.assertRaises(RuntimeError):
                sync.restore_transaction(output)

            self.assertTrue(manifest_path.exists())
            self.assertTrue(backup_root.exists())


if __name__ == "__main__":
    unittest.main()
