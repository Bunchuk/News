"""
Конфігурація новинного бота.

Тут задаються RSS-джерела за категоріями та основні параметри.
Стрічки можна вільно додавати/прибирати — код стійкий до недоступних фідів.
"""

import os
from zoneinfo import ZoneInfo

# --- Часовий пояс ---
TZ = ZoneInfo("Europe/Kyiv")

# Скільки годин назад брати новини (біля половини доби, з невеликим перекриттям,
# щоб між ранковим і вечірнім випуском не було "дірок").
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "13"))

# Обмеження, щоб промпт для LLM не роздувався
MAX_ITEMS_PER_CATEGORY = int(os.getenv("MAX_ITEMS_PER_CATEGORY", "25"))

# Ліміт довжини одного повідомлення в Telegram (Telegram ріже на 4096)
TELEGRAM_MAX_CHARS = 3900

# Файл SQLite-пам'яті переглянутих новин (персиститься через actions/cache)
DB_PATH = os.getenv("DB_PATH", "state.db")

# --- RSS-джерела ---
# category -> list of (назва_джерела, url)
FEEDS = {
    "Україна та світ": [
        ("Українська правда", "https://www.pravda.com.ua/rss/view_mainnews/"),
        ("Європейська правда", "https://www.eurointegration.com.ua/rss/"),
        ("Укрінформ", "https://www.ukrinform.ua/rss/block-lastnews"),
        ("Kyiv Independent", "https://kyivindependent.com/feed/"),
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ],
    "Технології та AI": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        ("Hacker News", "https://hnrss.org/frontpage"),
        ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ],
}

# Емодзі для заголовків секцій у підсумковому дайджесті
CATEGORY_EMOJI = {
    "Україна та світ": "🇺🇦",
    "Технології та AI": "🤖",
}

# --- Моделі LLM (можна перевизначити через env) ---
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
