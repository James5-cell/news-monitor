"""
News Monitor v2.2 - Telegram Notifier Module
- Segment at 2500-3000 chars for readability
- Each segment has section title (no bare "2/3")
- Split only at section boundaries (━━━━━━━━━━)
"""

import os
import re
import requests
from typing import Optional


# Telegram message length limits
MAX_MESSAGE_LENGTH = 4096
# 單則控制在 2500-3000 字內，取中間值
SAFE_SPLIT_LENGTH = 2800


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


# 與 summarizer 一致的分隔符，用於在邊界切段
SECTION_SEP = "━━━━━━━━━━"


def split_message_smart(message: str, max_length: int = SAFE_SPLIT_LENGTH) -> list[str]:
    """
    在段落邊界切分長訊息，避免「2/3、3/3」孤立。
    優先於 SECTION_SEP 切分，單段過長再以換行切。
    """
    if len(message) <= max_length:
        return [message]

    # 以「分隔符 + 換行」切區塊；第一塊為標題+宏觀+Top5，其後為分來源/明日
    raw_blocks = message.split("\n" + SECTION_SEP + "\n")
    blocks = [b.strip() for b in raw_blocks if b.strip()]

    if len(blocks) <= 1 and len(message) > max_length:
        blocks = [message]

    chunks = []
    current = ""

    for block in blocks:
        need_new_chunk = len(current) + len(block) + 4 > max_length
        if need_new_chunk and current.strip():
            chunks.append(current.strip())
            current = ""
        if len(block) > max_length:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            sub = split_by_newlines(block, max_length)
            chunks.extend(sub[:-1])
            current = sub[-1] if sub else ""
        else:
            current = (current + "\n\n" + SECTION_SEP + "\n\n" + block) if current else block

    if current.strip():
        chunks.append(current.strip())

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


def _segment_title(segment_index: int, total: int) -> str:
    """多段時，第 2 段起加上段落標題，避免孤立「2/3」。"""
    if total <= 1 or segment_index == 0:
        return ""
    labels = ["頭條與宏觀", "分來源摘要", "明日跟蹤"]
    label = labels[min(segment_index, len(labels) - 1)]
    if segment_index >= len(labels):
        label = f"續（{segment_index + 1}/{total}）"
    return f"📰 *全球財經日報* · {label}\n\n"


def send_long_message(message: str) -> bool:
    """
    自動分段發送：單則 2500-3000 字，每段皆有段落標題。
    """
    chunks = split_message_smart(message, SAFE_SPLIT_LENGTH)

    total_chunks = len(chunks)
    if total_chunks > 1:
        print(f"  📨 Message split into {total_chunks} parts (max ~{SAFE_SPLIT_LENGTH} chars each)")

    success_count = 0
    for i, chunk in enumerate(chunks):
        # 第 2 段起加段落標題，避免僅顯示「2/3」
        if total_chunks > 1 and i > 0:
            chunk = _segment_title(i, total_chunks) + chunk

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
