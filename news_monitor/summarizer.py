"""
News Monitor v2.2 - OpenAI Summarizer Module
- Structured macro insight (4 lines)
- Deduplication across sources (title similarity + 多源確認)
- Readable layout: Header / Top 5 / Macro / Per-source / Tomorrow
- Topic tags (🌍宏觀 / 🛢能源 / 💹市場 / 🧠AI)
"""

import os
import re
import json
from difflib import SequenceMatcher
from openai import OpenAI
from typing import Optional

# 主題標籤：供 LLM 或後處理選用
TOPIC_TAGS = {"macro": "🌍宏觀", "energy": "🛢能源", "market": "💹市場", "ai": "🧠AI"}

# 單一主題最多顯示條數，避免刷屏
MAX_ITEMS_PER_TOPIC = 4

# JSON Schema for structured news extraction
NEWS_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "news_list": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "新聞標題"},
                    "link": {"type": "string", "description": "新聞原始連結 URL"},
                    "description": {"type": "string", "description": "一句話簡短描述"}
                },
                "required": ["title", "description"]
            }
        }
    },
    "required": ["news_list"]
}

EXTRACTION_SYSTEM_PROMPT = """你是一位專業的新聞資料提取專家。

你的任務是從提供的網頁內容中提取新聞列表。

提取規則：
1. 提取前 15 條最新的新聞資訊
2. 只包含商業、科技、財經相關的標題
3. 忽略廣告、側邊欄、導航選單等無關內容
4. 每條新聞必須包含：
   - title: 新聞標題
   - link: 新聞原始連結（必須是完整 URL，如 https://...）
   - description: 一句話描述

重要：link 欄位必須提取完整的 URL，如果找不到連結則填入空字串。

輸出格式：JSON，包含 news_list 數組。"""

EXTRACTION_USER_PROMPT = """請從以下 {source_name} ({source_url}) 的網頁內容中提取前 15 條最新新聞：

{content}

請輸出 JSON 格式，包含 news_list 數組，每個元素必須有 title、link、description 欄位。
連結請使用完整 URL，如果原始連結是相對路徑，請補全為 {base_url} 開頭的完整連結。"""


def _normalize_title(title: str) -> str:
    """正規化標題供相似度比對：小寫、去標點、連續空白單一化。"""
    if not title:
        return ""
    s = re.sub(r"[^\w\s]", " ", title.lower())
    return " ".join(s.split())


