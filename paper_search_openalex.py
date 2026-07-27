#!/usr/bin/env python3
"""General-purpose OpenAlex paper search and citation retrieval toolkit.

The module intentionally uses only the Python standard library. It supports:
- works search with common filters and cursor pagination
- entity resolution for authors, institutions, sources, topics, publishers, funders
- multi-identifier / multi-version target-paper resolution
- incoming and outgoing citation retrieval
- cross-source record deduplication with provenance merging
- citation-edge discrepancy audits
- rate-limit and cost metadata capture

OpenAlex API keys are required by the current API. Set OPENALEX_API_KEY or pass
``api_key=...`` to :class:`OpenAlexClient`.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

OPENALEX_BASE = "https://api.openalex.org"
DEFAULT_PER_PAGE = 100
MAX_PER_PAGE = 100
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 5
RETRIABLE_STATUS = {429, 500, 502, 503, 504}
ENTITY_ENDPOINTS = {
    "works",
    "authors",
    "institutions",
    "sources",
    "topics",
    "publishers",
    "funders",
    "keywords",
}


class OpenAlexError(RuntimeError):
    """Base exception for OpenAlex client failures."""


class OpenAlexAuthenticationError(OpenAlexError):
    """Raised when no API key is available."""


class OpenAlexHTTPError(OpenAlexError):
    """HTTP error preserving response status and URL."""

    def __init__(self, status: int, url: str, message: str = "") -> None:
        super().__init__(f"OpenAlex HTTP {status}: {message or url}")
        self.status = status
        self.url = url
        self.message = message


def normalize_openalex_id(value: str | None) -> str:
    """Normalize a full or short OpenAlex entity ID to its compact form."""
    if not value:
        return ""
    value = value.strip()
    match = re.search(r"(?:openalex\.org/)?([WAISTPFK]\d+)$", value, re.I)
    return match.group(1).upper() if match else value


def normalize_doi(value: str | None) -> str:
    """Normalize DOI strings to lowercase bare DOI form."""
    if not value:
        return ""
    value = urllib.parse.unquote(value.strip())
    value = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    return value.strip().rstrip(".,;)").lower()


def extract_doi(text: str | None) -> str:
    """Extract the first DOI-like value from text."""
    if not text:
        return ""
    match = re.search(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", text, re.I)
    return normalize_doi(match.group(0)) if match else ""


def normalize_arxiv_id(value: str | None) -> str:
    """Normalize modern and legacy arXiv identifiers."""
    if not value:
        return ""
    value = value.strip()
    value = re.sub(r"^(?:https?://)?arxiv\.org/(?:abs|pdf)/", "", value, flags=re.I)
    value = re.sub(r"^arxiv:\s*", "", value, flags=re.I)
    value = re.sub(r"\.pdf$", "", value, flags=re.I)
    value = re.sub(r"v\d+$", "", value, flags=re.I)
    match = re.search(r"(?:[a-z-]+/\d{7}|\d{4}\.\d{4,5})", value, re.I)
    return match.group(0).lower() if match else ""


def extract_arxiv_id(text: str | None) -> str:
    return normalize_arxiv_id(text)


def normalize_title(value: str | None) -> str:
    """Normalize a title for comparison while retaining letters and numbers."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("_", " ")
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def title_similarity(left: str | None, right: str | None) -> float:
    """Blend token Jaccard and character sequence similarity."""
    a, b = normalize_title(left), normalize_title(right)
    if not a or not b:
        return 0.0
    aset, bset = set(a.split()), set(b.split())
    jaccard = len(aset & bset) / len(aset | bset)
    sequence = SequenceMatcher(None, a, b).ratio()
    return (0.6 * jaccard) + (0.4 * sequence)


def author_surname(value: str | Mapping[str, Any] | None) -> str:
    if isinstance(value, Mapping):
        value = (
            value.get("display_name")
            or (value.get("author") or {}).get("display_name")
            or value.get("name")
            or ""
        )
    if not value:
        return ""
    name = normalize_title(str(value))
    if not name:
        return ""
    if "," in str(value):
        return normalize_title(str(value).split(",", 1)[0])
    parts = name.split()
    return parts[-1] if parts else ""


