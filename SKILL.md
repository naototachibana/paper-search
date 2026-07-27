---
name: paper-search
description: Search, resolve, filter, group, and audit scholarly records. Use source-approved acquisition methods, with OpenAlex as the primary structured index and official APIs, feeds, bulk services, connectors, or explicitly permitted web access for complementary evidence.
---

# Paper Search

## Purpose

Use this skill for structured scholarly discovery, bibliographic verification, citation retrieval, citation-graph auditing, and supporting evidence about research software or recent technical developments.

OpenAlex is the primary automated scholarly index, not the sole source of truth. Every source must be accessed through a method that the source expressly supports or, for public web pages, does not prohibit.

Supported tasks include:

- topical and recent-paper searches
- DOI, arXiv, PMID, and OpenAlex work lookup
- author, institution, source, topic, publisher, funder, and keyword resolution
- incoming citations and outgoing references
- multi-version resolution across preprint, conference, and journal records
- citation-edge discrepancy audits
- grouping and lightweight bibliometric summaries
- verification against official publication records, source documents, code repositories, and recent technical reporting

Do not use scholarly indexes as the sole source for breaking news, product facts, legal or medical decisions, or current organizational claims. Combine them with current official documents and suitable external sources.

## Mandatory source-access gate

Before retrieving information from any source:

1. Identify the exact source and host.
2. Read `references/source-access-policy.json` and `references/source-access-policy.md`.
3. Prefer, in order:
   - official API
   - official bulk or OAI interface
   - official RSS, Atom, or JSON feed
   - authorized connector
   - permitted web fetch
   - permitted browser automation
   - document inspection
   - user-supplied or human-observed evidence
4. Do not replace unavailable credentials, approval, quota, or API coverage with scraping.
5. Before `permitted_web_fetch` or `permitted_browser_automation`, check the current terms and `robots.txt` for the exact host.
6. If either explicitly prohibits the intended automation, or the position is unclear, do not automate that source.
7. Never bypass authentication, paywalls, CAPTCHAs, geographic restrictions, rate limits, or other technical controls.
8. Record the information source and acquisition method separately.

Browser automation is not “manual.” Playwright is allowed only when:

- the page is public;
- no official API, feed, bulk interface, or connector covers the needed fact;
- the source's current terms and robots policy do not prohibit automation;
- JavaScript rendering or interaction is genuinely required;
- no login, paywall, CAPTCHA, or access control is bypassed;
- access is narrow rather than a bulk crawl.

## Acquisition-method vocabulary

Use one of these values in provenance:

- `official_api`
- `official_bulk_download`
- `official_feed`
- `connector`
- `permitted_web_fetch`
- `permitted_browser_automation`
- `document_inspection`
- `user_supplied`
- `human_observed`
- `local_file_import`
- `search_engine_discovery`

Do not use ambiguous values such as `manual`, `browser`, or `scraped`.

External evidence should contain:

```json
{
  "source": "google_scholar",
  "acquisition_method": "human_observed",
  "observed_at": "2026-07-27",
  "evidence_url": "https://scholar.google.com/...",
  "policy_checked_at": "2026-07-27",
  "policy_basis_urls": [
    "https://scholar.google.com/intl/us/scholar/help.html"
  ]
}
```

## Source-specific acquisition rules

The machine-readable policy is authoritative for this repository. The following is a working summary.

### OpenAlex

Use the checked-in Python client and official REST API for:

- work and entity search
- filters, sorting, grouping, and cursor pagination
- DOI/OpenAlex lookup
- incoming citations through `cites:`
- outgoing references
- rate-limit and cost metadata

Use an API key, `per_page<=100`, cursor pagination for deep result sets, response field selection, caching, and backoff.

### Crossref

Use the official REST API rather than scraping publisher pages for Crossref metadata. Use the polite pool with a valid `mailto` and identifying `User-Agent`, cache responses, observe rate/concurrency headers, and back off.

Use Crossref to verify DOI, title, authors, venue, dates, article type, relations, and version-of-record metadata.

### arXiv

