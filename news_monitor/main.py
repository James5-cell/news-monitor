"""
News Monitor v2.1 - Main Orchestrator
Fixed: Link preservation, 40-50 news output, auto-split messaging.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from scraper import scrape_all_sources
from summarizer import (
    process_all_sources, 
    generate_summary, 
    format_telegram_header,
    format_telegram_footer
)
from notifier import send_long_message, send_error_notification


def get_taipei_date() -> str:
    """Get current date in Taipei timezone (UTC+8)."""
    taipei_tz = timezone(timedelta(hours=8))
    now = datetime.now(taipei_tz)
    return now.strftime("%Y-%m-%d")


def run_pipeline() -> bool:
    """
    Execute the v2.1 news monitoring pipeline.
    
    Fixes in v2.1:
    - Link preservation in extraction and summary
    - 40-50 news items retained (8-10 per source)
    - Auto-split for long Telegram messages
    
    Returns:
        True if pipeline completed successfully
    """
    print("=" * 60)
    print(f"🚀 News Monitor Pipeline v2.1 Started")
    print(f"📅 Date: {get_taipei_date()}")
    print("=" * 60)
    
    # Step 1: Scrape news sources
    print("\n📥 Step 1: Scraping news sources...")
    try:
        scraped_results = scrape_all_sources()
        successful_scrapes = sum(1 for r in scraped_results if r["success"])
        
        if successful_scrapes == 0:
            error_msg = "All scraping attempts failed. Check Firecrawl API."
            print(f"❌ {error_msg}")
            send_error_notification(error_msg)
            return False
            
    except Exception as e:
        error_msg = f"Scraping error: {str(e)}"
        print(f"❌ {error_msg}")
        send_error_notification(error_msg)
        return False
    
    # Step 2: Extract structured news with links
    print("\n🧠 Step 2: Extracting structured news (with links)...")
    try:
        processed_results = process_all_sources(scraped_results)
        total_news = sum(len(p.get("news_list", [])) for p in processed_results)
        total_links = sum(
            sum(1 for n in p.get("news_list", []) if n.get("link")) 
            for p in processed_results
        )
        
        print(f"\n📊 Extraction complete: {total_news} news, {total_links} with links")
        
        if total_news == 0:
            error_msg = "No news items extracted."
            print(f"⚠️ {error_msg}")
            
    except Exception as e:
        error_msg = f"Extraction error: {str(e)}"
        print(f"❌ {error_msg}")
        send_error_notification(error_msg)
        return False
    
    # Step 3: Generate AI summary (preserving 40-50 items)
    print("\n✍️ Step 3: Generating AI summary (preserving links)...")
    try:
        summary = generate_summary(processed_results)
        
        if not summary:
            error_msg = "Failed to generate summary."
            print(f"❌ {error_msg}")
            send_error_notification(error_msg)
            return False
        
        # Count links in output
        link_count = summary.count("[→]")
        print(f"✅ Summary generated: {len(summary)} chars, {link_count} links preserved")
        
    except Exception as e:
        error_msg = f"Summarization error: {str(e)}"
        print(f"❌ {error_msg}")
        send_error_notification(error_msg)
        return False
    
    # Step 4: Send to Telegram (with auto-split)
    print("\n📤 Step 4: Sending to Telegram (auto-split enabled)...")
    try:
        stats = {
            "sources_count": successful_scrapes,
            "news_count": total_news,
            "credits_used": successful_scrapes
        }
        
        # Build full message
        header = format_telegram_header(get_taipei_date(), stats)
        footer = format_telegram_footer()
        final_message = header + summary + footer
        
        print(f"  📝 Total message length: {len(final_message)} chars")
        
        success = send_long_message(final_message)
        
        if success:
            print("✅ All messages sent successfully")
        else:
            print("⚠️ Some message parts may have failed")
            
    except Exception as e:
        error_msg = f"Notification error: {str(e)}"
        print(f"❌ {error_msg}")
        return False
    
    # Final Summary
    print("\n" + "=" * 60)
    print("📊 Pipeline v2.1 Summary:")
    print(f"   • Sources scraped: {successful_scrapes}/5")
    print(f"   • News extracted: {total_news}")
    print(f"   • Links preserved: {total_links}")
    print(f"   • Output links: {link_count}")
    print(f"   • Credits used: {successful_scrapes}")
    print("=" * 60)
    
    return True


def main():
    """Main entry point."""
    load_dotenv()
    
    required_vars = [
        "FIRECRAWL_API_KEY",
        "OPENAI_API_KEY", 
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID"
    ]
    
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    
    success = run_pipeline()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
