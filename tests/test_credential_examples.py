import unittest
from scripts.sync_from_platformbackend import convert_markdown_to_mdx, sanitize_example_credentials

class CredentialExamplesTests(unittest.TestCase):
    def test_generator_replaces_literal_bearer_and_keeps_placeholder(self):
        token = "ab" * 16
        result = convert_markdown_to_mdx("# Guide\n\n```sh\nAuthorization: Bearer " + token + "\n```", "Guide")
        self.assertNotIn(token, result)
        self.assertIn("Bearer YOUR_API_TOKEN", result)
        self.assertEqual(sanitize_example_credentials("Bearer YOUR_API_TOKEN"), "Bearer YOUR_API_TOKEN")

