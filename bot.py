#!/usr/bin/env python3
import logging
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

WEB_APP_URL = "https://ps2308.gt.tc"
BOT_TOKEN = "8934688321:AAF22dYMMrQhWSU7fvmGOCt_Igs8bstVdRE"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"🔥 ПОЛУЧЕНА КОМАНДА /start от {update.effective_user.id}")
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📊 Открыть табель", web_app=WebAppInfo(url=WEB_APP_URL))]],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        "👋 Система учёта табелей ООО «ПромСтрой»\n\n"
        "Нажмите кнопку ниже, чтобы открыть табель:",
        reply_markup=keyboard,
    )
    logger.info("✅ Ответ отправлен")

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"📨 Сообщение от {update.effective_user.id}: {update.message.text}")
    await update.message.reply_text(f"Получил: {update.message.text}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"❌ ОШИБКА: {context.error}")

def main() -> None:
    # Убираем proxy — на Render он не нужен
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=90,
        write_timeout=30,
        pool_timeout=30
    )
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message))
    app.add_error_handler(error_handler)
    logger.info("🚀 Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
