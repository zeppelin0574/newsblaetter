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
from typing import Callable
from urllib.parse import urlparse

import httpx

from .models import BriefItem, PublishResult, SourceFailure


def publish_briefing(
    items: list[BriefItem],
    failures: list[SourceFailure],
    output_dir: str,
    report_title: str,
    dry_run: bool = False,
) -> PublishResult:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    markdown = render_markdown(items, failures, now, report_title)
    markdown_path = Path(output_dir) / f"briefing_{now:%Y-%m-%d}.md"
    markdown_path.write_text(markdown, encoding="utf-8")

    email_sent = False
    telegram_sent = False
    feishu_sent = False
    if not dry_run:
        email_sent, email_error = _safe_send(lambda: _send_email(markdown, now, report_title))
        telegram_sent, telegram_error = _safe_send(lambda: _send_telegram(markdown))
        feishu_sent, feishu_error = _safe_send(lambda: _send_feishu(markdown))
    else:
        email_error = None
        telegram_error = None
        feishu_error = None

    return PublishResult(
        markdown_path=str(markdown_path),
        email_sent=email_sent,
        telegram_sent=telegram_sent,
        feishu_sent=feishu_sent,
        email_error=email_error,
        telegram_error=telegram_error,
        feishu_error=feishu_error,
    )


def render_markdown(
    items: list[BriefItem],
    failures: list[SourceFailure],
    generated_at: datetime,
    report_title: str,
) -> str:
    lines = [
        f"# {report_title} - {generated_at:%Y-%m-%d}",
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
                f"- 链接：{item.source_url}",
                f"- 概括：{item.summary}",
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


def _send_email(markdown: str, generated_at: datetime, report_title: str) -> bool:
    host = _env("SMTP_HOST")
    to_addr = _env("SMTP_TO")
    if not host or not to_addr:
        return False

    port = int(_env("SMTP_PORT") or "587")
    username = _env("SMTP_USERNAME")
    password = _env("SMTP_PASSWORD")
    from_addr = _env("SMTP_FROM") or username or to_addr
    use_tls = (_env("SMTP_USE_TLS") or "true").lower() in {"1", "true", "yes"}

    message = EmailMessage()
    message["Subject"] = f"{report_title} - {generated_at:%Y-%m-%d}"
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


def _safe_send(send_func: Callable[[], bool]) -> tuple[bool, str | None]:
    try:
        return send_func(), None
    except Exception as exc:
        return False, _short_error(exc)


def _send_telegram(markdown: str) -> bool:
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
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
    webhook_url = _normalize_feishu_webhook_url(_env("FEISHU_WEBHOOK_URL"))
    if not webhook_url:
        raise ValueError(
            "FEISHU_WEBHOOK_URL is not configured or was not loaded. "
            "Put the group custom bot Webhook URL in the project .env file."
        )

    text = markdown
    if len(text) > 12000:
        text = text[:11990] + "\n..."

    payload: dict[str, object] = {
        "msg_type": "text",
        "content": {"text": text},
    }

    secret = _env("FEISHU_SECRET")
    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = _feishu_sign(timestamp, secret)

    response = httpx.post(webhook_url, json=payload, timeout=20)
    response.raise_for_status()
    result = response.json()
    if result.get("code") not in (0, None):
        raise RuntimeError(_feishu_error_message(result))
    return True


def _feishu_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _normalize_feishu_webhook_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().strip('"').strip("'").strip()
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        if "/open-apis/bot/v2/hook/" not in parsed.path:
            raise ValueError(
                "FEISHU_WEBHOOK_URL must be the custom bot Webhook URL, "
                "for example https://open.feishu.cn/open-apis/bot/v2/hook/xxxx."
            )
        return value
    return f"https://open.feishu.cn/open-apis/bot/v2/hook/{value}"


def _feishu_error_message(result: dict[str, object]) -> str:
    code = result.get("code")
    msg = result.get("msg")
    if code == 19001:
        return (
            f"Feishu push failed: {result}. "
            "Webhook token is invalid. Paste the full Webhook URL from the group custom bot, "
            "not the Feishu app App ID or App Secret."
        )
    if code == 19021:
        return (
            f"Feishu push failed: {result}. "
            "Signature check failed. FEISHU_SECRET must be the group custom bot signing secret, "
            "and the system clock must be within one hour of Feishu server time."
        )
    if code == 19024:
        return (
            f"Feishu push failed: {result}. "
            "Keyword check failed. Add a keyword included in the pushed text, such as 每日新闻晨报."
        )
    return f"Feishu push failed: code={code}, msg={msg}, response={result}"


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().strip('"').strip("'").strip()


def _short_error(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    return message[:240] if message else exc.__class__.__name__
