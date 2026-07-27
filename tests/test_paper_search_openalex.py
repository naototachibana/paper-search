import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paper_search_openalex import (
    CitationAuditor,
    CitationRetriever,
    OpenAlexAuthenticationError,
    OpenAlexClient,
    TargetPaper,
    TargetResolver,
    deduplicate_works,
    extract_arxiv_id,
    extract_doi,
    normalize_arxiv_id,
    normalize_doi,
    normalize_openalex_id,
    normalize_title,
    parse_filter_values,
    records_match,
    title_similarity,
)


class FakeResponse:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class SequenceOpener:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []

    def __call__(self, request, timeout=30):
        self.requests.append(request.full_url)
        item = self.payloads.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item, {"X-RateLimit-Remaining": "42"})


class FakeClient:
    def __init__(self):
        self.get_map = {}
        self.search_results = []
        self.citing_map = {}
        self.reference_map = {}
        self.search_calls = 0

    def get_work(self, identifier, select=None):
        return self.get_map.get(identifier) or self.get_map.get(normalize_openalex_id(identifier)) or self.get_map.get(normalize_doi(identifier))

    def search_works(self, query, limit=25, filters=None, sort=None, select=None):
        self.search_calls += 1
        return list(self.search_results)

    def citing_works(self, work_id, limit=None):
        return list(self.citing_map.get(normalize_openalex_id(work_id), []))

    def referenced_works(self, work_id, limit=None):
        return list(self.reference_map.get(normalize_openalex_id(work_id), []))


class NormalizationTests(unittest.TestCase):
    def test_doi_normalization(self):
        self.assertEqual(normalize_doi("https://DOI.org/10.1000/ABC."), "10.1000/abc")
        self.assertEqual(extract_doi("See doi:10.1234/Test_Value."), "10.1234/test_value")

    def test_arxiv_normalization(self):
        self.assertEqual(normalize_arxiv_id("https://arxiv.org/pdf/2311.01135v2.pdf"), "2311.01135")
        self.assertEqual(extract_arxiv_id("arXiv:hep-th/9901001v3"), "hep-th/9901001")

    def test_openalex_id_normalization(self):
        self.assertEqual(normalize_openalex_id("https://openalex.org/w123"), "W123")

    def test_title_unicode(self):
        self.assertEqual(normalize_title("∇²DFT: A_Test"), "2dft a test")
        self.assertGreater(title_similarity("Generating QM1B with PySCF_IPU", "Generating QM1B with PySCF IPU"), 0.9)


class DeduplicationTests(unittest.TestCase):
    def test_same_doi_different_format(self):
        works = deduplicate_works([
            {"doi": "https://doi.org/10.1/ABC", "title": "Paper", "retrieval_sources": ["openalex"]},
            {"doi": "10.1/abc", "title": "Paper", "retrieval_sources": ["semantic_scholar"]},
        ])
        self.assertEqual(len(works), 1)
        self.assertEqual(set(works[0]["retrieval_sources"]), {"openalex", "semantic_scholar"})

    def test_same_title_different_version_doi(self):
        works = deduplicate_works([
            {"doi": "10.1/preprint", "title": "A Long Exact Scholarly Paper Title", "year": 2023, "authors": ["Jane Smith"]},
            {"doi": "10.1/final", "title": "A Long Exact Scholarly Paper Title", "year": 2024, "authors": ["J. Smith"]},
        ])
        self.assertEqual(len(works), 1)

    def test_same_title_different_author_not_merged(self):
        left = {"title": "A Long Exact Scholarly Paper Title", "year": 2024, "authors": ["Jane Smith"]}
        right = {"title": "A Long Exact Scholarly Paper Title", "year": 2024, "authors": ["John Jones"]}
        self.assertFalse(records_match(left, right))

    def test_target_ids_are_merged_only_when_present(self):
        works = deduplicate_works([
            {"doi": "10.1/a", "title": "A Long Exact Scholarly Paper Title", "year": 2024, "authors": ["A Smith"], "cites_target_work_ids": ["W1"]},
            {"doi": "10.1/a", "title": "A Long Exact Scholarly Paper Title", "year": 2024, "authors": ["A Smith"], "cites_target_work_ids": [], "cites_target_identity": True},
        ])
        self.assertEqual(works[0]["cites_target_work_ids"], ["W1"])
        self.assertTrue(works[0]["cites_target_identity"])


class ClientTests(unittest.TestCase):
    def test_key_required(self):
        old = os.environ.pop("OPENALEX_API_KEY", None)
        try:
            with self.assertRaises(OpenAlexAuthenticationError):
                OpenAlexClient(api_key="")
        finally:
            if old:
                os.environ["OPENALEX_API_KEY"] = old

    def test_url_has_api_key_and_current_page_limit(self):
        opener = SequenceOpener([{"meta": {}, "results": []}])
        client = OpenAlexClient(api_key="secret", opener=opener)
        client.list_entities("works", search="quantum", per_page=100)
        self.assertIn("api_key=secret", opener.requests[0])
        self.assertIn("per_page=100", opener.requests[0])
        self.assertEqual(client.last_rate_headers["X-RateLimit-Remaining"], "42")
        with self.assertRaises(ValueError):
            client.list_entities("works", per_page=101)

    def test_cursor_pagination(self):
        opener = SequenceOpener([
            {"meta": {"next_cursor": "next"}, "results": [{"id": "W1"}, {"id": "W2"}]},
            {"meta": {"next_cursor": None}, "results": [{"id": "W3"}]},
        ])
        client = OpenAlexClient(api_key="secret", opener=opener)
        self.assertEqual([w["id"] for w in client.iter_entities("works")], ["W1", "W2", "W3"])
        self.assertIn("cursor=%2A", opener.requests[0])
        self.assertIn("cursor=next", opener.requests[1])

    def test_filters(self):
        self.assertEqual(parse_filter_values(["publication_year=>2024", "open_access.is_oa=true"]), {
            "publication_year": ">2024", "open_access.is_oa": "true"
        })
        with self.assertRaises(ValueError):
            parse_filter_values(["broken"])


