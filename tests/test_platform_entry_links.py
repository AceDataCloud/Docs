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
                    links = re.findall(r'(?<=\]\()[^)]+|(?<=href=")[^"]+', text)
                    self.assertTrue(links)
                    for link in links:
                        parsed = urlparse(link)
                        if parsed.netloc == "raw.githubusercontent.com":
                            self.assertTrue(link.startswith(IMAGE_ROOT))
                            continue
                        self.assertEqual(parsed.netloc, "platform.acedata.cloud", link)
                        self.assertEqual(parse_qs(parsed.query).get("lang"), [locale], link)

    def test_key_instructions_show_copy_and_create_screens_at_the_relevant_steps(self):
        for language in ("en", "zh-Hans"):
            authentication = (ROOT / language / "authentication.mdx").read_text()
            self.assertIn(IMAGE_ROOT + "get-api-key-en.png", authentication)
            self.assertIn(IMAGE_ROOT + "create-api-key-en.png", authentication)
            self.assertLess(authentication.index("get-api-key-en.png"), authentication.index("create-api-key-en.png"))
            quickstart = (ROOT / language / "quickstart.mdx").read_text()
            self.assertIn(IMAGE_ROOT + "get-api-key-en.png", quickstart)
            self.assertLess(quickstart.index("get-api-key-en.png"), quickstart.index("export ACEDATACLOUD_API_KEY"))
            self.assertIn("platform.acedata.cloud/documents/api-key-guide?lang=", quickstart)


if __name__ == "__main__":
    unittest.main()
