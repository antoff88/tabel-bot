#!/usr/bin/env python3
import logging
import requests
import json
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

WEB_APP_URL = "https://ps2308.gt.tc"
BOT_TOKEN = "8934688321:AAF22dYMMrQhWSU7fvmGOCt_Igs8bstVdRE"
SITE_URL = "https://ps2308.gt.tc"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"🔥 ПОЛУЧЕНА КОМАНДА /start от {update.effective_user.id}")
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 Открыть табель", web_app=WebAppInfo(url=WEB_APP_URL))],
            [KeyboardButton("📋 Отчёт за неделю")],
            [KeyboardButton("📋 Отчёт за сегодня")]
        ],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        "👋 Система учёта табелей ООО «ПромСтрой»\n\n"
        "Нажмите кнопку ниже, чтобы открыть табель,\n"
        "или запросите отчёт:",
        reply_markup=keyboard,
    )
    logger.info("✅ Ответ отправлен")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE, period: str) -> None:
    """Обработчик запроса отчёта"""
    await update.message.reply_text(f"⏳ Формирую отчёт за {period}...")
    
    try:
        # Запрашиваем данные с сайта
        url = f"{SITE_URL}/tabel_report_all.php?type={period}"
        logger.info(f"Запрос к {url}")
        
        response = requests.get(url, timeout=30)
        data = response.json()
        
        if not data.get('days'):
            await update.message.reply_text("❌ Нет данных за выбранный период")
            return
        
        # Формируем текстовый отчёт
        report_text = f"📊 ОТЧЁТ ЗА {data.get('period', '').upper()}\n"
        report_text += "=" * 40 + "\n\n"
        
        total_hours = 0
        
        for day in data.get('days', []):
            report_text += f"📅 {day.get('date', '')}\n"
            report_text += f"📍 {day.get('location', '')}\n"
            report_text += f"👤 Ответственный: {day.get('responsible', '')}\n"
            report_text += f"👥 Сотрудников: {day.get('employeeCount', 0)}\n"
            report_text += f"⏱ Часов: {day.get('totalHours', 0)}\n\n"
            
            # Список сотрудников
            for emp in day.get('employees', []):
                report_text += f"  • {emp.get('name', '')}: {emp.get('hours', 0)} ч\n"
            report_text += "\n" + "-" * 30 + "\n\n"
            
            total_hours += day.get('totalHours', 0)
        
        report_text += f"\n📊 ИТОГО: {total_hours} человеко-часов"
        
        # Отправляем отчёт
        if len(report_text) > 4000:
            for i in range(0, len(report_text), 4000):
                await update.message.reply_text(report_text[i:i+4000])
        else:
            await update.message.reply_text(report_text)
            
        # Отправляем ссылку на полную версию в браузере
        await update.message.reply_text(
            f"📎 Полная версия с экспортом:\n{SITE_URL}/tabel.php\n\n"
            "Для экспорта в PDF/Excel откройте ссылку в браузере."
        )
        
    except Exception as e:
        logger.error(f"Ошибка при формировании отчёта: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_week_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_report(update, context, "week")

async def handle_today_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_report(update, context, "all")

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    logger.info(f"📨 Сообщение от {update.effective_user.id}: {text}")
    
    if "неделя" in text.lower():
        await handle_week_report(update, context)
    elif "сегодня" in text.lower():
        await handle_today_report(update, context)
    else:
        await update.message.reply_text(f"Получил: {text}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"❌ ОШИБКА: {context.error}")

def main() -> None:
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=90,
        write_timeout=30,
        pool_timeout=30
    )
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("week", handle_week_report))
    app.add_handler(CommandHandler("today", handle_today_report))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message))
    app.add_error_handler(error_handler)
    logger.info("🚀 Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
