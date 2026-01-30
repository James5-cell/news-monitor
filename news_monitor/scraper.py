"""
News Monitor v2 - Firecrawl Scraper Module
Upgraded with structured extraction for 10-15 news items per site.
Uses 5 sites only, with 2s rate limiting for stability.
"""

import os
import time
from typing import Optional
from firecrawl import Firecrawl


# 5 platforms only - optimized for 5 credits/day, 150 credits/30 days
# Each platform's main news page (combined business + tech content)
NEWS_SOURCES = [
    {
        "name": "WSJ",
        "url": "https://www.wsj.com/",
        "emoji": "📰",
        "description": "Wall Street Journal - Business & Tech"
    },
    {
        "name": "FT",
        "url": "https://www.ft.com/",
        "emoji": "🏛️",
        "description": "Financial Times - Companies & Technology"
    },
    {
        "name": "Bloomberg",
        "url": "https://www.bloomberg.com/",
        "emoji": "💹",
        "description": "Bloomberg - Business & Technology"
    },
    {
        "name": "Reuters",
        "url": "https://www.reuters.com/",
        "emoji": "📊",
        "description": "Reuters - World Business & Tech"
    },
    {
        "name": "Economist",
        "url": "https://www.economist.com/",
        "emoji": "🔬",
        "description": "The Economist - Business & Science"
    },
]

# Rate limiting: 2 seconds between requests (respects 2 concurrent request limit)
REQUEST_DELAY_SECONDS = 2


def get_firecrawl_client() -> Firecrawl:
    """Initialize Firecrawl client with API key from environment."""
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise ValueError("FIRECRAWL_API_KEY environment variable is not set")
    return Firecrawl(api_key=api_key)


def scrape_single_site(client: Firecrawl, url: str) -> Optional[str]:
    """
    Scrape a single news site using Firecrawl.
    
    Uses onlyMainContent=True to get clean content for LLM extraction.
    Each call consumes exactly 1 credit.
    
    Args:
        client: Firecrawl instance
        url: Target URL to scrape
        
    Returns:
        Markdown content of the page, or None if scraping fails
    """
    try:
        result = client.scrape(
            url=url,
            formats=["markdown"],
            only_main_content=True
        )
        return result.markdown if result and result.markdown else None
    except Exception as e:
        print(f"  ❌ Error scraping {url}: {e}")
        return None


def scrape_all_sources() -> list[dict]:
    """
    Scrape all configured news sources with rate limiting.
    
    Implements:
    - Sequential scraping (no parallel requests)
    - 2 second delay between requests
    - Error handling per source
    
    Returns:
        List of dicts containing source info and scraped content
    """
    client = get_firecrawl_client()
    results = []
    
    print(f"📡 Starting scrape of {len(NEWS_SOURCES)} sources...")
    print(f"⏱️  Rate limit: {REQUEST_DELAY_SECONDS}s between requests")
    
    for i, source in enumerate(NEWS_SOURCES):
        print(f"\n[{i+1}/{len(NEWS_SOURCES)}] Scraping {source['name']}...")
        
        content = scrape_single_site(client, source["url"])
        
        results.append({
            "name": source["name"],
            "url": source["url"],
            "emoji": source["emoji"],
            "description": source["description"],
            "content": content,
            "success": content is not None
        })
        
        if content:
            print(f"  ✅ Success: {len(content)} chars")
        
        # Rate limiting: wait before next request (skip for last one)
        if i < len(NEWS_SOURCES) - 1:
            print(f"  ⏳ Waiting {REQUEST_DELAY_SECONDS}s...")
            time.sleep(REQUEST_DELAY_SECONDS)
    
    successful = sum(1 for r in results if r["success"])
    print(f"\n📊 Scraping complete: {successful}/{len(NEWS_SOURCES)} sources successful")
    print(f"💳 Credits consumed: {successful}")
    
    return results


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    results = scrape_all_sources()
    for r in results:
        status = "✅" if r["success"] else "❌"
        content_len = len(r["content"]) if r["content"] else 0
        print(f"{status} {r['name']}: {content_len} chars")
