import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "references" / "source-access-policy.json"


class SourceAccessPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_policy_has_version_and_review_date(self):
        self.assertEqual(self.policy["schema_version"], "1.0")
        self.assertRegex(self.policy["last_reviewed"], r"^\d{4}-\d{2}-\d{2}$")

    def test_method_vocabulary_is_explicit(self):
        methods = self.policy["method_definitions"]
        for required in (
            "official_api",
            "official_bulk_download",
            "official_feed",
            "connector",
            "permitted_web_fetch",
            "permitted_browser_automation",
            "document_inspection",
            "user_supplied",
            "human_observed",
            "local_file_import",
            "search_engine_discovery",
        ):
            self.assertIn(required, methods)
        self.assertNotIn("manual", methods)
        self.assertNotIn("scraped", methods)

    def test_every_source_has_access_decision(self):
        known_methods = set(self.policy["method_definitions"])
        for name, source in self.policy["sources"].items():
            with self.subTest(source=name):
                self.assertIn(source["access_class"], {
                    "allowed_automated",
                    "allowed_automated_conditional",
                    "conditional_web",
                    "human_only",
                })
                self.assertTrue(source["preferred_methods"])
                self.assertTrue(set(source["preferred_methods"]).issubset(known_methods))
                self.assertTrue(set(source.get("fallback_methods", [])).issubset(known_methods))
                self.assertTrue(source.get("conditions"))
                self.assertIn("prohibited_methods", source)

    def test_google_scholar_is_not_automated(self):
        source = self.policy["sources"]["google_scholar"]
        self.assertEqual(source["access_class"], "human_only")
        self.assertEqual(source["preferred_methods"], ["human_observed", "user_supplied"])
        self.assertIn("browser_automation", source["prohibited_methods"])
        self.assertIn("web_scraping", source["prohibited_methods"])

    def test_reddit_does_not_fallback_to_scraping(self):
        source = self.policy["sources"]["reddit"]
        self.assertEqual(source["preferred_methods"], ["official_api"])
        self.assertIn("human_observed", source["fallback_methods"])
        self.assertIn("web_scraping", source["prohibited_methods"])
        self.assertIn("browser_automation", source["prohibited_methods"])

    def test_hacker_news_uses_official_api(self):
        source = self.policy["sources"]["hacker_news"]
        self.assertEqual(source["preferred_methods"][0], "official_api")
        self.assertTrue(any("HackerNews/API" in url for url in source["authority_urls"]))

    def test_arxiv_rate_rule_is_recorded(self):
        conditions = " ".join(self.policy["sources"]["arxiv"]["conditions"]).lower()
        self.assertIn("three seconds", conditions)
        self.assertIn("one connection", conditions)

    def test_conditional_web_requires_live_policy_check(self):
        globals_text = " ".join(self.policy["global_rules"]).lower()
        self.assertIn("terms and robots.txt", globals_text)
        for name in ("publisher_pages", "official_research_institutions", "news_and_technical_media", "generic_public_web"):
            with self.subTest(source=name):
                source = self.policy["sources"][name]
                self.assertEqual(source["access_class"], "conditional_web")
                self.assertIn("permitted_web_fetch", source["preferred_methods"])


if __name__ == "__main__":
    unittest.main()
