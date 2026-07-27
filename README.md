# paper-search

A general-purpose scholarly search and citation-audit skill. OpenAlex is the primary structured index, while other sources are accessed only through methods they officially support or do not prohibit.

## Design principle

The source and the acquisition method are separate facts.

```json
{
  "source": "crossref",
  "acquisition_method": "official_api"
}
```

```json
{
  "source": "google_scholar",
  "acquisition_method": "human_observed"
}
```

Playwright is not treated as “manual.” Browser automation is permitted only for a public page when no supported API/feed covers the needed fact, current terms and robots policy do not prohibit automation, JavaScript is genuinely required, and no access control is bypassed.

See:

- [`SKILL.md`](SKILL.md)
- [`references/source-access-policy.md`](references/source-access-policy.md)
- [`references/source-access-policy.json`](references/source-access-policy.json)

## Features

- current OpenAlex API-key, budget, and rate-limit handling
- work search with filters, sorting, grouping, and cursor paging
- author, institution, source, topic, publisher, funder, and keyword search
- lookup by DOI or OpenAlex ID
- multi-identifier and multi-version target resolution
- incoming citations and outgoing references across all resolved versions
- cross-source entity resolution and provenance merging
- citation discrepancy audits in the correct direction
- source-access policy for API, feed, bulk, connector, web, browser, document, and human-supplied evidence
- deterministic unit tests and CI

## Source-access model

| Source | Preferred method | Automated fallback | Prohibited or restricted fallback |
|---|---|---|---|
| OpenAlex | Official REST API or snapshot | User/local import | Unauthenticated API use, limit evasion |
| Crossref | Official REST API, polite pool | User/local import | Scraping publisher HTML for Crossref metadata |
| arXiv | API, RSS, OAI-PMH, bulk | Document inspection | HTML scraping as primary interface; unlicensed redistribution |
| OpenReview | API 2 or required legacy API | Narrow permitted web fetch | Access-control bypass |
| Semantic Scholar | Official API or datasets | User/local import | Website scraping; rate-limit evasion |
| Google Scholar | Human-observed or user-supplied | Search discovery only | Playwright, scraping, CAPTCHA bypass |
| PubMed/NCBI | E-utilities or bulk | Document inspection | HTML scraping as API substitute |
| Europe PMC | REST/SOAP/OAI/FTP/bulk | Document inspection | HTML scraping as API substitute |
| GitHub | Connector or REST/GraphQL API | Narrow public page fetch | Credential exposure or limit evasion |
| Reddit | Approved Data API with OAuth | Human-observed or user-supplied | HTML scraping or Playwright fallback |
| Hacker News | Official Firebase API | Narrow permitted page fetch | HTML scraping as primary source |
| Publishers, institutions, news, blogs | API/feed first, then permitted web | Permitted browser automation when required | Paywall/login/CAPTCHA bypass; broad crawling |

The detailed policy is machine-readable. It includes aliases for The Verge, Tom's Hardware, Wired, Ars Technica, TechCrunch, Engadget, CNET, ZDNet, MIT Technology Review, Gizmodo, and technical blogs. These sites are checked at execution time because their terms and robots policies can change.

## Required provenance

External evidence should record:

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

Allowed method values:

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

Do not use ambiguous provenance such as `manual`, `browser`, or `scraped`.

## Current OpenAlex compatibility

The implementation targets the OpenAlex API documented in July 2026:

- API key required
- free daily API allowance
- `per_page` maximum of 100
- up to 100 OR values per filter
- basic paging limited to 10,000 results
- cursor paging for larger result sets
- `/rate-limit` endpoint and `meta.cost_usd`

See [`references/openalex-current-api.md`](references/openalex-current-api.md).

## Setup

```bash
export OPENALEX_API_KEY="your-free-key"
python3 paper_search_openalex.py rate-limit
```

Optional editable installation:

```bash
python3 -m pip install -e .
paper-search rate-limit
```

The legacy `paper-search-openalex` console command remains as a compatibility alias.

## Examples

### Search papers

```bash
paper-search search \
  "spin-flip TDDFT spin contamination" \
  --filter 'publication_year=2022-2026' \
  --sort=-publication_date \
  --limit 50
```

### Resolve an institution

```bash
paper-search entity institutions "Toyohashi University of Technology"
```

### Get one paper

```bash
paper-search get-work 10.1038/sdata.2014.22
```

### Find papers citing all target versions

```bash
paper-search citing \
  --title "Generating QM1B with PySCF IPU" \
  --author "Mathiasen, A." \
  --year 2023 \
  --doi 10.48550/arXiv.2311.01135 \
  --doi 10.52202/075280-2402 \
  --arxiv 2311.01135
```

### Retrieve outgoing references

```bash
paper-search references \
  --doi 10.1038/sdata.2014.22 \
  --title "Quantum chemistry structures and properties of 134 kilo molecules" \
  --year 2014
```

### Audit citation discrepancies

```bash
paper-search audit-citations \
  --target-json examples/target-paper.json \
  --external-json examples/external-citations.json
```

## Citation model

The target is an identity set rather than one DOI:

```text
DOIs + arXiv IDs + OpenReview IDs + URLs + title/authors/year
                              ↓
                    resolved OpenAlex Work IDs
                              ↓
          citing works for each ID or references from each ID
                              ↓
       cross-version and cross-source entity resolution + provenance
```

An externally observed citation is attached to the target identity. It is not assigned to a particular OpenAlex Work ID unless an actual OpenAlex citation edge proves that relationship.

## Project layout

```text
.
├── SKILL.md
├── paper_search_openalex.py
├── references/
│   ├── openalex-current-api.md
│   ├── query-recipes.md
│   ├── citation-audit.md
│   ├── source-access-policy.md
│   └── source-access-policy.json
├── examples/
│   ├── target-paper.json
│   └── external-citations.json
├── tests/
│   ├── test_paper_search_openalex.py
│   └── test_source_access_policy.py
├── pyproject.toml
└── .github/workflows/tests.yml
```

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile paper_search_openalex.py
```

The policy tests verify that every source has an access class, preferred methods, authority records where applicable, and explicit restrictions for high-risk sources such as Google Scholar and Reddit.

## License

MIT
