from __future__ import annotations

import json
import os
from textwrap import shorten

from .models import Article, BriefItem


def build_brief_items(articles: list[Article]) -> list[BriefItem]:
    if not articles:
        return []

    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            return _build_with_openai(articles)
        except Exception:
            pass

    return [_fallback_item(article) for article in articles]


def _build_with_openai(articles: list[Article]) -> list[BriefItem]:
    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI()
    payload = [
        {
            "id": index,
            "title": article.title,
            "category": article.category,
            "source_name": article.source_name,
            "source_url": article.url,
            "excerpt": shorten(article.excerpt or "", width=1600, placeholder="..."),
        }
        for index, article in enumerate(articles, start=1)
    ]
    prompt = f"""
请只基于给定材料生成晨报条目，不编造材料外事实。

要求：
- 输出严格 JSON 对象，不要 Markdown，不要解释。
- JSON 对象格式为 {{"items": [...]}}。
- items 内每个对象包含 id、title、category、summary、comment。
- summary 使用中文，150-200字。
- comment 使用中文，一句话，给出影响判断或观察角度，避免夸张。
- title 可以翻译或压缩，但不要改变事实。
- 如果材料信息不足，请在 summary 中说明“原文披露信息有限”。

材料：
{json.dumps(payload, ensure_ascii=False)}
""".strip()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个严谨的中文新闻晨报编辑。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    raw_text = response.choices[0].message.content or ""
    decoded = _loads_items(raw_text)

    by_id = {index: article for index, article in enumerate(articles, start=1)}
    items: list[BriefItem] = []
    for item in decoded:
        article = by_id.get(int(item.get("id", 0)))
        if not article:
            continue
        items.append(
            BriefItem(
                title=str(item.get("title") or article.title),
                category=str(item.get("category") or article.category),
                summary=_fit_text(str(item.get("summary") or ""), article),
                comment=_one_sentence(str(item.get("comment") or "")),
                source_name=article.source_name,
                source_url=article.url,
            )
        )

    if not items:
        raise ValueError("model returned no usable briefing items")
    return items


def _loads_items(raw_text: str) -> list[dict[str, object]]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    if text.startswith("{"):
        decoded_object = json.loads(text)
        items = decoded_object.get("items", [])
        if not isinstance(items, list):
            raise ValueError("response JSON object did not contain an items array")
        return [item for item in items if isinstance(item, dict)]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("response did not contain JSON items")
    decoded = json.loads(text[start : end + 1])
    if not isinstance(decoded, list):
        raise ValueError("response JSON is not an array")
    return [item for item in decoded if isinstance(item, dict)]


def _fallback_item(article: Article) -> BriefItem:
    base = (
        f"{article.source_name} 报道或发布了“{article.title}”。"
        f"{article.excerpt[:520]} "
        f"这条信息被归入{article.category}方向，当前 MVP 仅使用来源中可见的标题和摘要生成内容，"
        "建议结合原文链接继续核验细节、发布时间和上下文。"
    )
    return BriefItem(
        title=article.title,
        category=article.category,
        summary=_fit_text(base, article),
        comment="值得关注其后续影响，以及是否会转化为可验证的市场或技术进展。",
        source_name=article.source_name,
        source_url=article.url,
    )


def _fit_text(text: str, article: Article) -> str:
    text = " ".join(text.split())
    if not text:
        text = f"{article.source_name} 发布了“{article.title}”，原文披露信息有限。"
    while len(text) < 150:
        text += " 原文披露信息有限，后续需要结合来源链接补充事实细节和背景判断。"
    if len(text) > 200:
        text = text[:197].rstrip() + "..."
    return text


def _one_sentence(text: str) -> str:
    text = " ".join(text.split()).strip()
    if not text:
        return "值得继续跟踪其落地进展。"
    for separator in ("。", "！", "？", ".", "!", "?"):
        if separator in text:
            return text.split(separator, 1)[0].strip() + "。"
    return text + "。"
