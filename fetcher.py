"""
Збір новин з RSS-стрічок.

- Кожна стрічка парситься окремо й у try/except: якщо джерело недоступне
  або віддало сміття — просто пропускаємо його, а не валимо весь запуск.
- Беремо лише свіжі записи (за LOOKBACK_HOURS).
- Прибираємо дублікати за посиланням і за нормалізованим заголовком.
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from time import mktime

import feedparser

from config import FEEDS, LOOKBACK_HOURS, MAX_ITEMS_PER_CATEGORY

log = logging.getLogger("fetcher")

# Прикидаємось звичайним браузером — деякі сайти інакше віддають 403
USER_AGENT = (
    "Mozilla/5.0 (compatible; NewsDigestBot/1.0; +https://github.com/)"
)


def _clean(text: str) -> str:
    """Прибирає HTML-теги та зайві пробіли з тексту опису."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # зняти теги
    text = html.unescape(text)                     # &amp; -> &
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _entry_time(entry):
    """Повертає час публікації запису у UTC або None, якщо не розпарсити."""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime.fromtimestamp(mktime(t), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def _norm_title(title: str) -> str:
    """Нормалізує заголовок для дедуплікації."""
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


def fetch_category(category: str, sources) -> list[dict]:
    """Збирає свіжі новини по одній категорії."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items: list[dict] = []
    seen_links: set[str] = set()
    seen_titles: set[str] = set()

    for source_name, url in sources:
        try:
            parsed = feedparser.parse(url, agent=USER_AGENT)
            if parsed.bozo and not parsed.entries:
                log.warning("Стрічка %s (%s) не розпарсилась", source_name, url)
                continue

            for entry in parsed.entries:
                published = _entry_time(entry)
                # Якщо дата є і вона стара — пропускаємо.
                # Якщо дати немає — обережно беремо (деякі фіди завжди свіжі).
                if published is not None and published < cutoff:
                    continue

                link = (entry.get("link") or "").strip()
                title = _clean(entry.get("title", ""))
                if not title:
                    continue

                nt = _norm_title(title)
                if (link and link in seen_links) or (nt and nt in seen_titles):
                    continue
                seen_links.add(link)
                seen_titles.add(nt)

                summary = _clean(entry.get("summary", ""))[:400]

                items.append({
                    "source": source_name,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": published,
                })
        except Exception as e:  # noqa: BLE001 — свідомо ковтаємо будь-яку помилку джерела
            log.warning("Помилка джерела %s: %s", source_name, e)
            continue

    # Сортуємо: свіжіші зверху (записи без дати — в кінець)
    items.sort(
        key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return items[:MAX_ITEMS_PER_CATEGORY]


def fetch_all() -> dict[str, list[dict]]:
    """Повертає {категорія: [новини...]} по всіх категоріях з config.FEEDS."""
    result = {}
    for category, sources in FEEDS.items():
        news = fetch_category(category, sources)
        log.info("Категорія «%s»: зібрано %d новин", category, len(news))
        result[category] = news
    return result