def _title_similarity(a: str, b: str) -> float:
    """回傳 0~1，越高越相似。使用序列比對。"""
    na, nb = _normalize_title(a), _normalize_title(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def deduplicate_across_sources(processed_results: list[dict]) -> list[dict]:
    """
    跨來源去重：標題相似度高的視為同一事件，合併為一則並標註「多源確認：A/B/C」。
    同事件只保留一則主訊息（保留第一個來源的連結與描述），其餘來源名寫入 sources_confirming。
    回傳結構與 processed_results 相同，但每個 news 可能多出 sources_confirming: list[str]。
    """
    # 展平：(source_name, index_in_source, item)
    flat: list[tuple[str, int, dict]] = []
    for result in processed_results:
        name = result.get("name", "")
        for i, news in enumerate(result.get("news_list", [])):
            flat.append((name, i, {**news, "sources_confirming": []}))

    # 相似度門檻：超過則視為同一事件
    SIM_THRESHOLD = 0.62

    merged_indices: set[tuple[str, int]] = set()  # 已被合併到別人的 (source, idx)
    canonical: list[tuple[str, int, dict]] = []   # (primary_source, idx, merged_item)

    for i, (src, idx, item) in enumerate(flat):
        if (src, idx) in merged_indices:
            continue
        title = item.get("title", "")
        link = item.get("link", "")
        desc = item.get("description", "")
        confirming = [src]

        for j, (src2, idx2, item2) in enumerate(flat):
            if i >= j or (src2, idx2) in merged_indices:
                continue
            if _title_similarity(title, item2.get("title", "")) >= SIM_THRESHOLD:
                merged_indices.add((src2, idx2))
                confirming.append(src2)
                if not link and item2.get("link"):
                    link = item2["link"]
                    desc = item2.get("description", desc)

        item_copy = {**item, "link": link or item.get("link"), "description": desc or item.get("description", "")}
        item_copy["sources_confirming"] = [s for s in confirming[1:]]  # 不含 primary
        canonical.append((src, idx, item_copy))

    # 按來源重新組回 processed 結構
    by_source: dict[str, list[dict]] = {}
    for result in processed_results:
        by_source[result["name"]] = []

    for primary_src, _, merged_item in canonical:
        if primary_src not in by_source:
            continue
        # 單一主題最多 4 條：依來源內條數限制（跨來源已合併，這裡只限制每來源條數）
        if len(by_source[primary_src]) >= 5:
            continue
        by_source[primary_src].append(merged_item)

    out = []
    for result in processed_results:
        name = result["name"]
        out.append({
            **result,
            "news_list": by_source.get(name, [])[:5],  # 每來源最多 5 條
        })
    return out


# v2.2 結構化摘要：宏觀 4 行 + Top5 + 分來源 + 明日跟蹤
SUMMARY_STRUCTURED_SCHEMA = {
    "type": "object",
    "properties": {
        "macro_insight": {
            "type": "object",
            "properties": {
                "risk_temperature": {"type": "string", "enum": ["高", "中", "低"], "description": "風險溫度"},
                "main_drivers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 3,
                    "description": "主驅動因素，如地緣、能源、利率、監管、流動性"
                },
                "asset_mapping": {
                    "type": "object",
                    "properties": {
                        "美股": {"type": "string", "enum": ["↑", "↓", "→"]},
                        "黃金": {"type": "string", "enum": ["↑", "↓", "→"]},
                        "原油": {"type": "string", "enum": ["↑", "↓", "→"]},
                        "BTC": {"type": "string", "enum": ["↑", "↓", "→"]}
                    },
                    "description": "資產方向"
                },
                "watch_24h": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "24h 內 3 個可觀測事件"
                }
            },
            "required": ["risk_temperature", "main_drivers", "asset_mapping", "watch_24h"]
        },
        "top5": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "one_liner": {"type": "string", "description": "中文一句點評"},
                    "link": {"type": "string"},
                    "tag": {"type": "string", "enum": ["🌍宏觀", "🛢能源", "💹市場", "🧠AI"]}
                },
                "required": ["title", "one_liner", "tag"]
            },
            "maxItems": 5
        },
        "per_source": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "one_liner": {"type": "string"},
                        "link": {"type": "string"},
                        "tag": {"type": "string", "enum": ["🌍宏觀", "🛢能源", "💹市場", "🧠AI"]},
                        "sources_confirming": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["title", "one_liner", "tag"]
                },
                "maxItems": 5
            },
            "description": "每個來源最多 3-5 條"
        },
        "tomorrow": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
            "description": "明日跟蹤清單 3 條"
        }
    },
    "required": ["macro_insight", "top5", "per_source", "tomorrow"]
}

SUMMARY_SYSTEM_PROMPT_V2 = """你是財經新聞編輯，負責產出「每日 Telegram 新聞」的結構化摘要。

## 輸出規定（嚴格遵守）

1. **宏觀洞察**：固定 4 行
   - 風險溫度：高 / 中 / 低
   - 主驅動：最多 3 個（地緣、能源、利率、監管、流動性等）
   - 資產映射：美股 / 黃金 / 原油 / BTC 各為 ↑ 或 ↓ 或 →
   - 24h 關注點：3 個可觀測事件

2. **Top 5 必看**：從所有新聞中選 5 條，每條含標題、中文一句、連結、主題標籤（🌍宏觀/🛢能源/💹市場/🧠AI）。

3. **分來源摘要**：每個來源最多 3-5 條，每條含標題、一句、連結、標籤。若該條有多源確認，會由系統傳入 sources_confirming，請保留在輸出中。

4. **明日跟蹤**：3 條可觀測的明日重點。

5. **去重與降噪**：同一主題（如戰爭、單一利率決議）最多呈現 4 條，其餘合併或省略。

6. **連結**：必須保留原始 URL，沒有則空字串。

請輸出 JSON，符合給定的 schema。"""

# 保留 v2.1 舊版 prompt，供相容或 fallback
SUMMARY_SYSTEM_PROMPT = """你是一位財經新聞編輯，負責整理每日新聞摘要。

## 核心規則（必須嚴格遵守）

1. **禁止大幅刪減新聞數量**：每個來源必須保留 8-10 則新聞
2. **必須保留所有連結**：每則新聞都要有 [閱讀原文](URL) 的連結
3. **使用極度精簡格式**：僅「標題 + 一句話點評」

## 輸出格式

開頭先寫 2-3 句「🔥 AI 宏觀洞察」（聚焦虛擬貨幣影響）

然後每個來源用以下格式：

*📰 來源名稱*
• 標題內容 — 一句話點評 [→](連結)
• 標題內容 — 一句話點評 [→](連結)
...（每來源 8-10 則）

## 重要提醒
- 使用 Telegram Markdown 格式
- 標題用普通文字，不要加粗（節省字數）
- 點評限制在 15 字以內
- 連結格式：[→](https://完整URL)"""


