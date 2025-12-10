import logging
import os
from typing import List, Dict, Optional

import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =========================
# Cấu hình logging
# =========================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================
# Đọc biến môi trường
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# Mặc định quốc gia & ngôn ngữ: Việt Nam
DEFAULT_GL = os.getenv("SERPER_GL", "vn")  # geolocation
DEFAULT_HL = os.getenv("SERPER_HL", "vi")  # language

SERPER_ENDPOINT = "https://google.serper.dev/search"


# =========================
# Hàm gọi Serper API
# =========================
def serper_search(
    query: str,
    gl: str = DEFAULT_GL,
    hl: str = DEFAULT_HL,
    num: int = 10,
) -> List[Dict]:
    """
    Gọi Serper Search API để lấy danh sách kết quả organic trên Google.

    Trả về list các dict: {position, title, link, snippet}
    """
    if not SERPER_API_KEY:
        logger.error("SERPER_API_KEY chưa được set trong biến môi trường.")
        raise RuntimeError("SERPER_API_KEY is not set")

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "q": query,
        "gl": gl,
        "hl": hl,
        "num": num,
        # có thể thêm "type": "search" nếu cần, nhưng với endpoint /search là mặc định
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
        logger.exception("Lỗi khi gọi Serper API: %s", e)
        raise RuntimeError(f"Lỗi gọi Serper API: {e}")

    data = resp.json()

    # Một số tài liệu dùng key "organic", một số dùng "organic_results"
    organic = data.get("organic") or data.get("organic_results") or []

    results: List[Dict] = []
    for item in organic:
        title = item.get("title")
        link = item.get("link")
        snippet = item.get("snippet", "")
        position = item.get("position")

        if not title or not link:
            continue

        results.append(
            {
                "position": position,
                "title": title,
                "link": link,
                "snippet": snippet,
            }
        )

    return results


# =========================
# Handler /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Xin chào 👋\n\n"
        "Bot này dùng Serper API để check top Google.\n\n"
        "Cách dùng:\n"
        "<code>/s [từ_khóa]</code>\n"
        "Ví dụ:\n"
        "<code>/s hi88</code>\n\n"
        "Mặc định: location = Việt Nam (gl=vn, hl=vi)."
    )
    await update.message.reply_text(text, parse_mode="HTML")


# =========================
# Handler /help
# =========================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "Cách dùng bot kiểm tra thứ hạng Google:\n\n"
        "<b>Lệnh:</b>\n"
        "<code>/s [từ_khóa]</code>\n\n"
        "Ví dụ:\n"
        "<code>/s hi88</code>\n\n"
        "Bot sẽ trả về danh sách các website đang top cho từ khóa đó "
        "trên Google (khu vực Việt Nam)."
    )
    await update.message.reply_text(text, parse_mode="HTML")


# =========================
# Handler /s - search
# =========================
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /s hi88
    /s "nhà cái hi88"
    """
    if not context.args:
        usage = (
            "Thiếu từ khóa.\n\n"
            "Ví dụ:\n"
            "<code>/s hi88</code>\n"
            "<code>/s nhà cái hi88</code>"
        )
        await update.message.reply_text(usage, parse_mode="HTML")
        return

    keyword = " ".join(context.args).strip()
    chat_id = update.effective_chat.id

    logger.info("User %s search keyword: %s", chat_id, keyword)

    # Thông báo đang xử lý
    msg = await update.message.reply_text("Đang tìm kết quả trên Google...")

    try:
        results = serper_search(keyword, gl=DEFAULT_GL, hl=DEFAULT_HL, num=10)
    except RuntimeError as e:
        await msg.edit_text(
            f"Lỗi khi gọi Serper API:\n<code>{e}</code>", parse_mode="HTML"
        )
        return

    if not results:
        await msg.edit_text(
            f"Không tìm thấy kết quả organic nào cho từ khóa: <b>{keyword}</b>",
            parse_mode="HTML",
        )
        return

    # Format kết quả cho Telegram
    lines = []
    header = (
        f"Kết quả Google cho từ khóa: <b>{keyword}</b>\n"
        f"Quốc gia: <b>Việt Nam</b> (gl=vn, hl=vi)\n\n"
    )
    lines.append(header)

    for r in results:
        pos = r.get("position")
        title = r.get("title")
        link = r.get("link")
        snippet = r.get("snippet") or ""

        # Cắt snippet cho gọn nếu quá dài
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."

        lines.append(
            f"{pos}. <b>{title}</b>\n"
            f"{link}\n"
            f"{snippet}\n"
        )

    text = "\n".join(lines)

    # Telegram giới hạn ~4096 ký tự; nếu quá dài thì cắt
    if len(text) > 4000:
        text = text[:3990] + "\n...(cắt bớt)..."

    await msg.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)


# =========================
# Hàm main khởi động bot
# =========================
def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment variables.")

    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Đăng ký handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("s", search_command))

    # Chạy bot dạng polling
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
