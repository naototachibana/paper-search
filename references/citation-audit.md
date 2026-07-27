# Citation discrepancy audit

## The central direction rule

When an external index says paper **C** cites target **T**, but OpenAlex does not return **C** from `filter=cites:T`, inspect **C**, the citing paper.

Do not infer the cause from `T.referenced_works_count`. That property describes references made by the target, not references pointing into it.

## Audit procedure

For each externally observed citing paper:

1. Resolve it in OpenAlex by OpenAlex ID, DOI, arXiv ID, then title/author/year.
2. Read the citing paper's `referenced_works` and `referenced_works_count`.
3. Compare those IDs with every resolved OpenAlex version of the target.
4. If no edge exists, inspect an accessible publisher HTML page, PDF, repository copy, or structured reference list.
5. Record evidence and classify the failure.

## Diagnoses

### `citation_edge_present`

The citing paper's OpenAlex `referenced_works` contains a resolved target Work ID.

### `citing_work_not_in_openalex`

The external citing paper could not be resolved in OpenAlex.

### `citing_work_reference_list_missing`

The citing work exists, but its OpenAlex reference list is absent or empty.

### `reference_present_but_unresolved`

The source document visibly cites the target, but none of the target Work IDs appears in OpenAlex `referenced_works`. This is strong evidence of reference extraction, matching, or version-clustering failure.

### `citation_edge_absent_unverified`

No OpenAlex edge exists, but the underlying source reference has not yet been independently verified.

## Evidence format

```json
{
  "title": "Citing paper title",
  "doi": "10.xxxx/...",
  "source_reference_verified": true,
  "reference_text": "Author et al. Target paper title ...",
  "evidence_url": "https://publisher.example/paper"
}
```

Keep quoted reference text brief and use it only for verification.

## Cross-index counts

Keep counts separate:

```json
{
  "openalex_raw": 0,
  "openalex_after_dedup": 0,
  "semantic_scholar": 7,
  "google_scholar_manual": 9,
  "union_after_deduplication": 8
}
```

A database-specific count is not a universal citation count. Coverage, source inclusion, version clustering, and reference matching differ across indexes.

## Google Scholar

Use Google Scholar as a manual high-recall audit source. Do not scrape it automatically or treat its count as a fixed ground truth. Its records can be merged, split, reprocessed, or temporarily removed.