def get_openai_client() -> OpenAI:
    """Initialize OpenAI client with API key from environment."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    return OpenAI(api_key=api_key)


def extract_news_from_content(client: OpenAI, source_name: str, source_url: str, content: str) -> list[dict]:
    """
    Extract structured news list from raw markdown content using GPT-4o-mini.
    
    Args:
        client: OpenAI client
        source_name: Name of the news source
        source_url: Base URL of the source for link completion
        content: Raw markdown content from scraper
        
    Returns:
        List of news items with title, link, description
    """
    try:
        truncated_content = content[:10000] if content else ""
        
        # Extract base URL for relative link completion
        from urllib.parse import urlparse
        parsed = urlparse(source_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": EXTRACTION_USER_PROMPT.format(
                    source_name=source_name,
                    source_url=source_url,
                    content=truncated_content,
                    base_url=base_url
                )}
            ],
            response_format={"type": "json_object"},
            max_tokens=3000,
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        news_list = result.get("news_list", [])
        
        # Post-process: ensure links are complete URLs
        for news in news_list:
            link = news.get("link", "")
            if link and not link.startswith("http"):
                if link.startswith("/"):
                    news["link"] = base_url + link
                else:
                    news["link"] = base_url + "/" + link
        
        return news_list[:15]
        
    except Exception as e:
        print(f"  ⚠️ Extraction error for {source_name}: {e}")
        return []


def process_all_sources(scraped_results: list[dict]) -> list[dict]:
    """
    Process all scraped sources to extract structured news.
    """
    client = get_openai_client()
    processed = []
    
    print(f"\n🧠 Extracting structured news from {len(scraped_results)} sources...")
    
    for result in scraped_results:
        if not result["success"] or not result["content"]:
            processed.append({**result, "news_list": []})
            continue
        
        print(f"  📋 Extracting from {result['name']}...")
        news_list = extract_news_from_content(
            client, 
            result["name"], 
            result["url"],
            result["content"]
        )
        
        processed.append({
            **result,
            "news_list": news_list
        })
        
        # Count links
        links_count = sum(1 for n in news_list if n.get("link"))
        print(f"     → Found {len(news_list)} news items ({links_count} with links)")
    
    total_news = sum(len(p["news_list"]) for p in processed)
    total_links = sum(sum(1 for n in p["news_list"] if n.get("link")) for p in processed)
    print(f"\n📊 Total: {total_news} news items, {total_links} with links")
    
    return processed


def _build_summary_user_prompt(processed_results: list[dict]) -> str:
    """組裝給 LLM 的輸入：每則新聞含 title, link, description, sources_confirming（若有）。"""
    parts = []
    for result in processed_results:
        if not result.get("news_list"):
            continue
        name = result.get("name", "")
        emoji = result.get("emoji", "📰")
        parts.append(f"\n## {emoji} {name}\n")
        for news in result["news_list"]:
            link = news.get("link", "")
            confirming = news.get("sources_confirming", [])
            extra = f" [多源確認：{', '.join(confirming)}]" if confirming else ""
            parts.append(f"- title: {news.get('title', '')}\n  description: {news.get('description', '')}\n  link: {link}{extra}\n")
    return "\n".join(parts) if parts else "（無新聞）"


SEP = "━━━━━━━━━━"

def _render_telegram_body(data: dict) -> str:
    """將結構化摘要轉成 Telegram 內文（含分隔符、標籤、連結）。"""
    lines = []

    # 宏觀洞察 4 行
    macro = data.get("macro_insight", {})
    am = macro.get("asset_mapping", {})
    asset_line = " ".join(f"{k}{am.get(k, '→')}" for k in ["美股", "黃金", "原油", "BTC"])
    lines.append("🔥 *宏觀洞察*")
    lines.append(f"風險溫度：{macro.get('risk_temperature', '中')}")
    lines.append(f"主驅動：{', '.join(macro.get('main_drivers', [])[:3])}")
    lines.append(f"資產映射：{asset_line}")
    lines.append(f"24h 關注：{' | '.join(macro.get('watch_24h', [])[:3])}")
    lines.append("")
    lines.append(SEP)
    lines.append("")

    # Top 5 必看
    lines.append("📌 *Top 5 必看*")
    for item in data.get("top5", [])[:5]:
        tag = item.get("tag", "💹市場")
        title = item.get("title", "")
        one = item.get("one_liner", "")
        link = item.get("link", "")
        link_md = f" [→]({link})" if link else ""
        lines.append(f"{tag} {title}")
        lines.append(f"  {one}{link_md}")
    lines.append("")
    lines.append(SEP)
    lines.append("")

    # 分來源摘要
    lines.append("📰 *分來源摘要*")
    per = data.get("per_source", {})
    for source_name, items in per.items():
        if not items:
            continue
        lines.append(f"*{source_name}*")
        for item in items[:5]:
            tag = item.get("tag", "💹市場")
            title = item.get("title", "")
            one = item.get("one_liner", "")
            link = item.get("link", "")
            link_md = f" [→]({link})" if link else ""
            conf = item.get("sources_confirming", [])
            conf_str = f" 多源確認：{', '.join(conf)}" if conf else ""
            lines.append(f"  {tag} {title}")
            lines.append(f"    {one}{link_md}{conf_str}")
        lines.append("")
    lines.append("")
    lines.append(SEP)
    lines.append("")

    # 明日跟蹤
    lines.append("📋 *明日跟蹤清單*")
    for t in data.get("tomorrow", [])[:3]:
        lines.append(f"  • {t}")
    return "\n".join(lines)


def generate_summary(processed_results: list[dict]) -> Optional[str]:
    """
    Generate AI summary (v2.2): 去重 → 結構化 LLM 輸出 → 組裝易讀 Telegram 內文。
    保留連結與多來源標註，單則長度由 notifier 分段控制。
    """
    try:
        # 去重（跨來源合併 + 多源確認）
        deduped = deduplicate_across_sources(processed_results)
        total_items = sum(len(r.get("news_list", [])) for r in deduped)
        if total_items == 0:
            return "⚠️ 今日無法取得任何新聞內容。"

        client = get_openai_client()
        user_content = f"""以下是今日從各大來源提取並已做跨來源去重的新聞（共 {total_items} 則）。
