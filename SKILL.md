---
name: paper-search
description: Search, resolve, filter, group, and audit scholarly records. Use OpenAlex as the primary structured index and validate or supplement results with publisher metadata, Crossref, arXiv, OpenReview, Semantic Scholar, domain databases, GitHub, and manual source inspection when needed.
---

# Paper Search

## Purpose

Use this skill when a task requires structured scholarly discovery, bibliographic verification, citation retrieval, or citation-graph auditing. OpenAlex is the primary automated backend, not the sole source of truth.

Supported tasks include:

- topical and recent-paper searches
- DOI, arXiv, PMID, and OpenAlex work lookup
- author, institution, source, topic, publisher, funder, and keyword resolution
- incoming citations and outgoing references
- multi-version resolution across preprint, conference, and journal records
- citation-edge discrepancy audits
- grouping and lightweight bibliometric summaries
- validation against official publication records and complementary indexes

Do not use scholarly indexes as the sole source for breaking news, product facts, legal or medical decisions, or current organizational claims. Combine them with current official documents and suitable external sources.

## Source architecture

### OpenAlex

Use the checked-in Python client and OpenAlex REST API for automated structured operations:

- paper and entity search
- filters, sorting, grouping, and cursor pagination
- DOI/OpenAlex lookup
- incoming citation retrieval through `cites:`
- outgoing references through `referenced_works`
- rate-limit and cost metadata

### Crossref and publisher records

Use Crossref or the publisher's official landing page to validate DOI, title, authors, venue, dates, article type, and version-of-record status. The current CLI does not silently query Crossref; use a future provider adapter or agent web/API access and preserve the source in provenance.

### arXiv and OpenReview

Use identifiers and official pages to resolve preprint and conference versions. The current OpenAlex resolver accepts arXiv IDs, OpenReview IDs, and URLs as target identity evidence. A direct arXiv/OpenReview adapter may be added later.

### Semantic Scholar

Use as an independent citation graph when OpenAlex coverage is incomplete. Import results as external records or add a provider adapter. Do not invent an OpenAlex Work ID from a Semantic Scholar DOI; resolve it through OpenAlex first.

### Google Scholar

Use only for manual, high-recall audits. Do not automate scraping. Record titles, stable identifiers, evidence URLs, and the date of observation. Treat version clusters and citation counts as mutable.

### Domain databases

Use PubMed or Europe PMC for biomedical literature, ADS for astronomy, INSPIRE for high-energy physics, and other field-specific indexes when their coverage is materially better. Keep their counts separate until entity resolution is complete.

### GitHub, technical blogs, and official project pages

Use GitHub and technical blogs to verify code, dataset releases, implementation state, benchmarks, and maintainer statements. They are evidence about software and practice, not substitutes for bibliographic metadata.

### Reddit and Hacker News

Use only as anecdotal evidence about indexing failures, user workflows, or community experience. Do not use them to establish API behavior or scholarly facts when official sources exist.

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

## Default workflow

### 1. Define the scholarly question

Translate the request into:

- concepts and synonyms
- date range
- work type
- open-access requirement
- named authors, institutions, journals, or topics
- ranking by relevance, recency, or citation count
- discovery versus exhaustive retrieval versus bibliometric comparison

### 2. Resolve named entities before filtering

Do not filter by ambiguous names when a stable entity ID exists.

```bash
python3 paper_search_openalex.py entity authors "Geoffrey Hinton"
python3 paper_search_openalex.py entity institutions "University of Tokyo"
python3 paper_search_openalex.py entity sources "Journal of Chemical Physics"
python3 paper_search_openalex.py entity topics "machine learning interatomic potentials"
```

Inspect the metadata, select the correct OpenAlex ID, and use it in work filters.

### 3. Search broadly, then narrow

```bash
python3 paper_search_openalex.py search \
  "graph neural networks molecular excited states" \
  --filter 'publication_year=>2024' \
  --filter 'type=article' \
  --sort=-publication_date \
  --limit 100
```

Common filters include:

- `publication_year=2024-2026`
- `from_publication_date=2025-01-01`
- `type=article|preprint`
- `open_access.is_oa=true`
- `authorships.author.id=A...`
- `authorships.institutions.id=I...`
- `primary_location.source.id=S...`
- `topics.id=T...`
- `cited_by_count=>100`

### 4. Inspect and rank results

Do not equate citation count with quality. Consider title and abstract relevance, date, work type, venue, author identity, institution, OA location, age of the paper, and duplicate versions.

When reporting results, include stable identifiers, title, year, venue, authors, relevance, and material coverage limitations.

### 5. Retrieve citations through all known versions

A target can have separate preprint, conference, and journal OpenAlex records. Resolve the complete identity first.

```bash
python3 paper_search_openalex.py citing \
  --title "Generating QM1B with PySCF IPU" \
  --author "Mathiasen, A." \
  --year 2023 \
  --doi 10.48550/arXiv.2311.01135 \
  --doi 10.52202/075280-2402 \
  --arxiv 2311.01135 \
  --openreview 9Z1cmO7S7o
```

The resolver performs title search even after finding multiple DOI records. It validates title, author, year, and known URLs, retrieves citations from every resolved Work ID, and deduplicates the union.

For outgoing references, replace `citing` with `references`.

### 6. Treat external citations as identity-level evidence

A citation found outside OpenAlex does not identify which OpenAlex version it cites unless an actual OpenAlex edge exists.

Use:

```json
{
  "cites_target_identity": true,
  "cites_target_work_ids": [],
  "target_version_resolution": "unresolved"
}
```

Never assign every target Work ID to a manually observed citation.

### 7. Audit citation discrepancies in the correct direction

Inspect the citing paper, not the target paper.

```bash
python3 paper_search_openalex.py audit-citations \
  --target-json examples/target-paper.json \
  --external-json examples/external-citations.json
```

For each citing paper, determine:

1. whether it exists in OpenAlex
2. whether its `referenced_works` list exists
3. whether a resolved target Work ID is present
4. whether the source PDF or HTML independently verifies the reference

Possible diagnoses:

- `citation_edge_present`
- `citing_work_not_in_openalex`
- `citing_work_reference_list_missing`
- `reference_present_but_unresolved`
- `citation_edge_absent_unverified`

## Cross-source rules

- Preserve source-specific counts.
- Deduplicate only after DOI, arXiv ID, OpenAlex ID, title, year, and author resolution.
- Merge `retrieval_sources` rather than discarding duplicate evidence.
- Never claim exhaustiveness when indexes disagree.
- Prefer official API documentation over community recollection.
- Use publisher pages and source documents for consequential verification.
- Preserve evidence URLs and reference text during manual audits.

## Quality rules

- Normalize DOI, arXiv, and OpenAlex IDs.
- Use cursor pagination for large OpenAlex result sets.
- Use `select` to reduce response size in custom code.
- Implement exponential backoff for 429 and transient 5xx responses.
- Preserve rate-limit and cost metadata.
- Do not interpret `cited_by_count=0` as proof of no real citations.
- Do not infer incoming citation failure from the target paper's own reference count.
- Distinguish publication versions from genuinely different papers.

## Output expectations

For literature searches, report:

1. scope and filters
2. strongest matching papers
3. recent versus foundational work
4. gaps and coverage limitations
5. stable identifiers and links

For citation retrieval, report:

1. resolved target versions
2. per-version OpenAlex counts
3. raw OpenAlex total
4. deduplicated union
5. source-specific counts
6. unresolved external citations
7. audit diagnoses and evidence

## Repository checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile paper_search_openalex.py
```