Use the official API, RSS, OAI-PMH, or documented bulk access. For the legacy API family, use no more than one request every three seconds and a single connection. Cache queries and prefer OAI-PMH or bulk access for large harvesting.

Descriptive metadata is reusable under CC0. Full text remains subject to the submission's license; do not redistribute PDFs or source files without permission.

### OpenReview

Use API 2 by default and legacy API v1 only where a venue still requires it. Respect `readers`, `nonreaders`, `writers`, authentication, and venue access controls. Do not scrape around API permissions or access private reviews.

### Semantic Scholar

Use the official Academic Graph API or documented datasets. Use an API key when available, batch endpoints for larger operations, obey rate limits, and provide required attribution.

Before use, confirm that the current API or dataset license permits the intended research, educational, commercial, retention, redistribution, and public-display behavior. Do not scrape the Semantic Scholar website or fabricate an OpenAlex ID from a DOI.

### Google Scholar

Do not scrape or automate Google Scholar with Playwright. Google Scholar explicitly asks automated software to respect its robots policy and offers no official public bulk API for this workflow.

Allowed evidence paths are:

- `human_observed`
- `user_supplied`
- discovery through a search engine, followed by verification against the original paper or publisher

Record the observation date. Treat citation counts and version clusters as mutable leads rather than authoritative records.

### PubMed and NCBI

Use NCBI E-utilities or documented bulk resources. Include `tool` and `email`. Stay at or below three requests per second without an API key and ten requests per second by default with a key. Follow NCBI guidance for very large jobs.

### Europe PMC

Use REST, SOAP, OAI, FTP, or documented bulk services. Do not scrape the HTML interface as a substitute. Check the license of each full-text article, figure, or supplement before reuse or redistribution.

### GitHub

Prefer the installed GitHub connector or the official REST/GraphQL APIs. Use authenticated access where appropriate, honor primary and secondary limits, `Retry-After`, and reset headers.

Use a public page fetch only for a small number of human-readable pages when API or connector coverage is insufficient.

### Reddit

Use the Reddit Data API only with required registration, OAuth identity, approved use case, attribution, rate-limit compliance, and retention/deletion compliance.

Do not use Playwright or HTML scraping as a fallback when API approval or credentials are unavailable. For isolated anecdotal evidence, use `user_supplied` or `human_observed` permalinks.

### Hacker News

Use the official read-only Firebase API for stories, comments, users, and rankings. Do not scrape the HTML interface as the primary data source. Cache responses and avoid unnecessary recursive traversal.

### Publisher pages, official institutions, news media, and technical blogs

Prefer official APIs, data portals, citation exports, RSS/Atom/JSON feeds, sitemaps intended for indexing, downloadable reports, or open repositories.

For public HTML:

1. check current terms and robots policy;
2. use a narrow `permitted_web_fetch` when allowed;
3. use Playwright only when JavaScript is required and automation is not prohibited;
4. do not bypass login, paywall, CAPTCHA, or reader restrictions;
5. do not perform broad crawling without explicit permission.

This rule covers publishers, universities, government and research-institute sites, The Verge, Tom's Hardware, Wired, Ars Technica, TechCrunch, Engadget, CNET, ZDNet, MIT Technology Review, Gizmodo, company engineering blogs, and similar sources. Because their policies change, permission must be checked at execution time rather than assumed from this file.

Use media and community sources for reporting, implementation status, and practitioner experience. Verify scientific claims against papers or official documents.

## Current OpenAlex assumptions

As of 2026-07-27:

- `OPENALEX_API_KEY` is required.
- A free key includes a daily usage allowance.
- list endpoints allow `per_page=100`.
- basic paging stops at 10,000 results; use cursor pagination beyond that.
- the API reports cost metadata in `meta.cost_usd` and exposes `/rate-limit`.

Before changing API behavior, check `references/openalex-current-api.md` and current OpenAlex documentation.

## Setup

```bash
export OPENALEX_API_KEY="..."
python3 paper_search_openalex.py rate-limit
```

Install the generic CLI when desired:

```bash
python3 -m pip install -e .
paper-search rate-limit
```

