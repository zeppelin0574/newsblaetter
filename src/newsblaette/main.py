from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import load_config, load_project_env
from .fetchers import fetch_sources
from .models import Article, SourceFailure
from .publisher import publish_briefing
from .scoring import select_articles
from .storage import Store
from .summarizer import build_brief_items


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    load_project_env()

    settings, sources = load_config(args.config)
    output_dir = args.output_dir or settings.output_dir
    store = Store(settings.database_path)

    if args.sample:
        articles, failures = _sample_articles(), _sample_failures()
    else:
        articles, failures = fetch_sources(settings, sources)

    selected = select_articles(articles, settings, store.seen_urls())
    brief_items = build_brief_items(selected)
    result = publish_briefing(
        brief_items,
        failures,
        output_dir=output_dir,
        dry_run=args.dry_run or args.sample,
    )

    if not args.dry_run and not args.sample:
        store.mark_sent(selected)

    print(f"articles fetched: {len(articles)}")
    print(f"articles selected: {len(selected)}")
    print(f"failed sources: {len(failures)}")
    print(f"markdown: {Path(result.markdown_path).resolve()}")
    print(f"email sent: {result.email_sent}")
    print(f"telegram sent: {result.telegram_sent}")
    print(f"feishu sent: {result.feishu_sent}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a daily AI/economy/tech morning briefing.")
    parser.add_argument("--config", default="config/sources.yaml", help="Path to sources YAML.")
    parser.add_argument("--output-dir", default=None, help="Override output directory.")
    parser.add_argument("--dry-run", action="store_true", help="Write Markdown but do not push or mark items sent.")
    parser.add_argument("--sample", action="store_true", help="Generate a sample briefing without network/API calls.")
    return parser.parse_args(argv)


def _sample_articles() -> list[Article]:
    now = datetime.now(timezone.utc)
    return [
        Article(
            title="示例：新一代模型发布并强调企业级安全能力",
            url="https://example.com/ai/model-release",
            source_name="Sample AI Source",
            category="AI",
            excerpt="一家 AI 公司发布新一代模型，重点强调更长上下文、工具调用、企业权限管理和合规审计能力。",
            published_at=now - timedelta(hours=2),
            source_priority=1.0,
        ),
        Article(
            title="示例：主要央行释放谨慎降息信号",
            url="https://example.com/economy/central-bank",
            source_name="Sample Economy Source",
            category="全球经济",
            excerpt="主要央行在最新声明中表示通胀仍需观察，市场重新评估未来两个季度的利率路径。",
            published_at=now - timedelta(hours=4),
            source_priority=1.0,
        ),
        Article(
            title="示例：芯片厂商公布新数据中心加速器路线图",
            url="https://example.com/tech/chip-roadmap",
            source_name="Sample Tech Source",
            category="科技",
            excerpt="芯片厂商公布面向数据中心的新一代加速器路线图，强调能效、互联带宽和推理成本优化。",
            published_at=now - timedelta(hours=6),
            source_priority=1.0,
        ),
    ]


def _sample_failures() -> list[SourceFailure]:
    return [
        SourceFailure(
            name="Sample Failed Source",
            category="AI",
            url="https://example.com/unreachable-rss",
            reason="sample: request timed out",
        )
    ]


if __name__ == "__main__":
    sys.exit(main())
