"""
News Monitor v2.1 - OpenAI Summarizer Module
Fixed: Link preservation, news quantity retention (40-50 items), concise format.
"""

import os
import json
from openai import OpenAI
from typing import Optional


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


# v2.1 更新：保留更多新聞的精簡摘要 Prompt
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


def generate_summary(processed_results: list[dict]) -> Optional[str]:
    """
    Generate AI summary preserving all news with links.
    v2.1: Keep 8-10 items per source, concise format.
    """
    try:
        client = get_openai_client()
        
        # Format all news data with links
        news_content = []
        for result in processed_results:
            if result["news_list"]:
                source_news = f"\n## {result['emoji']} {result['name']}\n"
                for i, news in enumerate(result["news_list"], 1):
                    link = news.get('link', '')
                    link_md = f" [連結]({link})" if link else ""
                    source_news += f"{i}. {news['title']}{link_md}\n   {news.get('description', '')}\n"
                news_content.append(source_news)
        
        if not news_content:
            return "⚠️ 今日無法取得任何新聞內容。"
        
        user_prompt = f"""以下是今日從各大新聞網站提取的新聞列表（共 {sum(len(r['news_list']) for r in processed_results)} 則）。

請按照系統提示的格式整理摘要，必須：
1. 每個來源保留 8-10 則新聞
2. 保留所有新聞連結
3. 使用極度精簡的格式

{''.join(news_content)}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=4000,
            temperature=0.5
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"❌ Summary generation error: {e}")
        return None


def format_telegram_header(date_str: str, stats: dict) -> str:
    """Format the Telegram message header."""
    return f"""📰 *全球財經日報* | {date_str}

📊 {stats['sources_count']} 來源 | {stats['news_count']} 則新聞 | {stats['credits_used']} 點數

---

"""


def format_telegram_footer() -> str:
    """Format the Telegram message footer."""
    return "\n\n---\n_🤖 News Monitor Bot v2.1_"


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
