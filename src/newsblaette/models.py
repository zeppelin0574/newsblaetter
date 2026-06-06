from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Settings:
    max_items: int = 10
    lookback_hours: int = 48
    per_source_limit: int = 8
    request_timeout_seconds: int = 12
    retry_count: int = 1
    database_path: str = "data/newsblaette.sqlite3"
    output_dir: str = "output"
    user_agent: str = "newsblaette-mvp/0.1"
    category_targets: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Source:
    name: str
    category: str
    type: str
    url: str
    priority: float = 1.0
    enabled: bool = True
    link_selector: str | None = None
    include_url_patterns: tuple[str, ...] = ()
    exclude_url_patterns: tuple[str, ...] = ()
    max_items: int | None = None


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    source_name: str
    category: str
    excerpt: str
    published_at: datetime | None = None
    source_priority: float = 1.0


@dataclass(frozen=True)
class SourceFailure:
    name: str
    category: str
    url: str
    reason: str


@dataclass(frozen=True)
class BriefItem:
    title: str
    category: str
    summary: str
    comment: str
    source_name: str
    source_url: str


@dataclass(frozen=True)
class PublishResult:
    markdown_path: str
    email_sent: bool
    telegram_sent: bool
    feishu_sent: bool
    email_error: str | None = None
    telegram_error: str | None = None
    feishu_error: str | None = None
