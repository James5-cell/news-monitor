"""
News Monitor v2.1 - Telegram Notifier Module
Fixed: Auto-split long messages at 3500 chars for complete delivery.
"""

import os
import requests
from typing import Optional


# Telegram message length limits
MAX_MESSAGE_LENGTH = 4096
SAFE_SPLIT_LENGTH = 3500  # Split before reaching limit


def get_telegram_config() -> tuple[str, str]:
    """Get Telegram bot token and chat ID from environment."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID environment variable is not set")
    
    return bot_token, chat_id


def send_telegram_message(message: str, parse_mode: str = "Markdown") -> bool:
    """
    Send a single message to Telegram.
    
    Args:
        message: Message text (max 4096 chars)
        parse_mode: "Markdown" or "HTML"
        
    Returns:
        True if message sent successfully
    """
    try:
        bot_token, chat_id = get_telegram_config()
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        response = requests.post(url, json=payload, timeout=30)
        
        # Handle Markdown parsing errors by falling back to plain text
        if response.status_code == 400:
            result = response.json()
            if "can't parse entities" in result.get("description", "").lower():
                print("  ⚠️ Markdown parsing failed, sending as plain text...")
                payload["parse_mode"] = None
                response = requests.post(url, json=payload, timeout=30)
        
        response.raise_for_status()
        
        result = response.json()
        if result.get("ok"):
            return True
        else:
            print(f"  ❌ Telegram API error: {result.get('description')}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def split_message_smart(message: str, max_length: int = SAFE_SPLIT_LENGTH) -> list[str]:
    """
    Split a long message into chunks, preserving formatting.
    
    Splitting strategy:
    1. Try to split at source section boundaries (📰, 📊, 🏛️, etc.)
    2. Fall back to splitting at double newlines
    3. Last resort: split at single newlines
    
    Args:
        message: Full message text
        max_length: Maximum characters per chunk
        
    Returns:
        List of message chunks
    """
    if len(message) <= max_length:
        return [message]
    
    chunks = []
    
    # Try to split by source emoji markers
    import re
    source_pattern = r'\n(?=\*?[📰🏛️💹📊🔬])'
    sections = re.split(source_pattern, message)
    
    current_chunk = ""
    
    for section in sections:
        # If adding this section exceeds limit
        if len(current_chunk) + len(section) > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # If single section is too long, split it further
            if len(section) > max_length:
                sub_chunks = split_by_newlines(section, max_length)
                chunks.extend(sub_chunks[:-1])
                current_chunk = sub_chunks[-1] if sub_chunks else ""
            else:
                current_chunk = section
        else:
            current_chunk += section
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


def split_by_newlines(text: str, max_length: int) -> list[str]:
    """
    Split text by newlines when section splitting isn't enough.
    """
    chunks = []
    current_chunk = ""
    
    for line in text.split("\n"):
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


def send_long_message(message: str) -> bool:
    """
    Send a potentially long message by auto-splitting.
    
    v2.1: Automatically splits at 3500 chars to ensure all 
    news items are delivered.
    
    Args:
        message: Full message text (can exceed 4096 chars)
        
    Returns:
        True if all chunks sent successfully
    """
    chunks = split_message_smart(message, SAFE_SPLIT_LENGTH)
    
    total_chunks = len(chunks)
    if total_chunks > 1:
        print(f"  📨 Message split into {total_chunks} parts")
    
    success_count = 0
    
    for i, chunk in enumerate(chunks):
        # Add part indicator for multi-part messages
        if total_chunks > 1:
            part_indicator = f"[{i+1}/{total_chunks}]\n\n" if i > 0 else ""
            chunk = part_indicator + chunk
        
        print(f"  → Sending part {i+1}/{total_chunks} ({len(chunk)} chars)...")
        
        if send_telegram_message(chunk):
            success_count += 1
        else:
            print(f"  ⚠️ Failed to send part {i+1}")
    
    return success_count == total_chunks


def send_error_notification(error_message: str) -> bool:
    """Send an error notification to Telegram."""
    message = f"⚠️ *News Monitor Error*\n\n{error_message}"
    return send_telegram_message(message)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test with a long message
    test_message = """📰 *全球財經日報* | 2026-01-31

📊 5 來源 | 60 則新聞 | 5 點數

---

🔥 *AI 宏觀洞察*
Fed 維持利率不變利好風險資產，科技股走強對加密市場形成正面支撐。

*📰 WSJ*
• Fed holds rates steady — 利好風險資產 [→](https://wsj.com/1)
• Tech stocks surge — 科技領漲 [→](https://wsj.com/2)
• AI investment boom — 資金湧入 [→](https://wsj.com/3)

*🏛️ FT*
• Bitcoin ETF inflows — 機構買入中 [→](https://ft.com/1)
• UK inflation falls — 通膨降溫 [→](https://ft.com/2)

---
_🤖 News Monitor Bot v2.1_"""

    print(f"Test message length: {len(test_message)}")
    
    # Test splitting
    chunks = split_message_smart(test_message * 3, SAFE_SPLIT_LENGTH)
    print(f"Would split into {len(chunks)} chunks")
    
    # Actually send
    # send_long_message(test_message)
