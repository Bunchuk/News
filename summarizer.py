"""
Формування дайджесту через LLM з триступеневим фолбеком:
Claude -> Gemini -> Groq (та сама схема, що й у біржового бота).

На вхід — зібрані новини, на вихід — готовий текст у Telegram-HTML.
"""

import logging
import os

from config import CATEGORY_EMOJI, CLAUDE_MODEL, GEMINI_MODEL, GROQ_MODEL

log = logging.getLogger("summarizer")

SYSTEM_PROMPT = (
    "Ти — редактор новинного дайджесту для українського читача, якого цікавлять "
    "війна в Україні + геополітика та технології/AI. Пишеш стисло, по суті, "
    "без води й без клікбейту, українською мовою."
)


def _build_user_prompt(slot_label: str, date_label: str, news: dict) -> str:
    """Готує текст запиту до LLM зі списком новин."""
    blocks = []
    for category, items in news.items():
        if not items:
            blocks.append(f"### {category}\n(свіжих новин немає)")
            continue
        lines = []
        for it in items:
            piece = f"- [{it['source']}] {it['title']}"
            if it["summary"]:
                piece += f" — {it['summary']}"
            if it["link"]:
                piece += f" | {it['link']}"
            lines.append(piece)
        blocks.append(f"### {category}\n" + "\n".join(lines))

    news_text = "\n\n".join(blocks)

    fmt_rules = "\n".join(
        f"«{cat}» → заголовок секції «{CATEGORY_EMOJI.get(cat, '•')} <b>{cat}</b>»"
        for cat in news.keys()
    )

    return f"""Нижче — сирі новини за останні години, згруповані за категоріями.
Зроби з них короткий дайджест ({slot_label}, {date_label}).

ВИМОГИ:
- Почни з одного рядка-шапки: «<b>🗞 Новинна сводка • {slot_label} • {date_label}</b>».
- Далі — секції за категоріями в такому вигляді:
{fmt_rules}
- У кожній секції 4–7 пунктів, найважливіше зверху.
- Об'єднуй новини про одну й ту саму подію з різних джерел в один пункт.
- Кожен пункт — 1–2 речення. У кінці пункту в дужках назви джерело, напр. (BBC).
- Прибирай дрібне й прохідне, лишай реально значуще.
- Якщо в категорії свіжих новин немає — коротко напиши про це одним рядком.
- Мова — українська.

ФОРМАТУВАННЯ (важливо, це піде напряму в Telegram):
- Дозволені ТІЛЬКИ теги <b>, <i> та <a href="...">. Жодного Markdown, ** чи #.
- Не використовуй списки з "-" на початку; замість буліта став емодзі «▪️» або «•».
- Не став посилань-сирцем; за потреби загортай у <a href="URL">текст</a>, але не обов'язково.
- Загальний обсяг — до 3500 символів.

СИРІ НОВИНИ:
{news_text}
"""


# --- Провайдери ---

def _try_claude(system: str, prompt: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def _try_gemini(system: str, prompt: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=system)
    resp = model.generate_content(prompt)
    return resp.text.strip()


def _try_groq(system: str, prompt: str) -> str:
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content.strip()


PROVIDERS = [
    ("Claude", "ANTHROPIC_API_KEY", _try_claude),
    ("Gemini", "GEMINI_API_KEY", _try_gemini),
    ("Groq", "GROQ_API_KEY", _try_groq),
]


def summarize(slot_label: str, date_label: str, news: dict) -> str:
    """Пробує провайдерів по черзі; повертає готовий текст дайджесту."""
    prompt = _build_user_prompt(slot_label, date_label, news)

    for name, env_key, fn in PROVIDERS:
        if not os.getenv(env_key):
            log.info("%s пропущено (немає %s)", name, env_key)
            continue
        try:
            log.info("Пробую %s…", name)
            text = fn(SYSTEM_PROMPT, prompt)
            if text:
                log.info("Дайджест згенеровано через %s", name)
                return text
        except Exception as e:  # noqa: BLE001
            log.warning("%s не спрацював: %s", name, e)
            continue

    raise RuntimeError("Жоден LLM-провайдер не спрацював (перевір API-ключі).")
