# 🌐 Global News Monitor Bot

A lightweight, budget-conscious news monitoring system that scrapes top financial news sites daily and delivers AI-curated summaries to Telegram with full article links.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![Firecrawl](https://img.shields.io/badge/Firecrawl-API-orange.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-green.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)

## ✨ Features

- **📰 5 Premium News Sources**: WSJ, Financial Times, Bloomberg, Reuters, The Economist
- **🧠 Structured AI Extraction**: Extracts 10-15 news items per source with titles, descriptions, and links
- **🔗 Link Preservation**: All original article URLs are retained in the output
- **💬 Telegram Delivery**: Auto-splits long messages for complete delivery
- **💰 Credit Optimized**: Only 5 Firecrawl credits per day (500 credits = 100 days)
- **⏰ GitHub Actions**: Automated daily execution at 08:00 Taipei time

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Firecrawl     │────▶│    OpenAI       │────▶│    Telegram     │
│   (Scraping)    │     │  (Extraction +  │     │   (Delivery)    │
│   5 credits/day │     │   Summarizing)  │     │   Auto-split    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## 📁 Project Structure

```
news_monitor/
├── main.py           # Pipeline orchestrator
├── scraper.py        # Firecrawl API wrapper (5 sites, 2s rate limit)
├── summarizer.py     # GPT-4o-mini extraction & summary
├── notifier.py       # Telegram Bot API with auto-split
├── requirements.txt  # Python dependencies
├── .env.example      # Environment template
└── .env              # Your API keys (gitignored)

.github/
└── workflows/
    └── news_monitor.yml  # Daily cron job (UTC 00:00)
```

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/news-monitor.git
cd news-monitor/news_monitor
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
FIRECRAWL_API_KEY=fc-xxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Run Locally

```bash
python main.py
```

## 🔑 API Keys Setup

| Service | Get Key | Free Tier |
|---------|---------|-----------|
| Firecrawl | [firecrawl.dev](https://www.firecrawl.dev/) | 500 credits one-time |
| OpenAI | [platform.openai.com](https://platform.openai.com/) | Pay-as-you-go (~$0.01/run) |
| Telegram | [@BotFather](https://t.me/BotFather) | Free |

### Getting Your Telegram Chat ID

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Send `/start` to your bot
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Find your `chat.id` in the response

## ⚙️ GitHub Actions Setup

### 1. Add Repository Secrets

Go to **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:
- `FIRECRAWL_API_KEY`
- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 2. Enable Workflow

The workflow runs automatically at:
- **Schedule**: Daily at UTC 00:00 (08:00 Taipei)
- **Manual**: Actions → Daily News Monitor → Run workflow

## 📊 Output Example

```
📰 Global Financial Daily | 2026-01-31

📊 5 sources | 60 news | 5 credits

---

🔥 AI Macro Insight
Fed's dovish stance supports risk assets. Tech sector strength 
signals positive momentum for crypto markets.

📰 WSJ
• Fed Holds Rates Steady — Risk assets rally [→](https://wsj.com/...)
• AI Investment Surge — Record funding [→](https://wsj.com/...)
• Apple Delays AR Launch — 2027 timeline [→](https://wsj.com/...)

🏛️ FT
• Bitcoin ETF Inflows — Institutional buying [→](https://ft.com/...)
• UK Inflation Falls — BoE may cut [→](https://ft.com/...)

...
```

## 💰 Credit Consumption

| Item | Value |
|------|-------|
| Daily consumption | 5 credits |
| 30-day total | 150 credits |
| Free tier (500) runway | **100 days** |

## 🛠️ Customization

### Change News Sources

Edit `scraper.py`:

```python
NEWS_SOURCES = [
    {"name": "Your Source", "url": "https://...", "emoji": "📰"},
    # Add more sources
]
```

### Modify AI Prompts

Edit `summarizer.py`:
- `EXTRACTION_SYSTEM_PROMPT` - How to extract news
- `SUMMARY_SYSTEM_PROMPT` - How to summarize

### Adjust Rate Limiting

```python
REQUEST_DELAY_SECONDS = 2  # Increase if hitting rate limits
```

## 📝 License

MIT License - See [LICENSE](LICENSE)

## 🙏 Credits

- [Firecrawl](https://www.firecrawl.dev/) - Web scraping API
- [OpenAI](https://openai.com/) - GPT-4o-mini
- Original inspiration from [Trend Finder](https://github.com/mendableai/trend-finder)
