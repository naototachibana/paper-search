# Source Access Policy

**Last reviewed:** 2026-07-27  
**Machine-readable policy:** [`source-access-policy.json`](source-access-policy.json)

This document governs how the `paper-search` skill acquires information. It is a conservative operational policy, not legal advice.

## Core rule

Use the least invasive supported method:

```text
official API
→ official bulk/OAI interface
→ official feed
→ authorized connector
→ permitted public-page fetch
→ permitted browser automation
→ document inspection
→ user-supplied or human-observed evidence
```

The absence of API credentials, approval, quota, or adapter implementation does not authorize scraping.

## Browser automation

Playwright and similar tools are automated access.

They may be used only when all of the following are true:

1. The exact page is public.
2. No official API, feed, bulk interface, or connector supplies the needed fact.
3. The current terms do not prohibit the intended automated access.
4. The current `robots.txt` does not prohibit the relevant automated agent.
5. JavaScript rendering or interaction is necessary.
6. No login, paywall, CAPTCHA, rate limit, geographic restriction, or other technical control is bypassed.
7. The operation is narrow, cached, and non-recursive.

If any condition cannot be established, use a user-supplied or human-observed record instead.

## Provenance schema

Store the information source separately from the acquisition method.

```json
{
  "source": "reddit",
  "acquisition_method": "official_api",
  "observed_at": "2026-07-27",
  "evidence_url": "https://www.reddit.com/r/example/comments/...",
  "policy_checked_at": "2026-07-27",
  "policy_basis_urls": [
    "https://redditinc.com/policies/data-api-terms"
  ]
}
```

For websites whose rules are checked dynamically, also record:

```json
{
  "terms_url": "https://example.com/terms",
  "robots_url": "https://example.com/robots.txt",
  "terms_result": "no explicit prohibition found for narrow public-page retrieval",
  "robots_result": "allowed for configured user agent"
}
```

Do not write `manual`. Use `human_observed`, `user_supplied`, `document_inspection`, or another precise method.

## Source matrix

### OpenAlex

**Use:** official API or snapshot.

- API key required.
- Use `per_page<=100`.
- Use cursor pagination beyond normal paging limits.
- Track request cost and rate headers.
- Honor 429/5xx with backoff.

**Do not:** scrape the web UI as an API substitute or evade budget/rate controls.

Official basis:

- https://developers.openalex.org/api-reference/authentication
- https://developers.openalex.org/api-reference/errors

### Crossref

**Use:** official REST API or documented bulk interfaces.

- Prefer the polite pool with `mailto` and identifying `User-Agent`.
- Cache responses.
- Observe rate and concurrency headers.
- Back off on 429/403.

**Do not:** scrape publisher pages merely to reproduce Crossref metadata.

Official basis:

- https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- https://github.com/CrossRef/rest-api-doc

### arXiv

**Use:** official API, RSS, OAI-PMH, or documented bulk access.

- Legacy API family: at most one request every three seconds.
- Use one connection at a time.
- Cache identical searches.
- Prefer OAI-PMH/bulk for harvesting.
- Descriptive metadata is CC0.
- Full text is governed by each submission's license.

**Do not:** use HTML scraping as the primary interface, evade limits, or redistribute content without a suitable license.

Official basis:

- https://info.arxiv.org/help/api/tou.html
- https://info.arxiv.org/help/api/user-manual.html

### OpenReview

**Use:** API 2 by default; API v1 only where required by older venues.

- Respect `readers`, `nonreaders`, `writers`, authentication, and venue permissions.
- Only retrieve private material when the authenticated user is authorized.

**Do not:** scrape around access controls or share credentials.

Official basis:

- https://docs.openreview.net/getting-started/using-the-api
- https://openreview.net/legal/terms

### Semantic Scholar

**Use:** Academic Graph API or documented datasets.

- Accept the applicable license.
- Use an API key where available.
- Use batch/bulk endpoints for large operations.
- Respect rate limits and required attribution.
- Verify that the planned research, educational, commercial, retention, redistribution, and display use is permitted.

**Do not:** scrape the website, evade controls, or synthesize OpenAlex IDs from Semantic Scholar metadata.

Official basis:

- https://www.semanticscholar.org/product/api
- https://www.semanticscholar.org/product/api/license
- https://api.semanticscholar.org/api-docs

### Google Scholar

**Use:** `human_observed` or `user_supplied` evidence. Search-engine discovery may be used to find candidates, which must then be verified against original sources.

**Do not:** scrape, use Playwright, automate “cites” pagination, or bypass CAPTCHA.

Google Scholar asks automated software to respect its `robots.txt` and does not provide an official public bulk API for this workflow.

Official basis:

- https://scholar.google.com/intl/us/scholar/help.html

### PubMed / NCBI

**Use:** E-utilities or documented bulk resources.

- Include `tool` and `email`.
- Without API key: no more than 3 requests/second.
- With API key: default maximum 10 requests/second.
- Follow NCBI scheduling guidance for large jobs.

**Do not:** scrape HTML as an API substitute or distribute requests to evade limits.

Official basis:

- https://www.ncbi.nlm.nih.gov/sites/books/NBK25497/
- https://www.ncbi.nlm.nih.gov/books/NBK25499/

### Europe PMC

**Use:** REST, SOAP, OAI, FTP, or documented bulk services.

- Check the license of each article before reuse of full text, figures, or supplements.
- Use metadata and OA services for automated retrieval.

**Do not:** scrape HTML as an API substitute or redistribute content contrary to its license.

Official basis:

- https://europepmc.org/RestfulWebService
- https://europepmc.org/developers
- https://europepmc.org/Copyright

### GitHub

**Use:** installed connector, REST API, or GraphQL API.

- Prefer authenticated calls.
- Honor primary and secondary rate limits.
- Honor `Retry-After` and reset headers.
- Use a public page fetch only when API/connector coverage is insufficient and the operation is narrow.

**Do not:** expose credentials, evade limits, or bypass repository permissions.

Official basis:

- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

### Reddit

**Use:** Reddit Data API only with registration, OAuth identity, an approved use case, attribution, rate compliance, and retention/deletion compliance.

Without approved API access, use isolated `human_observed` or `user_supplied` permalinks.

**Do not:** scrape Reddit HTML, automate it with Playwright, mask OAuth identity, or treat absent API credentials as permission to collect data.

Official basis:

- https://redditinc.com/policies/data-api-terms

### Hacker News

**Use:** official read-only Firebase API.

- Retrieve stories, comments, users, and rankings through the API.
- Cache item responses.
- Avoid unnecessary recursive traversal.

**Do not:** scrape the HTML interface as the primary source.

Official basis:

- https://github.com/HackerNews/API
- https://www.ycombinator.com/blog/hacker-news-api

### Publisher pages

Prefer:

1. Crossref or another official metadata API;
2. citation-export endpoints;
3. RSS/Atom;
4. open repositories;
5. permitted narrow page fetch;
6. document inspection of a lawfully accessible or user-supplied file.

Playwright is permitted only after a current terms/robots check and only for a public JavaScript-dependent page.

Never bypass a paywall, login, CAPTCHA, or reader restriction.

### Official institutions and government/research sites

Prefer official APIs, open-data portals, RSS/Atom, downloadable reports, or public repositories. For HTML, check terms and robots at execution time. Use Playwright only for public JS-dependent pages where automation is not prohibited.

### News outlets and technical blogs

This category includes The Verge, Tom's Hardware, Wired, Ars Technica, TechCrunch, Engadget, CNET, ZDNet, MIT Technology Review, Gizmodo, engineering blogs, and similar sources.

Because access policies change, do not hardcode permission.

For each exact host:

1. look for an official feed or API;
2. check terms and `robots.txt`;
3. use narrow web fetch only when allowed;
4. use Playwright only when allowed and required by JavaScript;
5. do not access paywalled text through alternate endpoints;
6. use reporting as context and verify scientific claims against papers or official documents.

## Policy refresh

Recheck the official policy before:

- recurring monitoring;
- high-volume retrieval;
- commercial use;
- redistribution;
- storing user-generated content;
- using a source whose policy was last checked more than 90 days ago;
- using a source after a material API or terms change.

When official policies conflict, the stricter applicable rule wins. When uncertainty remains, do not automate.
