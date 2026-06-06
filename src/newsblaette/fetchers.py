from __future__ import annotations

import re
import warnings
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from time import sleep
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

from .models import Article, Settings, Source, SourceFailure


class FetchError(Exception):
    pass


def fetch_sources(settings: Settings, sources: list[Source]) -> tuple[list[Article], list[SourceFailure]]:
    headers = {"User-Agent": settings.user_agent}
    articles: list[Article] = []
    failures: list[SourceFailure] = []

    with httpx.Client(headers=headers, follow_redirects=True, timeout=settings.request_timeout_seconds) as client:
        for source in sources:
            try:
                if source.type == "rss":
                    articles.extend(_fetch_rss(client, source, settings))
                elif source.type == "html":
                    articles.extend(_fetch_html_index(client, source, settings))
                else:
                    raise FetchError(f"unsupported source type: {source.type}")
            except Exception as exc:
                failures.append(
                    SourceFailure(
                        name=source.name,
                        category=source.category,
                        url=source.url,
                        reason=_short_reason(exc),
                    )
                )

    return _dedupe_articles(articles), failures


def _fetch_rss(client: httpx.Client, source: Source, settings: Settings) -> list[Article]:
    response = _request_with_retry(client, source.url, settings.retry_count)
    parsed = feedparser.parse(response.content)

    if parsed.bozo and not parsed.entries:
        raise FetchError(str(parsed.bozo_exception))
    if not parsed.entries:
        raise FetchError("rss feed returned no entries")

    limit = source.max_items or settings.per_source_limit
    articles: list[Article] = []
    for entry in parsed.entries[:limit]:
        url = getattr(entry, "link", "") or ""
        title = _clean_text(getattr(entry, "title", "") or "")
        if not url or not title:
            continue

        excerpt = _entry_excerpt(entry)
        articles.append(
            Article(
                title=title,
                url=url,
                source_name=source.name,
                category=source.category,
                excerpt=excerpt,
                published_at=_entry_datetime(entry),
                source_priority=source.priority,
            )
        )

    if not articles:
        raise FetchError("rss feed had entries, but none contained title and link")
    return articles


def _fetch_html_index(client: httpx.Client, source: Source, settings: Settings) -> list[Article]:
    response = _request_with_retry(client, source.url, settings.retry_count)
    soup = BeautifulSoup(response.text, "html.parser")
    anchors = soup.select(source.link_selector) if source.link_selector else soup.find_all("a")

    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in anchors:
        href = anchor.get("href")
        if not href:
            continue
        url = urljoin(source.url, href)
        if url in seen:
            continue
        if source.include_url_patterns and not any(pattern in url for pattern in source.include_url_patterns):
            continue
        if source.exclude_url_patterns and any(pattern in url for pattern in source.exclude_url_patterns):
            continue
        title = _clean_text(anchor.get_text(" ", strip=True))
        if not title:
            continue
        seen.add(url)
        links.append((url, title))

    if not links:
        raise FetchError("html page returned no matching article links")

    articles: list[Article] = []
    for url, link_title in links[: source.max_items or settings.per_source_limit]:
        try:
            article_response = _request_with_retry(client, url, settings.retry_count)
            article_soup = BeautifulSoup(article_response.text, "html.parser")
            title = _page_title(article_soup) or link_title
            excerpt = _page_excerpt(article_soup)
            articles.append(
                Article(
                    title=title,
                    url=url,
                    source_name=source.name,
                    category=source.category,
                    excerpt=excerpt,
                    published_at=None,
                    source_priority=source.priority,
                )
            )
        except Exception:
            continue

    if not articles:
        raise FetchError("html links were found, but no article pages could be fetched")
    return articles


def _request_with_retry(client: httpx.Client, url: str, retry_count: int) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt < retry_count:
                sleep(0.5 * (attempt + 1))
    raise FetchError(str(last_error) if last_error else "request failed")


def _entry_excerpt(entry: object) -> str:
    for key in ("summary", "description"):
        value = getattr(entry, key, None)
        if value:
            return _clean_text(_strip_html(str(value)))
    content = getattr(entry, "content", None)
    if content and isinstance(content, list):
        value = content[0].get("value") if content and isinstance(content[0], dict) else None
        if value:
            return _clean_text(_strip_html(str(value)))
    return ""


def _entry_datetime(entry: object) -> datetime | None:
    for key in ("published", "updated", "created"):
        value = getattr(entry, key, None)
        if value:
            try:
                dt = parsedate_to_datetime(str(value))
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (TypeError, ValueError, IndexError):
                continue
    return None


def _page_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return _clean_text(h1.get_text(" ", strip=True))
    title = soup.find("title")
    return _clean_text(title.get_text(" ", strip=True)) if title else ""


def _page_excerpt(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = " ".join(p for p in paragraphs if p)
    if not text:
        text = container.get_text(" ", strip=True)
    return _clean_text(text)[:2400]


def _strip_html(value: str) -> str:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MarkupResemblesLocatorWarning)
        return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def _clean_text(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _dedupe_articles(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    unique: list[Article] = []
    for article in articles:
        key = article.url.split("#", 1)[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


def _short_reason(exc: Exception) -> str:
    reason = str(exc).replace("\n", " ").strip()
    return reason[:220] if reason else exc.__class__.__name__
