# Changelog

## 0.2.0 — 2026-07-27

- Added a source-access gate that selects methods supported or not prohibited by each information source.
- Added a machine-readable source policy covering OpenAlex, Crossref, arXiv, OpenReview, Semantic Scholar, Google Scholar, PubMed/NCBI, Europe PMC, GitHub, Reddit, Hacker News, publishers, institutions, news media, and technical blogs.
- Defined precise acquisition methods and removed ambiguous `manual`/`scraped` provenance.
- Restricted Playwright to public JavaScript-dependent pages whose current terms and robots policy permit automation.
- Explicitly prohibited Google Scholar and Reddit browser scraping as fallback behavior.
- Added policy provenance fields and updated the external-citation example.
- Added deterministic source-policy tests.

## 0.1.0 — 2026-07-27

- Added general OpenAlex works search and entity resolution.
- Added current API-key, cost, and rate-limit handling.
- Added cursor pagination with the current 100-result page limit.
- Added multi-identifier, multi-version target-paper resolution.
- Added incoming citation and outgoing reference retrieval.
- Added cross-source deduplication with provenance merging.
- Added correct-direction citation discrepancy audits.
- Added agent-facing `SKILL.md`, references, examples, tests, and CI.
