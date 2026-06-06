from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Article


class Store:
    def __init__(self, database_path: str):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists sent_articles (
                    url_hash text primary key,
                    url text not null,
                    title text not null,
                    source_name text not null,
                    category text not null,
                    published_at text,
                    sent_at text not null
                )
                """
            )

    def seen_urls(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("select url from sent_articles").fetchall()
        return {row[0] for row in rows}

    def mark_sent(self, articles: list[Article]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.executemany(
                """
                insert or ignore into sent_articles
                    (url_hash, url, title, source_name, category, published_at, sent_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        _hash_url(article.url),
                        article.url,
                        article.title,
                        article.source_name,
                        article.category,
                        article.published_at.isoformat() if article.published_at else None,
                        now,
                    )
                    for article in articles
                ],
            )


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()
