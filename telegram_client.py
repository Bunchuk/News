"""
Відправка повідомлень у Telegram.

- Ріже довгий текст на частини < 4096 символів (по абзацах).
- Якщо Telegram відхилив HTML (помилка 400) — знімає теги й шле як звичайний текст,
  щоб дайджест точно дійшов.
"""

import logging
import re

import requests

from config import TELEGRAM_MAX_CHARS

log = logging.getLogger("telegram")

API = "https://api.telegram.org/bot{token}/sendMessage"


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def _split(text: str, limit: int = TELEGRAM_MAX_CHARS) -> list[str]:
    """Розбиває текст на шматки по абзацах, не перевищуючи limit."""
    if len(text) <= limit:
        return [text]
    parts, buf = [], ""
    for para in text.split("\n\n"):
        candidate = f"{buf}\n\n{para}" if buf else para
        if len(candidate) <= limit:
            buf = candidate
        else:
            if buf:
                parts.append(buf)
            # якщо один абзац сам довший за ліміт — ріжемо жорстко
            while len(para) > limit:
                parts.append(para[:limit])
                para = para[limit:]
            buf = para
    if buf:
        parts.append(buf)
    return parts


def _send_one(token: str, chat_id: str, text: str) -> None:
    url = API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=30)
    if r.status_code == 400:
        # Найімовірніше — битий HTML. Шлемо як plain text.
        log.warning("HTML відхилено (%s), шлю без розмітки", r.text[:200])
        payload.pop("parse_mode")
        payload["text"] = _strip_tags(text)
        r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()


def send(token: str, chat_id: str, text: str) -> None:
    """Відправляє дайджест (з розбиттям за потреби)."""
    for i, part in enumerate(_split(text), 1):
        _send_one(token, chat_id, part)
        log.info("Відправлено частину %d", i)
