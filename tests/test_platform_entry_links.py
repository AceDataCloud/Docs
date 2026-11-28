import json
import re
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("authentication", "quickstart", "introduction", "services", "concepts/async-tasks")
IMAGE_ROOT = "https://raw.githubusercontent.com/AceDataCloud/NanoBananaDify/2522b2f57210597af2db866445319334a1677a23/_assets/tutorial/"


class PlatformEntryLinksTests(unittest.TestCase):
    def test_entry_pages_send_readers_to_localized_platform_pages(self):
        for language, locale in (("en", "en"), ("zh-Hans", "zh-cn")):
            for name in PAGES:
                with self.subTest(language=language, page=name):
                    text = (ROOT / language / f"{name}.mdx").read_text()
                    self.assertNotIn("create-api-key", text)
                    links = re.findall(r'(?<=\]\()[^)]+|(?<=href=")[^"]+', text)
                    self.assertTrue(links)
                    for link in links:
                        parsed = urlparse(link)
                        if link == "https://cdn.acedata.cloud/dvc3cg.jpg":
                            continue
                        if parsed.netloc == "raw.githubusercontent.com":
                            self.assertTrue(link.startswith(IMAGE_ROOT))
                            continue
                        self.assertEqual(parsed.netloc, "platform.acedata.cloud", link)
                        self.assertEqual(parse_qs(parsed.query).get("lang"), [locale], link)

    def test_key_instructions_keep_only_the_copy_screen_before_the_request(self):
        for language in ("en", "zh-Hans"):
            authentication = (ROOT / language / "authentication.mdx").read_text()
            self.assertIn("platform.acedata.cloud/console/applications?", authentication)
            self.assertIn(IMAGE_ROOT + "get-api-key-en.png", authentication)
            self.assertNotIn("create-api-key", authentication)
            quickstart = (ROOT / language / "quickstart.mdx").read_text()
            self.assertIn("platform.acedata.cloud/console/applications?", quickstart)
            self.assertIn(IMAGE_ROOT + "get-api-key-en.png", quickstart)
            self.assertLess(quickstart.index("get-api-key-en.png"), quickstart.index("export ACEDATACLOUD_API_KEY"))

    def test_each_chat_first_request_has_a_response_json(self):
        for language in ("en", "zh-Hans"):
            for name in ("quickstart", "authentication"):
                with self.subTest(language=language, page=name):
                    text = (ROOT / language / f"{name}.mdx").read_text()
                    self.assertIn("platform.acedata.cloud/documents/openai-chat-completions-integration?", text)
                    request_end = text.index("```", text.index("curl --fail-with-body"))
                    response = re.search(r"```json\n(.*?)\n```", text[request_end:], re.S)
                    self.assertIsNotNone(response)
                    payload = json.loads(response.group(1))
                    self.assertEqual(payload["object"], "chat.completion")
                    self.assertEqual(payload["model"], "gpt-6-luna")
                    self.assertTrue(payload["choices"][0]["message"]["content"])
                    self.assertEqual(payload["choices"][0]["finish_reason"], "stop")

    def test_async_example_shows_submission_pending_and_complete_results(self):
        for language in ("en", "zh-Hans"):
            text = (ROOT / language / "concepts/async-tasks.mdx").read_text()
            self.assertIn("platform.acedata.cloud/documents/acemusic-audios-integration?", text)
            self.assertIn("platform.acedata.cloud/documents/acemusic-tasks-integration?", text)
            examples = [json.loads(value) for value in re.findall(r"```json\n(.*?)\n```", text, re.S)]
            submitted, pending, completed = examples[:3]
            self.assertEqual(submitted["status"], "created")
            self.assertEqual(submitted["task_id"], pending["id"])
            self.assertEqual(pending["id"], completed["id"])
            self.assertEqual(pending["state"], "processing")
            self.assertIsNone(pending["finished_at"])
            self.assertFalse(pending["response"]["success"])
            self.assertEqual(completed["state"], "succeeded")
            self.assertTrue(completed["response"]["success"])
            tracks = completed["response"]["data"]
            self.assertEqual(len(tracks), 2)
            self.assertEqual(len({track["id"] for track in tracks}), 2)
            self.assertTrue(all(track["state"] == "succeeded" and track["audio_url"] for track in tracks))


if __name__ == "__main__":
    unittest.main()
