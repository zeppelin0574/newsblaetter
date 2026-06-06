from __future__ import annotations

from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import Settings, Source


def load_project_env() -> None:
    load_dotenv()


def load_config(config_path: str | Path) -> tuple[Settings, list[Source]]:
    path = Path(config_path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    raw_settings = data.get("settings", {}) or {}
    settings = Settings(
        max_items=int(raw_settings.get("max_items", 10)),
        lookback_hours=int(raw_settings.get("lookback_hours", 48)),
        per_source_limit=int(raw_settings.get("per_source_limit", 8)),
        request_timeout_seconds=int(raw_settings.get("request_timeout_seconds", 12)),
        retry_count=int(raw_settings.get("retry_count", 1)),
        database_path=str(raw_settings.get("database_path", "data/newsblaette.sqlite3")),
        output_dir=str(raw_settings.get("output_dir", "output")),
        user_agent=str(raw_settings.get("user_agent", "newsblaette-mvp/0.1")),
        category_targets=dict(raw_settings.get("category_targets", {}) or {}),
    )

    sources: list[Source] = []
    for item in data.get("sources", []) or []:
        if not item.get("url"):
            continue
        sources.append(
            Source(
                name=str(item.get("name") or item["url"]),
                category=str(item.get("category") or "未分类"),
                type=str(item.get("type") or "rss").lower(),
                url=str(item["url"]),
                priority=float(item.get("priority", 1.0)),
                enabled=bool(item.get("enabled", True)),
                link_selector=item.get("link_selector"),
                include_url_patterns=tuple(item.get("include_url_patterns", []) or ()),
                exclude_url_patterns=tuple(item.get("exclude_url_patterns", []) or ()),
                max_items=int(item["max_items"]) if item.get("max_items") is not None else None,
            )
        )

    return settings, [source for source in sources if source.enabled]
