import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_sync_from_platformbackend import sync


def record(key, source="# Source", content="# Translated", status="ready"):
    return {"source_key": key, "source_hash": sync.digest(source), "status": status,
            "content": content if status == "ready" else None,
            "content_hash": sync.digest(content) if status == "ready" else None}


def catalog(language="en", records=None):
    records = records or [record("development_codex")]
    return {"schema_version": 1, "source_language": "zh-cn", "language": language,
            "catalog_hash": "a" * 64, "public_api_ids": ["public-api"], "items": records}


class PublicationTests(unittest.TestCase):
    def test_existing_legacy_locale_pages_remain_in_the_reconciliation_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs.json").write_text(json.dumps({"navigation": {"languages": [{"language": "en"}]}}))
            (root / "el/guides").mkdir(parents=True)
            self.assertEqual(sync.get_docs_languages(root), ["en", "el"])

    def test_partial_reconciliation_publishes_ready_pages_but_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend, output, snapshots = root / "backend", root / "output", root / "catalogs"
            (backend / "docs").mkdir(parents=True)
            (backend / "cost").mkdir()
            (backend / "cost/service_api_mapping.json").write_text(json.dumps([{"alias": "codex", "apis": []}]))
            (backend / "docs/development_codex.md").write_text("# Source")
            snapshots.mkdir()
            output.mkdir()
            config = {"navigation": {"languages": [{"language": lang, "tabs": [
                {"tab": "Guides", "groups": [{"group": "Coding", "pages": []}]},
                {"tab": "MCP", "groups": [{"group": "MCP", "pages": []}]}]} for lang in ["zh-Hans", "en"]]}}
            (output / "docs.json").write_text(json.dumps(config))
            old = output / "en/guides/codex/codex.mdx"
            old.parent.mkdir(parents=True)
            old.write_text("# Previous")
            (snapshots / "zh-cn.json").write_text(json.dumps(catalog("zh-cn", [record("development_codex", content="# Source")])))
            (snapshots / "en.json").write_text(json.dumps(catalog("en", [record("development_codex", status="stale")])))
            argv = ["sync", "--backend-dir", str(backend), "--output-dir", str(output),
                    "--catalog-dir", str(snapshots), "--report", str(root / "report.json")]
            with patch("sys.argv", argv), patch.object(sync, "load_exact_doc_records", return_value={}), patch.dict(
                sync.os.environ, {"PUBLIC_EXAMPLE_DENYLIST": "identifier:test-id\nhost:test.invalid\nterm:test-private-term"}
            ):
                self.assertEqual(sync.main(), 2)
                self.assertEqual(old.read_text(), "# Previous")
                self.assertIn("# Source".removeprefix("# "), (output / "zh-Hans/guides/codex/codex.mdx").read_text())
                report = json.loads((root / "report.json").read_text())
                self.assertFalse(report["complete"])
                self.assertEqual(report["ready"], 1)
                (snapshots / "en.json").write_text(json.dumps(catalog()))
                self.assertEqual(sync.main(), 0)
                self.assertIn("Translated", old.read_text())
                first = {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()}
                self.assertEqual(sync.main(), 0)
                self.assertEqual(first, {str(p.relative_to(output)): p.read_bytes() for p in output.rglob("*") if p.is_file()})

    def test_catalog_accepts_text_and_mcp_without_api_siblings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = catalog(records=[record("development_codex"), record("mcp_seedance")])
            (root / "en.json").write_text(json.dumps(payload))
            actual = sync.load_publication_catalog("en", root)
            self.assertEqual(set(actual["records"]), {"development_codex", "mcp_seedance"})

    def test_catalog_rejects_wrong_locale_duplicate_identity_and_corrupt_content(self):
        payloads = [catalog("zh-cn"), catalog(records=[record("development_codex")] * 2), catalog()]
        payloads[-1]["items"][0]["content"] = "Tampered"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for payload in payloads:
                (root / "en.json").write_text(json.dumps(payload))
                with self.assertRaises(RuntimeError):
                    sync.load_publication_catalog("en", root)

    def test_catalog_change_during_locale_reads_aborts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            en, zh = catalog(), catalog("zh-cn")
            zh["items"][0]["source_hash"] = "b" * 64
            for language, payload in [("en", en), ("zh-cn", zh)]:
                (root / f"{language}.json").write_text(json.dumps(payload))
            with self.assertRaisesRegex(RuntimeError, "changed between"):
                sync.load_publication_catalogs(["en", "zh-Hans"], root)

    def test_routes_cover_standalone_mcp_exact_maps_and_publication_holds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            keys = ["development_codex", "development_sdk", "mcp_seedance", "development_kling_assets",
                    "development_oauth_apps", "x402_integration_guide", "development_flux_generate_video"]
            for key in keys:
                (root / "docs" / f"{key}.md").write_text("# Source")
            records = {key: record(key) for key in keys}
            routes, excluded = sync.publication_routes(root, {"records": records},
                {"flux_generate_video": "flux"}, {"codex": {"output_path": "guides/codex/exact.mdx"}})
            self.assertEqual(routes["development_codex"], Path("guides/codex/exact.mdx"))
            self.assertEqual(routes["development_sdk"], Path("guides/platform/sdk.mdx"))
            self.assertEqual(routes["mcp_seedance"], Path("mcp/seedance.mdx"))
            self.assertEqual(routes["development_flux_generate_video"], Path("guides/flux/flux_generate_video.mdx"))
            self.assertEqual(routes["development_oauth_apps"], Path("guides/oauth.mdx"))
            self.assertEqual(routes["x402_integration_guide"], Path("guides/x402.mdx"))
            self.assertEqual(excluded["development_kling_assets"], "publication_hold")

    def test_all_locales_receive_mcp_and_pending_pages_are_not_counted_as_current(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend, old, output = root / "backend", root / "old", root / "output"
            (backend / "docs").mkdir(parents=True)
            keys = ["mcp_seedance", "development_codex", "development_sdk", "development_new"]
            for key in keys:
                (backend / "docs" / f"{key}.md").write_text("# Source")
            routes = {"mcp_seedance": Path("mcp/seedance.mdx"), "development_codex": Path("guides/codex/codex.mdx"),
                      "development_sdk": Path("guides/platform/sdk.mdx"), "development_new": Path("guides/platform/new.mdx")}
            records = {key: record(key) for key in keys}
            records["development_codex"]["status"] = "stale"
            records["development_sdk"]["source_hash"] = sync.digest("# Previous source")
            records["development_new"]["status"] = "missing"
            for relative in ["en/guides/codex/codex.mdx", "en/mcp/overview.mdx", "en/mcp/seedance.mdx"]:
                path = old / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("previous")
            catalogs = {locale: {"records": copy.deepcopy(records)} for locale in sync.LANGUAGE_SOURCE_DIRS}
            results = sync.sync_document_pages(backend, output, old, catalogs, routes)
            for locale in sync.LANGUAGE_SOURCE_DIRS:
                self.assertIn("Translated", (output / locale / "mcp/seedance.mdx").read_text())
            self.assertEqual((output / "en/mcp/overview.mdx").read_text(), "previous")
            self.assertEqual((output / "en/guides/codex/codex.mdx").read_text(), "previous")
            en = {row["source_key"]: row for row in results if row["language"] == "en"}
            self.assertEqual(en["development_codex"]["status"], "stale")
            self.assertTrue(en["development_codex"]["retained_previous"])
            self.assertEqual(en["development_sdk"]["status"], "source_not_deployed")
            self.assertEqual(en["development_new"]["status"], "missing")
            self.assertFalse((output / "en/guides/platform/new.mdx").exists())

    def test_navigation_exposes_new_translations_and_removes_retired_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {"navigation": {"languages": [{"language": "en", "tabs": [
                {"tab": "Guides", "groups": [{"group": "Coding", "pages": []},
                  {"group": "Getting Started", "pages": ["en/quickstart", "en/guides/retired/old"]}]},
                {"tab": "MCP Servers", "groups": [{"group": "MCP", "pages": ["en/mcp/sora"]}]},
                {"tab": "API Reference", "groups": [{"group": "Retired", "openapi": {"source": "/openapi/retired.json"}}]}]}]}}
            (root / "docs.json").write_text(json.dumps(config))
            (root / "openapi").mkdir()
            (root / "openapi/live.json").write_text(json.dumps({"info": {"title": "Live"}}))
            for path in ["en/guides/codex/desktop.mdx", "en/guides/platform/sdk.mdx", "en/mcp/seedance.mdx", "en/mcp/overview.mdx"]:
                file = root / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("body")
            exact = {"codex_desktop": {"output_path": "guides/codex/desktop.mdx"}}
            sync.refresh_generated_navigation(root, ["en"], exact)
            once = (root / "docs.json").read_text()
            sync.refresh_generated_navigation(root, ["en"], exact)
            self.assertEqual(once, (root / "docs.json").read_text())
            self.assertIn("en/quickstart", once)
            self.assertIn("en/guides/codex/desktop", once)
            self.assertIn("en/guides/platform/sdk", once)
            self.assertIn("en/mcp/overview", once)
            self.assertNotIn("en/mcp/sora", once)
            self.assertNotIn("en/guides/retired/old", once)
            self.assertNotIn("/openapi/retired.json", once)
            self.assertIn("/openapi/live.json", once)

    def test_transaction_can_restore_navigation_and_every_mcp_locale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, stage = root / "old", root / "stage"
            for base, content in [(old, "before"), (stage, "after")]:
                (base / "en/mcp").mkdir(parents=True)
                (base / "en/mcp/seedance.mdx").write_text(content)
                (base / "docs.json").write_text(content)
            real_replace = sync.os.replace

            def interrupt(source, target):
                if Path(source) == stage / "en/mcp":
                    raise KeyboardInterrupt
                return real_replace(source, target)

            with patch.object(sync.os, "replace", side_effect=interrupt), self.assertRaises(KeyboardInterrupt):
                sync.publish_generated_tree(stage, old, [Path("docs.json"), Path("en/mcp")])
            self.assertEqual((old / "docs.json").read_text(), "before")
            self.assertEqual((old / "en/mcp/seedance.mdx").read_text(), "before")

    def test_missing_public_openapi_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "Missing public OpenAPI"):
                sync.merge_openapi_specs(Path(directory), {"alias": "test", "apis": [{"id": "missing"}]})
