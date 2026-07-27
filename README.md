# paper-search

A general-purpose scholarly search and citation-audit skill. OpenAlex is the primary structured index, while publisher metadata and complementary scholarly sources are used for identity resolution, coverage checks, and evidence-backed citation audits.

## Why this repository exists

A reliable paper-search workflow needs more than `GET /works?search=...`:

- named authors, institutions, journals, and topics must be resolved to stable IDs
- recent and foundational papers require different ranking strategies
- preprint, conference, and journal versions can be separate records
- citations can be split across those versions
- Google Scholar, Semantic Scholar, Crossref, and OpenAlex can disagree
- a missing citation edge must be diagnosed from the citing paper's reference list

This repository generalizes the earlier `openalex-citation-retrieval` work. Citing-works retrieval is one feature inside a broader paper-search skill.

## Features

- current OpenAlex API-key and usage-budget handling
- work search with arbitrary filters, sorting, grouping, and cursor paging
- author, institution, source, topic, publisher, funder, and keyword search
- lookup by DOI or OpenAlex ID
- multi-identifier target resolution
- incoming citations and outgoing references across every resolved version
- cross-source entity resolution and provenance merging
- citation discrepancy audits
- rate-limit and cost metadata capture
- standard-library-only runtime
- deterministic unit tests

## Source model

The checked-in CLI currently automates OpenAlex. Other sources are used through explicit adapters or audit inputs rather than being silently treated as OpenAlex records:

| Source | Current handling |
|---|---|
| OpenAlex | Automated REST API client in `paper_search_openalex.py` |
| Crossref | Publisher/DOI metadata validation; adapter planned |
| arXiv | Identifier and version resolution through arXiv IDs/URLs; direct API adapter planned |
| OpenReview | Conference/preprint identity evidence; direct API adapter planned |
| Semantic Scholar | Independent citation-graph source; records can be imported as external JSON; direct adapter planned |
| Google Scholar | Manual high-recall audit only; no automated scraping |
| Publisher pages and official documents | Manual or agent web verification, especially for publication metadata and reference text |
| PubMed, Europe PMC, ADS, INSPIRE | Domain-specific supplementation when relevant |
| GitHub and technical blogs | Implementation, dataset, and software-status evidence; not treated as bibliographic authority |
| Reddit and Hacker News | Anecdotal workflow/indexing evidence only |

External citations are attached to the target paper identity. They are never assigned to a particular OpenAlex Work ID unless an actual OpenAlex citation edge proves that relationship.

## Current OpenAlex compatibility

The implementation targets the OpenAlex API documented in July 2026:

- API key required
- free daily API allowance
- `per_page` maximum of 100
- up to 100 OR values per filter
- basic paging limited to 10,000 results
- cursor paging for larger result sets
- `/rate-limit` endpoint and `meta.cost_usd`

Older OpenAlex examples that use no key or `per_page=200` are no longer treated as authoritative. See [`references/openalex-current-api.md`](references/openalex-current-api.md).

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
python3 paper_search_openalex.py search \
  "spin-flip TDDFT spin contamination" \
  --filter 'publication_year=2022-2026' \
  --sort=-publication_date \
  --limit 50
```

### Resolve an institution

```bash
python3 paper_search_openalex.py entity institutions "Toyohashi University of Technology"
```

Use the selected `I...` identifier:

```bash
python3 paper_search_openalex.py search "molecular machine learning" \
  --filter 'authorships.institutions.id=I...' \
  --limit 100
```

### Get one paper

```bash
python3 paper_search_openalex.py get-work 10.1038/sdata.2014.22
```

### Find papers citing all versions of a target

```bash
python3 paper_search_openalex.py citing \
  --title "Generating QM1B with PySCF IPU" \
  --author "Mathiasen, A." \
  --year 2023 \
  --doi 10.48550/arXiv.2311.01135 \
  --doi 10.52202/075280-2402 \
  --arxiv 2311.01135
```

### Retrieve outgoing references

```bash
python3 paper_search_openalex.py references \
  --doi 10.1038/sdata.2014.22 \
  --title "Quantum chemistry structures and properties of 134 kilo molecules" \
  --year 2014
```

### Group results

```bash
python3 paper_search_openalex.py group publication_year \
  --query "machine learning interatomic potentials" \
  --filter 'publication_year=2020-2026'
```

### Audit citation discrepancies

```bash
python3 paper_search_openalex.py audit-citations \
  --target-json examples/target-paper.json \
  --external-json examples/external-citations.json
```

## Citation retrieval model

The target is an identity set, not one DOI:

```text
DOIs + arXiv IDs + OpenReview IDs + URLs + title/authors/year
                              ↓
                    resolved OpenAlex Work IDs
                              ↓
          citing works for each ID or references from each ID
                              ↓
       cross-version and cross-source entity resolution + provenance
```

Externally observed citations are attached to the target identity, not fabricated OpenAlex Work edges. Only an actual OpenAlex `cites:` result can populate `cites_target_work_ids`.

## Project layout

```text
.
├── SKILL.md
├── paper_search_openalex.py
├── references/
│   ├── openalex-current-api.md
│   ├── query-recipes.md
│   └── citation-audit.md
├── examples/
│   ├── target-paper.json
│   └── external-citations.json
├── tests/
│   └── test_paper_search_openalex.py
├── pyproject.toml
└── .github/workflows/tests.yml
```

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile paper_search_openalex.py
```

The test suite covers identifier normalization, cross-source deduplication, current page limits, cursor pagination, target-version resolution, provenance merging, and correct-direction citation auditing.

## Source strategy

OpenAlex is a structured scholarly index, not a universal truth source. For consequential or disputed results, compare with publisher metadata, Crossref, arXiv/OpenReview, domain indexes, Semantic Scholar, and manual source-document inspection. Google Scholar can be useful for high-recall audits, but its version clustering and citation counts can change and it does not provide an official bulk API.

## License

MIT