請依 schema 輸出 JSON：macro_insight、top5（最多 5 條）、per_source（每來源 3-5 條）、tomorrow（3 條）。
同一主題最多 4 條。必須保留每則的 link；若無連結則給空字串。
若輸入中某則新聞已標註「多源確認：A, B」，請在該條目的 sources_confirming 陣列中保留 ["A","B"]。

{_build_summary_user_prompt(deduped)}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT_V2},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            max_tokens=4000,
            temperature=0.4
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)

        # 補齊 top5 / per_source 的 link、sources_confirming（從 deduped 依標題比對）
        all_news = []
        for result in deduped:
            for news in result.get("news_list", []):
                all_news.append(news)

        def fill_link_and_confirm(item: dict) -> None:
            t = item.get("title", "")
            for news in all_news:
                if _title_similarity(t, news.get("title", "")) >= 0.5:
                    if not item.get("link") and news.get("link"):
                        item["link"] = news["link"]
                    if not item.get("sources_confirming") and news.get("sources_confirming"):
                        item["sources_confirming"] = news["sources_confirming"]
                    return

        for item in data.get("top5", []):
            fill_link_and_confirm(item)
        per = data.get("per_source", {})
        for result in deduped:
            name = result.get("name", "")
            if name not in per:
                continue
            for llm_item in per[name]:
                fill_link_and_confirm(llm_item)

        body = _render_telegram_body(data)
        return body

    except json.JSONDecodeError as e:
        print(f"❌ Summary JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"❌ Summary generation error: {e}")
        return None


def format_telegram_header(date_str: str, stats: dict) -> str:
    """Header：日期、來源數、總條數（可選 credits）。"""
    credits = f" | {stats.get('credits_used', '')} 點數" if stats.get("credits_used") else ""
    return f"""📰 *全球財經日報* | {date_str}
📊 {stats['sources_count']} 來源 | {stats['news_count']} 則新聞{credits}

{SEP}
"""


def format_telegram_footer() -> str:
    """Format the Telegram message footer."""
    return "\n\n---\n_🤖 News Monitor Bot v2.2_"


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    mock_results = [
        {
            "name": "Test Source",
            "url": "https://example.com",
            "emoji": "📰",
            "description": "Test",
            "content": "# Headlines\n- [Fed announces rate decision](https://example.com/fed)\n- [Bitcoin ETF sees record inflows](https://example.com/btc)\n- [Apple delays new product](https://example.com/apple)",
            "success": True
        }
    ]
    
    processed = process_all_sources(mock_results)
    print(json.dumps(processed, indent=2, ensure_ascii=False))
