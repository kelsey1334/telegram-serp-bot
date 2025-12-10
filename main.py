import logging
import os
from typing import List, Dict
from urllib.parse import urlparse

import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =========================
# Logging
# =========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================
# ENV
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# 🇧🇷 Brazil là mặc định
DEFAULT_GL = "br"   # country = Brazil
DEFAULT_HL = "pt"   # language = Portuguese

SERPER_ENDPOINT = "https://google.serper.dev/search"


# =========================
# Serper API
# =========================
def serper_search(query: str, gl: str = DEFAULT_GL, hl: str = DEFAULT_HL, num: int = 10) -> List[Dict]:
    if not SERPER_API_KEY:
        raise RuntimeError("SERPER_API_KEY is not set.")

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "q": query,
        "gl": gl,
        "hl": hl,
        "num": num,
    }

    try:
        resp = requests.post(
            SERPER_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.exception("Serper API error: %s", e)
        raise RuntimeError(f"Serper API error: {e}")

    data = resp.json()
    organic = data.get("organic") or data.get("organic_results") or []

    results = []
    for item in organic:
        title = item.get("title")
        link = item.get("link")
        snippet = item.get("snippet", "")
        pos = item.get("position")

        if not title or not link:
            continue

        results.append({
            "position": pos,
            "title": title,
            "link": link,
            "snippet": snippet
        })

    return results


def extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return url


# =========================
# BOT COMMANDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🇧🇷 Bot kiểm tra thứ hạng Google Brazil.\n\n"
        "Cách dùng:\n"
        "🔎 <code>/s [từ_khóa]</code>\n"
        "Ví dụ:\n"
        "<code>/s hi88</code>\n\n"
        "Kết quả hiển thị dạng:\n"
        "🏆 Top 1: domain.com\n"
        "⭐ Top 2: domain.com\n"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Ví dụ:\n<code>/s hi88</code>",
            parse_mode="HTML",
        )
        return

    keyword = " ".join(context.args).strip()

    msg = await update.message.reply_text("⏳ Đang tìm kết quả Google Brazil...")

    try:
        results = serper_search(keyword)
    except RuntimeError as e:
        await msg.edit_text(f"⚠️ Lỗi API:\n<code>{e}</code>", parse_mode="HTML")
        return

    if not results:
        await msg.edit_text(
            f"Không tìm thấy kết quả cho từ khóa: <b>{keyword}</b>",
            parse_mode="HTML"
        )
        return

    seen = set()
    domain_positions = []

    for r in results:
        domain = extract_domain(r["link"])
        pos = r.get("position")

        if domain in seen:
            continue
        seen.add(domain)

        if not isinstance(pos, int):
            pos = len(domain_positions) + 1

        domain_positions.append((pos, domain))

    domain_positions.sort(key=lambda x: x[0])

    lines = []
    header = (
        "🇧🇷 <b>Google Brazil SERP</b>\n"
        f"🔎 Từ khóa: <code>{keyword}</code>\n\n"
    )
    lines.append(header)

    for pos, domain in domain_positions:
        if pos == 1:
            icon = "🏆"
        elif pos == 2:
            icon = "⭐"
        elif pos == 3:
            icon = "⭐"
        else:
            icon = "•"

        lines.append(f"{icon} Top {pos}: <code>{domain}</code>")

    text = "\n".join(lines)

    if len(text) > 4000:
        text = text[:3990] + "\n...(cắt bớt)..."

    await msg.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)


# =========================
# MAIN
# =========================
def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("s", search_command))

    app.run_polling()


if __name__ == "__main__":
    main()