`paper-search-openalex` remains as a compatibility alias. Never commit API keys.

## Default scholarly workflow

### 1. Define the question

Translate the request into:

- concepts and synonyms
- date range
- work type
- open-access requirement
- named authors, institutions, journals, or topics
- ranking by relevance, recency, or citation count
- discovery versus exhaustive retrieval versus bibliometric comparison

### 2. Resolve named entities

Do not filter by ambiguous names when a stable entity ID exists.

```bash
paper-search entity authors "Geoffrey Hinton"
paper-search entity institutions "University of Tokyo"
paper-search entity sources "Journal of Chemical Physics"
paper-search entity topics "machine learning interatomic potentials"
```

Inspect the metadata, select the correct OpenAlex ID, and use it in work filters.

### 3. Search broadly, then narrow

```bash
paper-search search \
  "graph neural networks molecular excited states" \
  --filter 'publication_year=>2024' \
  --filter 'type=article' \
  --sort=-publication_date \
  --limit 100
```

### 4. Inspect and rank

Do not equate citation count with quality. Consider title and abstract relevance, date, work type, venue, author identity, institution, OA location, age, and duplicate versions.

### 5. Retrieve citations through all versions

```bash
paper-search citing \
  --title "Generating QM1B with PySCF IPU" \
  --author "Mathiasen, A." \
  --year 2023 \
  --doi 10.48550/arXiv.2311.01135 \
  --doi 10.52202/075280-2402 \
  --arxiv 2311.01135 \
  --openreview 9Z1cmO7S7o
```

The resolver searches by title even after finding multiple DOI records, validates title/author/year/URLs, retrieves citations from every resolved Work ID, and deduplicates the union.

For outgoing references, use `references`.

### 6. Treat external citations as identity-level evidence

A citation found outside OpenAlex does not identify which OpenAlex version it cites unless an actual OpenAlex edge exists.

```json
{
  "source": "google_scholar",
  "acquisition_method": "human_observed",
  "cites_target_identity": true,
  "cites_target_work_ids": [],
  "target_version_resolution": "unresolved"
}
```

Never assign every target Work ID to an externally observed citation.

### 7. Audit citation discrepancies in the correct direction

Inspect the citing paper, not the target paper.

```bash
paper-search audit-citations \
  --target-json examples/target-paper.json \
  --external-json examples/external-citations.json
```

Determine:

1. whether the citing work exists in OpenAlex;
2. whether its `referenced_works` list exists;
3. whether a resolved target Work ID is present;
4. whether the source PDF or HTML independently verifies the reference.

Possible diagnoses:

- `citation_edge_present`
- `citing_work_not_in_openalex`
- `citing_work_reference_list_missing`
- `reference_present_but_unresolved`
- `citation_edge_absent_unverified`

## Cross-source and quality rules

- Preserve source-specific counts.
- Keep `source` separate from `acquisition_method`.
- Deduplicate only after identifier, title, year, and author resolution.
- Merge provenance rather than discarding duplicate evidence.
- Never claim exhaustiveness when indexes disagree.
- Prefer current official documentation over community recollection.
- Preserve evidence URLs, observation dates, policy-check dates, and reference text.
- Normalize DOI, arXiv, and OpenAlex IDs.
- Use cursor pagination for large OpenAlex result sets.
- Implement backoff for 429 and transient 5xx responses.
- Do not interpret `cited_by_count=0` as proof of no real citations.
- Do not infer incoming citation failure from the target paper's own reference count.
- Distinguish publication versions from genuinely different papers.
- Recheck source policies before recurring or high-volume acquisition.

## Output expectations

For literature searches, report:

1. scope and filters
2. strongest matching papers
3. recent versus foundational work
4. source and acquisition method
5. gaps and coverage limitations
6. stable identifiers and links

For citation retrieval, report:

1. resolved target versions
2. per-version OpenAlex counts
3. raw OpenAlex total
4. deduplicated union
5. source-specific counts
6. acquisition methods
7. unresolved external citations
8. audit diagnoses and evidence

## Repository checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile paper_search_openalex.py
```
