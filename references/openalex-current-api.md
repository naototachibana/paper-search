# Current OpenAlex API notes

Validated: **2026-07-27**

This file records assumptions that materially affect the implementation. Re-check them against the current developer documentation before changing API behavior.

## Authentication and cost

- API requests require `api_key`.
- A free API key includes a daily allowance currently described as `$1/day`.
- Different endpoint classes have different costs.
- list and filter requests expose query cost in `meta.cost_usd`.
- use `/rate-limit` to inspect remaining budget and reset timing.
- the current changelog states that API keys became required on 2026-02-13.

Primary references:

- https://developers.openalex.org/api-reference/authentication
- https://developers.openalex.org/api-reference/rate-limits/check-rate-limit-status
- https://help.openalex.org/hc/en-us/articles/38868153578263-Changelog

## Current query limits

At validation time:

- maximum `per_page`: 100
- maximum OR values per filter: 100
- maximum `sample`: 10,000
- basic paging limit: 10,000 results
- use cursor pagination for deeper retrieval
- maximum request rate: 100 requests/second, subject to budget

Reference:

- https://developers.openalex.org/api-reference/authentication
- https://developers.openalex.org/api-reference/works/list-works

## Paging

Start cursor paging with:

```text
cursor=*
```

Then pass the returned `meta.next_cursor` until it is null or the result list is empty.

Do not use cursor paging to mirror the complete OpenAlex corpus. Use the snapshot for full-database work.

## Search versus filters

Use `search=` for relevance-ranked text discovery over scholarly text. Use structured filters for constraints.

Examples:

```text
search=quantum chemistry machine learning
filter=publication_year:2024-2026
sort=-publication_date
```

Resolve ambiguous named entities first:

```text
/authors?search=...
/institutions?search=...
/sources?search=...
/topics?search=...
```

Then filter works using the chosen stable ID.

## Citation directions

- `filter=cites:W...` returns works that cite the target: incoming citations.
- `filter=cited_by:W...` returns works referenced by the target: outgoing citations.

The names are easy to reverse. Test both directions explicitly.

## Archived documentation warning

The archived `ourresearch/openalex-docs` repository and older tutorials may still state:

- no authentication required
- `per-page=200`
- old rate-limit or polite-pool behavior

Treat the current `developers.openalex.org` reference and help-center changelog as authoritative when these conflict.

## Operational observations

The current API returns rate-limit and cost information that client libraries may discard. This toolkit retains `meta` and `X-RateLimit-*` headers when available. A March 2026 PyAlex issue specifically reported missing rate-limit-header exposure and insufficient 429 handling, reinforcing the need for explicit retry and budget instrumentation.