def record_year(record: Mapping[str, Any]) -> int | None:
    value = record.get("publication_year", record.get("year"))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def record_authors(record: Mapping[str, Any]) -> list[str]:
    authorships = record.get("authorships")
    if isinstance(authorships, list):
        values = []
        for item in authorships:
            if not isinstance(item, Mapping):
                continue
            author = item.get("author") or {}
            name = author.get("display_name") if isinstance(author, Mapping) else ""
            if name:
                values.append(str(name))
        return values
    authors = record.get("authors") or []
    values = []
    for item in authors:
        if isinstance(item, Mapping):
            name = item.get("name") or item.get("display_name") or ""
        else:
            name = str(item)
        if name:
            values.append(name)
    return values


def record_first_author_surname(record: Mapping[str, Any]) -> str:
    authors = record_authors(record)
    return author_surname(authors[0]) if authors else ""


def record_arxiv_id(record: Mapping[str, Any]) -> str:
    external = record.get("externalIds") or record.get("external_ids") or record.get("ids") or {}
    if isinstance(external, Mapping):
        for key in ("ArXiv", "arxiv"):
            if external.get(key):
                return normalize_arxiv_id(str(external[key]))
    for key in ("arxiv_id", "arxiv"):
        if record.get(key):
            return normalize_arxiv_id(str(record[key]))
    for value in (record.get("doi"), record.get("landing_page_url"), record.get("url")):
        arxiv_id = extract_arxiv_id(str(value or ""))
        if arxiv_id:
            return arxiv_id
    return ""


def record_doi(record: Mapping[str, Any]) -> str:
    doi = normalize_doi(str(record.get("doi") or ""))
    if doi:
        return doi
    external = record.get("externalIds") or record.get("external_ids") or {}
    if isinstance(external, Mapping):
        return normalize_doi(str(external.get("DOI") or external.get("doi") or ""))
    return ""


def record_openalex_id(record: Mapping[str, Any]) -> str:
    value = record.get("openalex_id") or record.get("id") or ""
    normalized = normalize_openalex_id(str(value))
    return normalized if normalized.startswith("W") else ""


def record_semantic_scholar_id(record: Mapping[str, Any]) -> str:
    external = record.get("externalIds") or record.get("external_ids") or {}
    value = record.get("semantic_scholar_id") or record.get("paperId") or ""
    if not value and isinstance(external, Mapping):
        value = external.get("CorpusId") or external.get("S2PaperId") or ""
    return str(value).strip().lower()


