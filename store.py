"""
Пам'ять переглянутих новин (SQLite), щоб та сама подія не потрапляла
і в ранковий, і у вечірній випуск.

Логіка:
- select_new() лише ЧИТАЄ БД і повертає, що з зібраного ще не надсилалось;
- mark_seen() записує новини як переглянуті — викликається ТІЛЬКИ після
  успішної відправки, щоб при збої LLM/Telegram новини не губилися;
- purge_old() чистить старі записи, щоб файл не ріс.

На GitHub Actions файл БД персиститься між запусками через actions/cache
(див. .github/workflows/news-digest.yml).
"""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from fetcher import _norm_title

log = logging.getLogger("store")

# Скільки тримати історію. Вікно новин ~13 год, тож 3 днів із запасом достатньо.
RETENTION_DAYS = 3


def connect(path: str) -> sqlite3.Connection:
    """Відкриває БД і створює таблицю, якщо її ще немає."""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen (
            link       TEXT,
            title_norm TEXT,
            seen_at    TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_link ON seen(link)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_title ON seen(title_norm)")
    conn.commit()
    return conn


def purge_old(conn: sqlite3.Connection, days: int = RETENTION_DAYS) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn.execute("DELETE FROM seen WHERE seen_at < ?", (cutoff,))
    conn.commit()


def _load_seen(conn: sqlite3.Connection):
    links, titles = set(), set()
    for link, title_norm in conn.execute("SELECT link, title_norm FROM seen"):
        if link:
            links.add(link)
        if title_norm:
            titles.add(title_norm)
    return links, titles


def select_new(conn: sqlite3.Connection, news: dict):
    """
    Повертає (news_відфільтрований, плоский_список_нових).
    БД не змінює — новина вважається дублем, якщо збігається посилання
    АБО нормалізований заголовок (те саме, що й у fetcher).
    """
    seen_links, seen_titles = _load_seen(conn)
    batch_links, batch_titles = set(), set()  # щоб не дублювати в межах одного запуску
    filtered: dict = {}
    flat: list = []

    for category, items in news.items():
        keep = []
        for it in items:
            link = it.get("link") or ""
            tnorm = _norm_title(it.get("title", ""))
            if link and (link in seen_links or link in batch_links):
                continue
            if tnorm and (tnorm in seen_titles or tnorm in batch_titles):
                continue
            batch_links.add(link)
            batch_titles.add(tnorm)
            keep.append(it)
            flat.append(it)
        filtered[category] = keep

    return filtered, flat


def mark_seen(conn: sqlite3.Connection, items: list) -> None:
    """Записує надіслані новини як переглянуті."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (it.get("link") or "", _norm_title(it.get("title", "")), now)
        for it in items
    ]
    conn.executemany(
        "INSERT INTO seen (link, title_norm, seen_at) VALUES (?, ?, ?)", rows
    )
    conn.commit()
