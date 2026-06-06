from __future__ import annotations

import base64
import hashlib
import hmac
import os
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import httpx

from .models import BriefItem, PublishResult, SourceFailure


def publish_briefing(
    items: list[BriefItem],
    failures: list[SourceFailure],
    output_dir: str,
    dry_run: bool = False,
) -> PublishResult:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    markdown = render_markdown(items, failures, now)
    markdown_path = Path(output_dir) / f"briefing_{now:%Y-%m-%d}.md"
    markdown_path.write_text(markdown, encoding="utf-8")

    email_sent = False
    telegram_sent = False
    feishu_sent = False
    if not dry_run:
        email_sent = _send_email(markdown, now)
        telegram_sent = _send_telegram(markdown)
        feishu_sent = _send_feishu(markdown)

    return PublishResult(
        markdown_path=str(markdown_path),
        email_sent=email_sent,
        telegram_sent=telegram_sent,
        feishu_sent=feishu_sent,
    )


def render_markdown(items: list[BriefItem], failures: list[SourceFailure], generated_at: datetime) -> str:
    lines = [
        f"# 每日新闻晨报 - {generated_at:%Y-%m-%d}",
        "",
        f"生成时间：{generated_at:%Y-%m-%d %H:%M}",
        "",
    ]

    if not items:
        lines.extend(["今日没有筛选出可推送新闻。", ""])
    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                f"## {index}. {item.title}",
                "",
                f"- 方向：{item.category}",
                f"- 来源：{item.source_name}",
                f"- 摘要：{item.summary}",
                f"- 一句话评价：{item.comment}",
                f"- 原文：{item.source_url}",
                "",
            ]
        )

    lines.append("## 今日未成功爬取的信息源")
    lines.append("")
    if failures:
        for failure in failures:
            lines.append(f"- {failure.name}（{failure.category}）：{failure.url} - {failure.reason}")
    else:
        lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def _send_email(markdown: str, generated_at: datetime) -> bool:
    host = os.getenv("SMTP_HOST")
    to_addr = os.getenv("SMTP_TO")
    if not host or not to_addr:
        return False

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM") or username or to_addr
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}

    message = EmailMessage()
    message["Subject"] = f"每日新闻晨报 - {generated_at:%Y-%m-%d}"
    message["From"] = from_addr
    message["To"] = to_addr
    message.set_content(markdown)

    with smtplib.SMTP(host, port, timeout=20) as smtp:
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)
    return True


def _send_telegram(markdown: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    text = markdown
    if len(text) > 3800:
        text = text[:3790] + "\n..."

    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text},
        timeout=20,
    )
    response.raise_for_status()
    return True


def _send_feishu(markdown: str) -> bool:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        return False

    text = markdown
    if len(text) > 12000:
        text = text[:11990] + "\n..."

    payload: dict[str, object] = {
        "msg_type": "text",
        "content": {"text": text},
    }

    secret = os.getenv("FEISHU_SECRET")
    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _feishu_sign(timestamp, secret)

    response = httpx.post(webhook_url, json=payload, timeout=20)
    response.raise_for_status()
    result = response.json()
    if result.get("code") not in (0, None):
        raise RuntimeError(f"Feishu push failed: {result}")
    return True


def _feishu_sign(timestamp: str, secret: str) -> str:
    key = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(key, b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")
