from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .models import Article, Settings


def select_articles(articles: list[Article], settings: Settings, seen_urls: set[str]) -> list[Article]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=settings.lookback_hours)

    candidates = [
        article
        for article in articles
        if article.url not in seen_urls and (article.published_at is None or article.published_at >= cutoff)
    ]
    candidates.sort(key=lambda article: _score(article, now), reverse=True)

    selected: list[Article] = []
    selected_urls: set[str] = set()

    by_category: dict[str, list[Article]] = defaultdict(list)
    for article in candidates:
        by_category[article.category].append(article)

    for category, target in settings.category_targets.items():
        for article in by_category.get(category, [])[:target]:
            if len(selected) >= settings.max_items:
                return selected
            selected.append(article)
            selected_urls.add(article.url)

    for article in candidates:
        if len(selected) >= settings.max_items:
            break
        if article.url in selected_urls:
            continue
        selected.append(article)
        selected_urls.add(article.url)

    return selected


def _score(article: Article, now: datetime) -> float:
    recency = 0.4
    if article.published_at:
        age_hours = max((now - article.published_at).total_seconds() / 3600, 0)
        recency = max(0.1, 1 - age_hours / 72)
    text = f"{article.title} {article.excerpt}".lower()
    signal = sum(
        0.12
        for keyword in (
            "ai",
            "artificial intelligence",
            "model",
            "chip",
            "market",
            "inflation",
            "rates",
            "central bank",
            "economy",
            "research",
            "security",
        )
        if keyword in text
    )
    return article.source_priority + recency + min(signal, 0.6)
