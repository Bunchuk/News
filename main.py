"""
Точка входу новинного бота.

Запуск:
    python main.py            # слот визначиться автоматично за часом Києва
    python main.py --slot morning
    python main.py --slot evening

Потрібні змінні оточення:
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    + хоча б один з: ANTHROPIC_API_KEY / GEMINI_API_KEY / GROQ_API_KEY
"""

import argparse
import logging
import os
import sys
from datetime import datetime

import store
from config import DB_PATH, TZ
from fetcher import fetch_all
from summarizer import summarize
from telegram_client import send

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


def resolve_slot(explicit: str | None) -> str:
    """Визначає слот: явний аргумент/env або автоматично за годиною Києва."""
    slot = explicit or os.getenv("SLOT")
    if slot in ("morning", "evening"):
        return slot
    hour = datetime.now(TZ).hour
    return "morning" if hour < 14 else "evening"


SLOT_LABELS = {"morning": "Ранковий випуск", "evening": "Вечірній випуск"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=["morning", "evening"], default=None)
    args = ap.parse_args()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.error("Немає TELEGRAM_BOT_TOKEN або TELEGRAM_CHAT_ID")
        return 1

    slot = resolve_slot(args.slot)
    now = datetime.now(TZ)
    slot_label = SLOT_LABELS[slot]
    date_label = now.strftime("%d.%m.%Y")
    log.info("Слот: %s (%s)", slot, date_label)

    news = fetch_all()
    total = sum(len(v) for v in news.values())
    if total == 0:
        log.warning("Свіжих новин не знайдено — нічого не надсилаю")
        return 0

    # Дедуплікація між випусками: лишаємо тільки те, що ще не надсилалось.
    conn = store.connect(DB_PATH)
    store.purge_old(conn)
    news, new_items = store.select_new(conn, news)
    log.info("Нових (не надсиланих раніше): %d із %d", len(new_items), total)
    if not new_items:
        log.info("З минулого випуску нічого нового — пропускаю")
        conn.close()
        return 0

    try:
        digest = summarize(slot_label, date_label, news)
    except Exception as e:  # noqa: BLE001
        log.error("Не вдалося згенерувати дайджест: %s", e)
        conn.close()  # НЕ позначаємо як переглянуте — новини лишаться на наступний запуск
        return 2

    send(token, chat_id, digest)
    store.mark_seen(conn, new_items)   # позначаємо переглянутим лише після успішної відправки
    conn.close()
    log.info("Готово ✅ (нових новин: %d)", len(new_items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
