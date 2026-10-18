import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {
    "suno": "suno",
    "seedance": "seedance",
    "happyhorse": "happyHorse",
    "gpt-image": "gptImage",
    "nano-banana": "nanoBanana",
}


class NativeN8nGuideContractTests(unittest.TestCase):
    def test_task_examples_cannot_create_or_run_a_model(self):
        for slug, node_name in SERVICES.items():
            with self.subTest(service=slug):
                workflow = json.loads(
                    (ROOT / "examples" / "n8n" / f"read-{slug}-task.json").read_text()
                )
                self.assertFalse(workflow["active"])
                self.assertFalse(workflow.get("pinData"))
                self.assertEqual(len(workflow["nodes"]), 3)
                service_nodes = []
                for node in workflow["nodes"]:
                    self.assertNotIn("credentials", node)
                    if node["type"].startswith("@acedatacloud/"):
                        service_nodes.append(node)
                    else:
                        self.assertIn(
                            node["type"],
                            ["n8n-nodes-base.manualTrigger", "n8n-nodes-base.stickyNote"],
                        )
                self.assertEqual(len(service_nodes), 1)
                reader = service_nodes[0]
                self.assertEqual(
                    reader["type"],
                    f"@acedatacloud/n8n-nodes-{slug}.{node_name}",
                )
                self.assertEqual(reader["parameters"]["resource"], "task")
                self.assertEqual(reader["parameters"]["operation"], "get")
                self.assertIn("replace-with-your-existing-", reader["parameters"]["taskId"])
                self.assertFalse(reader["retryOnFail"])
                self.assertEqual(
                    workflow["connections"]["Start read-only lookup"]["main"][0][0]["node"],
                    reader["name"],
                )

    def test_both_languages_link_exact_example_and_explain_auth_boundary(self):
        navigation = (ROOT / "docs.json").read_text()
        for lang in ["en", "zh-Hans"]:
            overview = (ROOT / lang / "integrations" / "n8n.mdx").read_text()
            for slug in SERVICES:
                with self.subTest(language=lang, service=slug):
                    path = f"{lang}/integrations/n8n-{slug}"
                    self.assertIn(f'"{path}"', navigation)
                    self.assertIn(f"/{path}", overview)
                    guide = (ROOT / f"{path}.mdx").read_text()
                    self.assertIn(f"examples/n8n/read-{slug}-task.json", guide)
                    self.assertIn("API Token", guide)
                    self.assertIn("Initialize General Application", guide)
                    self.assertIn("Allowed APIs", guide)
                    self.assertIn("401 / 403", guide)
                    self.assertIn("Retry On Fail", guide)
                    self.assertIn("utm_source=opensource", guide)
                    self.assertIn("utm_medium=referral", guide)
                    self.assertIn("utm_campaign=evergreen", guide)
                    self.assertIn("utm_content=", guide)
                    self.assertIn("2026-10-18", guide)
                    self.assertIn("n8n-docs/4a84a4229f694c8565dcd0a9cd0af37623fa2cbc/", guide)