def records_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Conservative cross-source entity resolution for scholarly works."""
    for getter in (record_doi, record_openalex_id, record_arxiv_id, record_semantic_scholar_id):
        a, b = getter(left), getter(right)
        if a and b and a == b:
            return True

    left_title = normalize_title(str(left.get("title") or left.get("display_name") or ""))
    right_title = normalize_title(str(right.get("title") or right.get("display_name") or ""))
    if not left_title or not right_title or len(left_title) < 18 or left_title != right_title:
        return False

    ly, ry = record_year(left), record_year(right)
    if ly is not None and ry is not None and abs(ly - ry) > 1:
        return False

    la, ra = record_first_author_surname(left), record_first_author_surname(right)
    if la and ra:
        return la == ra
    return ly is not None and ry is not None


def _ordered_union(existing: Iterable[Any], incoming: Iterable[Any]) -> list[Any]:
    output: list[Any] = []
    seen: set[str] = set()
    for value in list(existing) + list(incoming):
        key = json.dumps(value, sort_keys=True, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        if key not in seen:
            seen.add(key)
            output.append(value)
    return output


def merge_work_records(base: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    """Merge metadata without discarding provenance from either source."""
    result = dict(base)
    for key, value in incoming.items():
        if key in {"retrieval_sources", "_retrieval_sources", "cites_target_work_ids", "_cited_target_ids"}:
            continue
        if result.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
            result[key] = value

    result["retrieval_sources"] = _ordered_union(
        base.get("retrieval_sources", base.get("_retrieval_sources", [])) or [],
        incoming.get("retrieval_sources", incoming.get("_retrieval_sources", [])) or [],
    )
    result["cites_target_work_ids"] = _ordered_union(
        base.get("cites_target_work_ids", base.get("_cited_target_ids", [])) or [],
        incoming.get("cites_target_work_ids", incoming.get("_cited_target_ids", [])) or [],
    )
    if base.get("cites_target_identity") or incoming.get("cites_target_identity"):
        result["cites_target_identity"] = True
    if incoming.get("target_version_resolution") or base.get("target_version_resolution"):
        result["target_version_resolution"] = (
            base.get("target_version_resolution") or incoming.get("target_version_resolution")
        )
    return result


def deduplicate_works(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate works across versions and sources, merging provenance."""
    output: list[dict[str, Any]] = []
    for raw in records:
        record = dict(raw)
        match_index = next((i for i, existing in enumerate(output) if records_match(existing, record)), None)
        if match_index is None:
            record.setdefault(
                "retrieval_sources",
                list(record.get("_retrieval_sources", [])) if record.get("_retrieval_sources") else [],
            )
            record.setdefault(
                "cites_target_work_ids",
                list(record.get("_cited_target_ids", [])) if record.get("_cited_target_ids") else [],
            )
            output.append(record)
        else:
            output[match_index] = merge_work_records(output[match_index], record)
    return output


@dataclass
class TargetPaper:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    dois: list[str] = field(default_factory=list)
    arxiv_ids: list[str] = field(default_factory=list)
    openreview_ids: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    openalex_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "TargetPaper":
        identifiers = data.get("identifiers") or {}
        return cls(
            title=str(data.get("title") or ""),
            authors=list(data.get("authors") or []),
            year=int(data["year"]) if data.get("year") is not None else None,
            dois=[normalize_doi(str(v)) for v in identifiers.get("dois", data.get("dois", [])) if v],
            arxiv_ids=[normalize_arxiv_id(str(v)) for v in identifiers.get("arxiv", data.get("arxiv_ids", [])) if v],
            openreview_ids=[str(v) for v in identifiers.get("openreview", data.get("openreview_ids", [])) if v],
            urls=[str(v) for v in identifiers.get("urls", data.get("urls", [])) if v],
            openalex_ids=[normalize_openalex_id(str(v)) for v in identifiers.get("openalex", data.get("openalex_ids", [])) if v],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "identifiers": {
                "dois": self.dois,
                "arxiv": self.arxiv_ids,
                "openreview": self.openreview_ids,
                "urls": self.urls,
                "openalex": self.openalex_ids,
            },
        }