class ResolverTests(unittest.TestCase):
    def make_work(self, wid, doi, title="Generating QM1B with PySCF IPU", year=2023):
        return {
            "id": f"https://openalex.org/{wid}",
            "doi": f"https://doi.org/{doi}",
            "title": title,
            "publication_year": year,
            "type": "article",
            "authorships": [{"author": {"display_name": "Alexander Mathiasen"}}],
            "locations": [],
        }

    def test_resolver_always_title_searches_after_two_dois(self):
        client = FakeClient()
        client.get_map["10.1/a"] = self.make_work("W1", "10.1/a")
        client.get_map["10.1/b"] = self.make_work("W2", "10.1/b")
        client.search_results = [self.make_work("W3", "10.1/c")]
        target = TargetPaper(title="Generating QM1B with PySCF IPU", authors=["Mathiasen, A."], year=2023, dois=["10.1/a", "10.1/b"])
        resolved = TargetResolver(client).resolve(target)
        self.assertEqual({r["openalex_id"] for r in resolved}, {"W1", "W2", "W3"})
        self.assertEqual(client.search_calls, 1)

    def test_bad_doi_metadata_gets_warning(self):
        client = FakeClient()
        client.get_map["10.1/wrong"] = self.make_work("W9", "10.1/wrong", title="Completely Different Article", year=2010)
        target = TargetPaper(title="Generating QM1B with PySCF IPU", authors=["Mathiasen"], year=2023, dois=["10.1/wrong"])
        resolved = TargetResolver(client).resolve(target)
        self.assertTrue(resolved[0]["validation_warnings"])
        self.assertNotEqual(resolved[0]["confidence"], "high")


class CitationTests(unittest.TestCase):
    def test_multi_version_union_and_external_unresolved(self):
        client = FakeClient()
        shared = {"id": "https://openalex.org/W9", "doi": "https://doi.org/10.9/x", "title": "A Long Shared Citing Paper", "publication_year": 2025, "authorships": [{"author": {"display_name": "Jane Smith"}}]}
        client.citing_map = {"W1": [shared], "W2": [shared]}
        result = CitationRetriever(client).retrieve(["W1", "W2"], external_records=[{
            "doi": "10.9/x", "title": "A Long Shared Citing Paper", "year": 2025, "authors": ["J. Smith"], "source": "google_scholar_manual"
        }])
        self.assertEqual(result["openalex_raw_count"], 2)
        self.assertEqual(result["union_after_deduplication"], 1)
        work = result["works"][0]
        self.assertEqual(set(work["cites_target_work_ids"]), {"W1", "W2"})
        self.assertEqual(set(work["retrieval_sources"]), {"openalex", "google_scholar_manual"})

    def test_external_only_does_not_claim_specific_target_version(self):
        result = CitationRetriever(FakeClient()).retrieve(["W1", "W2"], external_records=[{
            "title": "A Long External Citing Paper", "year": 2025, "authors": ["Jane Smith"], "source": "manual"
        }])
        self.assertEqual(result["works"][0]["cites_target_work_ids"], [])
        self.assertEqual(result["works"][0]["target_version_resolution"], "unresolved")

    def test_auditor_checks_citing_work_reference_list(self):
        client = FakeClient()
        client.get_map["10.9/citing"] = {
            "id": "https://openalex.org/W9",
            "title": "A Long Verified Citing Paper",
            "referenced_works": ["https://openalex.org/W1"],
            "referenced_works_count": 4,
        }
        audits = CitationAuditor(client).audit(["W1", "W2"], [{"doi": "10.9/citing", "title": "A Long Verified Citing Paper"}])
        self.assertEqual(audits[0]["diagnosis"], "citation_edge_present")
        self.assertEqual(audits[0]["evidence"]["linked_target_work_ids"], ["W1"])

    def test_auditor_reports_unresolved_reference(self):
        client = FakeClient()
        client.get_map["10.9/citing"] = {
            "id": "https://openalex.org/W9",
            "title": "A Long Verified Citing Paper",
            "referenced_works": ["https://openalex.org/W99"],
            "referenced_works_count": 10,
        }
        audits = CitationAuditor(client).audit(["W1"], [{
            "doi": "10.9/citing", "title": "A Long Verified Citing Paper", "source_reference_verified": True,
            "reference_text": "Mathiasen et al. Generating QM1B..."
        }])
        self.assertEqual(audits[0]["diagnosis"], "reference_present_but_unresolved")


if __name__ == "__main__":
    unittest.main()
