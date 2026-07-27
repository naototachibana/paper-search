# Query recipes

All examples require `OPENALEX_API_KEY`.

## Recent literature by relevance

```bash
python3 paper_search_openalex.py search \
  "solvent-aware graph neural networks optical properties" \
  --filter 'publication_year=2025-2026' \
  --sort=-relevance_score \
  --limit 100
```

## Most cited papers within a bounded period

```bash
python3 paper_search_openalex.py search \
  "machine learning interatomic potentials" \
  --filter 'publication_year=2022-2026' \
  --sort=-cited_by_count \
  --limit 100
```

Do not compare recent and old works only by raw citation count.

## Open-access papers

```bash
python3 paper_search_openalex.py search "MR-SF-TDDFT" \
  --filter 'open_access.is_oa=true' \
  --limit 100
```

## Resolve an author and search their work

```bash
python3 paper_search_openalex.py entity authors "Pavlo Dral"
python3 paper_search_openalex.py search "quantum chemistry data sets" \
  --filter 'authorships.author.id=A...'
```

Prefer ORCID when available.

## Resolve an institution

```bash
python3 paper_search_openalex.py entity institutions "University of Tokyo"
python3 paper_search_openalex.py search "quantum computing chemistry" \
  --filter 'authorships.institutions.id=I...'
```

## Resolve a journal or conference source

```bash
python3 paper_search_openalex.py entity sources "Journal of Chemical Theory and Computation"
python3 paper_search_openalex.py search "excited states" \
  --filter 'primary_location.source.id=S...'
```

## Topic-constrained search

```bash
python3 paper_search_openalex.py entity topics "molecular property prediction"
python3 paper_search_openalex.py search "conformer energy" \
  --filter 'topics.id=T...'
```

## Work types

OpenAlex work types can change. Inspect current returned values rather than assuming journal terminology. Common values include `article`, `preprint`, `book`, `book-chapter`, `dataset`, `dissertation`, and `review`.

```bash
python3 paper_search_openalex.py search "QM9" \
  --filter 'type=article|preprint|dataset'
```

## Group by year

```bash
python3 paper_search_openalex.py group publication_year \
  --query "graph neural networks chemistry"
```

## Group by topic

```bash
python3 paper_search_openalex.py group topics.id \
  --query "density functional theory machine learning" \
  --filter 'publication_year=2024-2026'
```

Only one `group_by` dimension is supported per query. Combine multiple grouped queries client-side.

## Multi-version citing works

```bash
python3 paper_search_openalex.py citing \
  --title "Full title" \
  --author "FirstAuthor, A." \
  --year 2024 \
  --doi 10.xxxx/preprint \
  --doi 10.xxxx/final \
  --arxiv 2401.00001 \
  --url https://openreview.net/forum?id=...
```

The union must be deduplicated by normalized identifiers and conservative title/author/year matching.

## Batch work lookups in custom code

For many known identifiers, use OpenAlex OR filters instead of one request per DOI where practical. Current documentation permits up to 100 OR values per filter. Split larger inputs into chunks and deduplicate by OpenAlex ID.