class OpenAlexClient:
    """Small OpenAlex REST client with retries, cursor paging, and cost metadata."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = OPENALEX_BASE,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        user_agent: str = "paper-search-openalex/1.0",
        opener: Any | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENALEX_API_KEY", "")
        if not self.api_key:
            raise OpenAlexAuthenticationError(
                "OPENALEX_API_KEY is required. Create a free key at https://openalex.org/settings/api"
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.opener = opener or urllib.request.urlopen
        self.last_meta: dict[str, Any] = {}
        self.last_rate_headers: dict[str, str] = {}

    def _build_url(self, path: str, params: Mapping[str, Any] | None = None) -> str:
        query: dict[str, Any] = dict(params or {})
        query["api_key"] = self.api_key
        encoded = urllib.parse.urlencode(query, doseq=True, safe="|,:><!")
        return f"{self.base_url}/{path.lstrip('/')}?{encoded}"

    def _request(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        url = self._build_url(path, params)
        for attempt in range(self.max_retries):
            request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    headers = getattr(response, "headers", {})
                    self.last_rate_headers = {
                        str(k): str(v)
                        for k, v in headers.items()
                        if str(k).lower().startswith("x-ratelimit")
                    }
                    payload = json.loads(response.read().decode("utf-8"))
                    self.last_meta = dict(payload.get("meta") or {}) if isinstance(payload, Mapping) else {}
                    return payload
            except urllib.error.HTTPError as exc:
                body = ""
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                if exc.code not in RETRIABLE_STATUS or attempt == self.max_retries - 1:
                    raise OpenAlexHTTPError(exc.code, url, body[:500]) from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = float(retry_after) if retry_after and retry_after.isdigit() else (2**attempt)
                time.sleep(delay + random.random() * 0.25)
            except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                if attempt == self.max_retries - 1:
                    raise OpenAlexError(f"Request failed after {self.max_retries} attempts: {url}") from exc
                time.sleep((2**attempt) + random.random() * 0.25)
        raise OpenAlexError(f"Request failed: {url}")

    def get_single(self, entity: str, identifier: str, *, select: Sequence[str] | None = None) -> dict[str, Any] | None:
        if entity not in ENTITY_ENDPOINTS:
            raise ValueError(f"Unsupported entity: {entity}")
        params = {"select": ",".join(select)} if select else {}
        try:
            return self._request(f"/{entity}/{identifier}", params)
        except OpenAlexHTTPError as exc:
            if exc.status == 404:
                return None
            raise

    def list_entities(
        self,
        entity: str,
        *,
        search: str | None = None,
        filters: Mapping[str, Any] | None = None,
        sort: str | None = None,
        select: Sequence[str] | None = None,
        group_by: str | None = None,
        per_page: int = DEFAULT_PER_PAGE,
        page: int | None = None,
        cursor: str | None = None,
        sample: int | None = None,
    ) -> dict[str, Any]:
        if entity not in ENTITY_ENDPOINTS:
            raise ValueError(f"Unsupported entity: {entity}")
        if not 1 <= per_page <= MAX_PER_PAGE:
            raise ValueError(f"per_page must be between 1 and {MAX_PER_PAGE}")
        params: dict[str, Any] = {"per_page": per_page}
        if search:
            params["search"] = search
        if filters:
            params["filter"] = ",".join(f"{key}:{value}" for key, value in filters.items() if value is not None)
        if sort:
            params["sort"] = sort
        if select:
            params["select"] = ",".join(select)
        if group_by:
            params["group_by"] = group_by
        if page is not None:
            params["page"] = page
        if cursor is not None:
            params["cursor"] = cursor
        if sample is not None:
            params["sample"] = sample
        return self._request(f"/{entity}", params)

    def iter_entities(
        self,
        entity: str,
        *,
        limit: int | None = None,
        **kwargs: Any,
    ) -> Iterator[dict[str, Any]]:
        cursor = "*"
        yielded = 0
        per_page = min(int(kwargs.pop("per_page", DEFAULT_PER_PAGE)), MAX_PER_PAGE)
        while cursor:
            payload = self.list_entities(entity, cursor=cursor, per_page=per_page, **kwargs)
            results = payload.get("results") or []
            if not results:
                return
            for result in results:
                yield result
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            cursor = (payload.get("meta") or {}).get("next_cursor")

    def search_works(self, query: str, *, limit: int = 25, filters: Mapping[str, Any] | None = None,
                     sort: str = "-relevance_score", select: Sequence[str] | None = None) -> list[dict[str, Any]]:
        return list(self.iter_entities("works", search=query, filters=filters, sort=sort, select=select, limit=limit))

    def resolve_entity(self, entity: str, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        if entity == "works":
            return self.search_works(query, limit=limit)
        return list(self.iter_entities(entity, search=query, limit=limit))

    def get_work(self, identifier: str, *, select: Sequence[str] | None = None) -> dict[str, Any] | None:
        normalized = normalize_openalex_id(identifier)
        if normalized.startswith("W"):
            identifier = normalized
        elif normalize_doi(identifier):
            identifier = f"doi:{normalize_doi(identifier)}"
        return self.get_single("works", identifier, select=select)

    def citing_works(self, work_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        wid = normalize_openalex_id(work_id)
        return list(self.iter_entities("works", filters={"cites": wid}, limit=limit))

    def referenced_works(self, work_id: str, *, limit: int | None = None) -> list[dict[str, Any]]:
        wid = normalize_openalex_id(work_id)
        return list(self.iter_entities("works", filters={"cited_by": wid}, limit=limit))

    def group_works(self, group_by: str, *, query: str | None = None,
                    filters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        payload = self.list_entities("works", search=query, filters=filters, group_by=group_by)
        return list(payload.get("group_by") or [])

    def rate_limit(self) -> dict[str, Any]:
        return self._request("/rate-limit")


class TargetResolver:
    """Resolve a target paper to all plausible OpenAlex work-version records."""

    DEFAULT_SELECT = [
        "id", "doi", "title", "display_name", "publication_year", "type",
        "authorships", "locations", "primary_location", "ids", "referenced_works",
        "referenced_works_count", "cited_by_count",
    ]

    def __init__(self, client: OpenAlexClient, *, title_threshold: float = 0.86) -> None:
        self.client = client
        self.title_threshold = title_threshold

    def _validation(self, work: Mapping[str, Any], target: TargetPaper) -> tuple[list[str], list[str]]:
        matched: list[str] = []
        warnings: list[str] = []
        similarity = title_similarity(str(work.get("title") or work.get("display_name") or ""), target.title)
        if similarity >= self.title_threshold:
            matched.append("title")
        elif target.title:
            warnings.append(f"title_similarity={similarity:.3f}")

        year = record_year(work)
        if target.year is None or year is None or abs(year - target.year) <= 1:
            matched.append("year")
        else:
            warnings.append(f"year_mismatch={year}")

        target_surnames = {author_surname(author) for author in target.authors if author_surname(author)}
        work_surnames = {author_surname(author) for author in record_authors(work) if author_surname(author)}
        if not target_surnames or target_surnames & work_surnames:
            matched.append("author")
        else:
            warnings.append("author_mismatch")
        return matched, warnings

    def _known_url_match(self, work: Mapping[str, Any], target_urls: Sequence[str]) -> bool:
        known = {url.rstrip("/").casefold() for url in target_urls}
        locations = work.get("locations") or []
        candidates: list[str] = []
        for location in locations:
            if isinstance(location, Mapping):
                for key in ("landing_page_url", "pdf_url"):
                    if location.get(key):
                        candidates.append(str(location[key]))
        primary = work.get("primary_location") or {}
        if isinstance(primary, Mapping):
            for key in ("landing_page_url", "pdf_url"):
                if primary.get(key):
                    candidates.append(str(primary[key]))
        return any(candidate.rstrip("/").casefold() in known for candidate in candidates)

    def resolve(self, target: TargetPaper) -> list[dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}

        def add(work: Mapping[str, Any], method: str, confidence: str) -> None:
            wid = normalize_openalex_id(str(work.get("id") or ""))
            if not wid.startswith("W"):
                return
            matched, warnings = self._validation(work, target)
            existing = candidates.get(wid)
            entry = {
                "openalex_id": wid,
                "version_type": work.get("type") or "unknown",
                "matched_by": [method] + [value for value in matched if value != method],
                "confidence": confidence if not warnings else ("medium" if confidence == "high" else confidence),
                "validation_warnings": warnings,
                "metadata": dict(work),
            }
            if existing:
                existing["matched_by"] = _ordered_union(existing["matched_by"], entry["matched_by"])
                existing["validation_warnings"] = _ordered_union(
                    existing.get("validation_warnings", []), entry["validation_warnings"]
                )
                if existing["confidence"] != "high" and entry["confidence"] == "high":
                    existing["confidence"] = "high"
            else:
                candidates[wid] = entry

        for wid in target.openalex_ids:
            work = self.client.get_work(wid, select=self.DEFAULT_SELECT)
            if work:
                add(work, "openalex_id", "high")

        discovered_dois = set(target.dois)
        arxiv_ids = set(target.arxiv_ids)
        target_urls = list(target.urls)
        for openreview_id in target.openreview_ids:
            target_urls.append(f"https://openreview.net/forum?id={openreview_id}")
        for url in target_urls:
            arxiv_id = extract_arxiv_id(url)
            if arxiv_id:
                arxiv_ids.add(arxiv_id)
            doi = extract_doi(url)
            if doi:
                discovered_dois.add(doi)

        for doi in sorted(discovered_dois):
            work = self.client.get_work(doi, select=self.DEFAULT_SELECT)
            if work:
                add(work, "doi", "high")

        for arxiv_id in sorted(arxiv_ids):
            work = self.client.get_work(f"10.48550/arxiv.{arxiv_id}", select=self.DEFAULT_SELECT)
            if work:
                add(work, "arxiv", "high")

        if target.title:
            for work in self.client.search_works(target.title, limit=25, select=self.DEFAULT_SELECT):
                similarity = title_similarity(str(work.get("title") or ""), target.title)
                matched, warnings = self._validation(work, target)
                url_match = self._known_url_match(work, target_urls)
                if url_match:
                    add(work, "url", "high")
                elif similarity >= self.title_threshold and "year" in matched and "author" in matched:
                    add(work, "title_author_year", "high")
                elif similarity >= 0.92 and "year" in matched:
                    add(work, "title_year", "medium")

        return sorted(candidates.values(), key=lambda item: item["openalex_id"])


class CitationRetriever:
    """Retrieve and merge incoming or outgoing citations across target versions."""

    def __init__(self, client: OpenAlexClient) -> None:
        self.client = client

    def retrieve(
        self,
        target_work_ids: Sequence[str],
        *,
        direction: str = "incoming",
        limit_per_target: int | None = None,
        external_records: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if direction not in {"incoming", "outgoing"}:
            raise ValueError("direction must be 'incoming' or 'outgoing'")
        collected: list[dict[str, Any]] = []
        per_target: dict[str, int] = {}

        for raw_id in target_work_ids:
            work_id = normalize_openalex_id(raw_id)
            works = (
                self.client.citing_works(work_id, limit=limit_per_target)
                if direction == "incoming"
                else self.client.referenced_works(work_id, limit=limit_per_target)
            )
            per_target[work_id] = len(works)
            for work in works:
                item = dict(work)
                item["retrieval_sources"] = _ordered_union(item.get("retrieval_sources", []), ["openalex"])
                item["cites_target_work_ids"] = (
                    [work_id] if direction == "incoming" else []
                )
                collected.append(item)

        for external in external_records or []:
            item = dict(external)
            item["retrieval_sources"] = _ordered_union(
                item.get("retrieval_sources", []), [str(item.get("source") or "external")]
            )
            if direction == "incoming":
                item.setdefault("cites_target_identity", True)
                item.setdefault("target_version_resolution", "unresolved")
                item.setdefault("cites_target_work_ids", [])
            collected.append(item)

        deduped = deduplicate_works(collected)
        source_counts: dict[str, int] = {}
        for work in deduped:
            for source in work.get("retrieval_sources", []):
                source_counts[source] = source_counts.get(source, 0) + 1

        return {
            "direction": direction,
            "target_work_ids": [normalize_openalex_id(value) for value in target_work_ids],
            "per_target_counts": per_target,
            "openalex_raw_count": sum(per_target.values()),
            "union_after_deduplication": len(deduped),
            "source_counts_after_deduplication": source_counts,
            "works": sorted(
                deduped,
                key=lambda work: (-(record_year(work) or 0), -(int(work.get("cited_by_count") or 0))),
            ),
        }


class CitationAuditor:
    """Audit why externally observed citations are absent from OpenAlex citation edges."""

    def __init__(self, client: OpenAlexClient) -> None:
        self.client = client

    def audit(self, target_work_ids: Sequence[str], external_citations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        target_ids = {normalize_openalex_id(value) for value in target_work_ids}
        results: list[dict[str, Any]] = []

        for external in external_citations:
            source_record = dict(external)
            work: dict[str, Any] | None = None
            lookup_method = ""
            if record_openalex_id(source_record):
                lookup_method = "openalex_id"
                work = self.client.get_work(record_openalex_id(source_record))
            if work is None and record_doi(source_record):
                lookup_method = "doi"
                work = self.client.get_work(record_doi(source_record))
            if work is None and source_record.get("title"):
                lookup_method = "title"
                candidates = self.client.search_works(str(source_record["title"]), limit=10)
                work = next((candidate for candidate in candidates if records_match(candidate, source_record)), None)

            if work is None:
                results.append({
                    "title": source_record.get("title", ""),
                    "found_in_openalex": False,
                    "diagnosis": "citing_work_not_in_openalex",
                    "lookup_method": lookup_method,
                    "evidence": {},
                })
                continue

            referenced = {normalize_openalex_id(value) for value in (work.get("referenced_works") or [])}
            linked = sorted(target_ids & referenced)
            ref_count = work.get("referenced_works_count")
            source_reference_verified = bool(source_record.get("source_reference_verified"))
            evidence = {
                "citing_openalex_id": normalize_openalex_id(str(work.get("id") or "")),
                "referenced_works_count": ref_count,
                "linked_target_work_ids": linked,
                "source_reference_verified": source_reference_verified,
                "reference_text": source_record.get("reference_text", ""),
                "evidence_url": source_record.get("evidence_url", ""),
            }

            if linked:
                diagnosis = "citation_edge_present"
            elif not work.get("referenced_works") and (ref_count in (0, None)):
                diagnosis = "citing_work_reference_list_missing"
            elif source_reference_verified:
                diagnosis = "reference_present_but_unresolved"
            else:
                diagnosis = "citation_edge_absent_unverified"

            results.append({
                "title": work.get("title") or source_record.get("title", ""),
                "found_in_openalex": True,
                "lookup_method": lookup_method,
                "diagnosis": diagnosis,
                "evidence": evidence,
            })
        return results


def compact_work(work: Mapping[str, Any]) -> dict[str, Any]:
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {} if isinstance(primary, Mapping) else {}
    return {
        "openalex_id": record_openalex_id(work),
        "doi": record_doi(work),
        "title": work.get("title") or work.get("display_name") or "",
        "year": record_year(work),
        "type": work.get("type") or "",
        "cited_by_count": work.get("cited_by_count") or 0,
        "authors": record_authors(work),
        "source": source.get("display_name") if isinstance(source, Mapping) else "",
        "is_oa": (work.get("open_access") or {}).get("is_oa") if isinstance(work.get("open_access"), Mapping) else primary.get("is_oa") if isinstance(primary, Mapping) else None,
        "landing_page_url": primary.get("landing_page_url") if isinstance(primary, Mapping) else "",
        "retrieval_sources": work.get("retrieval_sources", work.get("_retrieval_sources", [])),
        "cites_target_work_ids": work.get("cites_target_work_ids", work.get("_cited_target_ids", [])),
        "cites_target_identity": work.get("cites_target_identity", False),
        "target_version_resolution": work.get("target_version_resolution", ""),
    }


def parse_filter_values(items: Sequence[str]) -> dict[str, str]:
    filters: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Filter must be FIELD=VALUE: {item}")
        key, value = item.split("=", 1)
        filters[key.strip()] = value.strip()
    return filters


def write_json(data: Any, output: str | None = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def _target_from_args(args: argparse.Namespace) -> TargetPaper:
    return TargetPaper(
        title=args.title or "",
        authors=args.author or [],
        year=args.year,
        dois=[normalize_doi(value) for value in (args.doi or [])],
        arxiv_ids=[normalize_arxiv_id(value) for value in (args.arxiv or [])],
        openreview_ids=args.openreview or [],
        urls=args.url or [],
        openalex_ids=[normalize_openalex_id(value) for value in (args.openalex_id or [])],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search OpenAlex and inspect scholarly citation relationships")
    parser.add_argument("--api-key", help="OpenAlex API key; defaults to OPENALEX_API_KEY")
    parser.add_argument("--output", help="Write JSON output to this path")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search scholarly works")
    search.add_argument("query")
    search.add_argument("--filter", action="append", default=[], metavar="FIELD=VALUE")
    search.add_argument("--sort", default="-relevance_score")
    search.add_argument("--limit", type=int, default=25)

    entity = sub.add_parser("entity", help="Resolve authors, institutions, sources, topics, publishers, funders, or keywords")
    entity.add_argument("entity", choices=sorted(ENTITY_ENDPOINTS - {"works"}))
    entity.add_argument("query")
    entity.add_argument("--limit", type=int, default=10)

    get_work = sub.add_parser("get-work", help="Get one work by OpenAlex ID or DOI")
    get_work.add_argument("identifier")

    group = sub.add_parser("group", help="Group works by an OpenAlex field")
    group.add_argument("field")
    group.add_argument("--query")
    group.add_argument("--filter", action="append", default=[], metavar="FIELD=VALUE")

    sub.add_parser("rate-limit", help="Show API budget and rate-limit status")

    for name, help_text in (("citing", "Retrieve works citing all versions of a target paper"),
                            ("references", "Retrieve works referenced by all versions of a target paper")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--title")
        command.add_argument("--author", action="append")
        command.add_argument("--year", type=int)
        command.add_argument("--doi", action="append")
        command.add_argument("--arxiv", action="append")
        command.add_argument("--openreview", action="append")
        command.add_argument("--url", action="append")
        command.add_argument("--openalex-id", action="append")
        command.add_argument("--limit-per-target", type=int)
        command.add_argument("--external-json", help="Optional JSON list of externally observed citing works")

    audit = sub.add_parser("audit-citations", help="Audit external citations missing from OpenAlex edges")
    audit.add_argument("--target-json", required=True, help="TargetPaper JSON file")
    audit.add_argument("--external-json", required=True, help="JSON list of externally verified citing works")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        client = OpenAlexClient(api_key=args.api_key)
        if args.command == "search":
            works = client.search_works(args.query, limit=args.limit, filters=parse_filter_values(args.filter), sort=args.sort)
            write_json({"query": args.query, "count": len(works), "works": [compact_work(work) for work in works], "meta": client.last_meta}, args.output)
        elif args.command == "entity":
            results = client.resolve_entity(args.entity, args.query, limit=args.limit)
            write_json({"entity": args.entity, "query": args.query, "results": results, "meta": client.last_meta}, args.output)
        elif args.command == "get-work":
            write_json(client.get_work(args.identifier), args.output)
        elif args.command == "group":
            write_json({"group_by": args.field, "groups": client.group_works(args.field, query=args.query, filters=parse_filter_values(args.filter)), "meta": client.last_meta}, args.output)
        elif args.command == "rate-limit":
            write_json(client.rate_limit(), args.output)
        elif args.command in {"citing", "references"}:
            target = _target_from_args(args)
            resolved = TargetResolver(client).resolve(target)
            external = []
            if args.external_json:
                external = json.loads(Path(args.external_json).read_text(encoding="utf-8"))
            direction = "incoming" if args.command == "citing" else "outgoing"
            retrieval = CitationRetriever(client).retrieve(
                [item["openalex_id"] for item in resolved],
                direction=direction,
                limit_per_target=args.limit_per_target,
                external_records=external,
            )
            retrieval["target"] = target.to_dict()
            retrieval["resolved_target_works"] = [
                {key: value for key, value in item.items() if key != "metadata"} for item in resolved
            ]
            retrieval["works"] = [compact_work(work) for work in retrieval["works"]]
            write_json(retrieval, args.output)
        elif args.command == "audit-citations":
            target_data = json.loads(Path(args.target_json).read_text(encoding="utf-8"))
            target = TargetPaper.from_mapping(target_data)
            resolved = TargetResolver(client).resolve(target)
            external = json.loads(Path(args.external_json).read_text(encoding="utf-8"))
            audits = CitationAuditor(client).audit([item["openalex_id"] for item in resolved], external)
            write_json({"target": target.to_dict(), "resolved_target_works": [item["openalex_id"] for item in resolved], "audits": audits}, args.output)
        return 0
    except (OpenAlexError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
