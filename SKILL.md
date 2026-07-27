---
name: paper-search-openalex
description: Search, resolve, filter, group, and audit scholarly records with the current OpenAlex API. Use for literature discovery, author/institution/source resolution, bibliographic metadata, references, related works, and multi-version citing-works retrieval.
---

# Paper Search with OpenAlex

## Purpose

Use this skill when a task requires structured scholarly search or bibliometric relationships through OpenAlex. It supports:

- topical literature searches
- recent-paper searches with date, OA, type, author, institution, source, and topic filters
- DOI, arXiv, PMID, and OpenAlex work lookup
- author, institution, source, topic, publisher, funder, and keyword resolution
- incoming citations (`citing works`)
- outgoing citations (`references`)
- multi-version resolution across preprint, conference, and journal records
- citation-edge discrepancy audits
- grouping and lightweight bibliometric summaries

Do not use OpenAlex as the sole source for breaking news, product facts, legal or medical decisions, or claims about current organizations. For those tasks, combine it with current official documents and appropriate external sources.

## Current API assumptions

The live API behavior changes over time. As of 2026-07-27:

- `OPENALEX_API_KEY` is required.
- A free key includes a daily usage allowance.
- list endpoints allow `per_page=100`.
- basic paging stops at 10,000 results; use cursor pagination beyond that.
- the API reports cost metadata in `meta.cost_usd` and exposes `/rate-limit`.

Before changing API behavior in this repository, check `references/openalex-current-api.md` and the current OpenAlex developer documentation.

## Setup

```bash
export OPENALEX_API_KEY="..."
python3 paper_search_openalex.py rate-limit
```

Install as a CLI when desired:

```bash
python3 -m pip install -e .
paper-search-openalex rate-limit
```

Never commit an API key. Pass it through `OPENALEX_API_KEY` or `--api-key`.

## Default workflow

### 1. Clarify the scholarly question

Translate the request into:

- search concepts and synonyms
- date range
- work type
- open-access requirement
- named authors, institutions, journals, or topics
- desired ranking: relevance, recency, or citation count
- whether the user needs discovery, exhaustive retrieval, or bibliometric comparison

### 2. Resolve named entities before filtering

Do not filter by ambiguous names when an entity ID exists.

```bash
python3 paper_search_openalex.py entity authors "Geoffrey Hinton"
python3 paper_search_openalex.py entity institutions "University of Tokyo"
python3 paper_search_openalex.py entity sources "Journal of Chemical Physics"
python3 paper_search_openalex.py entity topics "machine learning interatomic potentials"
```

Inspect the returned metadata and choose the correct OpenAlex ID. Then use that ID in a work filter.

### 3. Search broadly, then narrow

Start with a conceptually complete query. Add filters only when they reflect the user's actual constraints.

```bash
python3 paper_search_openalex.py search \
  "graph neural networks molecular excited states" \
  --filter 'publication_year=>2024' \
  --filter 'type=article' \
  --sort=-publication_date \
  --limit 100
```

Common filters:

- `publication_year=2024-2026`
- `from_publication_date=2025-01-01`
- `type=article|preprint`
- `open_access.is_oa=true`
- `authorships.author.id=A...`
- `authorships.institutions.id=I...`
- `primary_location.source.id=S...`
- `topics.id=T...`
- `cited_by_count=>100`

Use `references/query-recipes.md` for patterns.

### 4. Inspect and rank results

Do not equate citation count with quality. For recent work, citations are strongly time-dependent. Consider:

- title and abstract relevance
- publication date
- work type and venue
- author and institution identity
- open-access location
- citation count normalized by age when appropriate
- whether multiple records represent versions of the same work

When reporting results, include DOI or OpenAlex ID, title, year, venue, authors, and why the paper is relevant.

### 5. Retrieve citations through all known versions

A target paper can have separate preprint, conference, and journal OpenAlex records. Resolve the complete target identity before retrieving citations.

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

The resolver always performs title search even after finding multiple DOI records. It validates title, author, year, and known URLs, then retrieves citations from every resolved Work ID and deduplicates the union.

For outgoing references, replace `citing` with `references`.

### 6. Treat external citation records as target-identity evidence

A citation found in Google Scholar, Semantic Scholar, Crossref, or manual PDF review does not identify which OpenAlex version it cites unless an actual OpenAlex citation edge exists.

External records must therefore use:

```json
{
  "cites_target_identity": true,
  "cites_target_work_ids": [],
  "target_version_resolution": "unresolved"
}
```

Never assign all target Work IDs to a manually observed citation.

### 7. Audit citation discrepancies in the correct direction

To explain why an externally verified citation is absent from OpenAlex, inspect the citing paper, not the target paper.

```bash
python3 paper_search_openalex.py audit-citations \
  --target-json examples/target-paper.json \
  --external-json examples/external-citations.json
```

For each citing paper, determine:

1. whether it exists in OpenAlex
2. whether its `referenced_works` list is present
3. whether a resolved target Work ID is in that list
4. whether the source PDF or HTML independently verifies the reference

Possible diagnoses:

- `citation_edge_present`
- `citing_work_not_in_openalex`
- `citing_work_reference_list_missing`
- `reference_present_but_unresolved`
- `citation_edge_absent_unverified`

See `references/citation-audit.md`.

## Cross-source use

OpenAlex is the primary structured source for this skill. Supplement it when needed:

- official publisher pages and Crossref for DOI and publication metadata
- arXiv and OpenReview for preprint/conference identities
- Semantic Scholar for an independent citation graph
- Google Scholar for high-recall manual audits, not automated scraping
- PubMed, Europe PMC, ADS, INSPIRE, or domain databases where field coverage matters
- GitHub and technical blogs for code, datasets, and implementation status
- Reddit or Hacker News only as anecdotal evidence about workflows or indexing behavior

Keep source-specific counts separate. Report the deduplicated union only after entity resolution, and preserve `retrieval_sources` for every work.

## Quality rules

- Prefer current OpenAlex developer documentation over archived examples.
- Normalize DOI, arXiv, and OpenAlex IDs before comparison.
- Use cursor pagination for more than 10,000 results.
- Use `select` in custom code to reduce response size.
- Implement exponential backoff for 429 and transient 5xx errors.
- Preserve cost and rate-limit metadata.
- Do not claim exhaustiveness when external indexes disagree.
- Do not interpret `cited_by_count=0` as proof of no real citations.
- Do not infer citation-edge failure from the target paper's own reference count.
- Distinguish publication versions from genuinely different papers.
- Preserve evidence URLs and reference text during manual audits.

## Output expectations

For literature searches, summarize:

1. search scope and filters
2. strongest matching papers
3. recent versus foundational work
4. notable gaps or coverage limitations
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
