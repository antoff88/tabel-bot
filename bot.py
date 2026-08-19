#!/usr/bin/env python3
import logging
import requests
import json
import threading
import io
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

WEB_APP_URL = "https://ps2308.gt.tc"
BOT_TOKEN = "8934688321:AAF22dYMMrQhWSU7fvmGOCt_Igs8bstVdRE"
SITE_URL = "https://ps2308.gt.tc"
API_KEY = "ps2308_2026_secret_key"
PORT = 10000

# =============================================
# 🔐 АДМИНИСТРАТОР
# =============================================
ADMIN_ID = 6014139484

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =============================================
# HTTP-сервер для Render
# =============================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_http_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    logger.info(f"🌐 HTTP-сервер запущен на порту {PORT}")
    server.serve_forever()

# =============================================
# Генерация PDF
# =============================================
def generate_pdf_report(data, period_label):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, alignment=1, spaceAfter=12)
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Normal'], fontSize=12, alignment=1, spaceAfter=12)
    
    elements = []
    elements.append(Paragraph(f"📊 ОТЧЁТ ЗА {period_label.upper()}", title_style))
    elements.append(Spacer(1, 0.3*cm))
    
    total_hours = 0
    total_employees = set()
    for day in data.get('days', []):
        total_hours += day.get('totalHours', 0)
        for emp in day.get('employees', []):
            total_employees.add(emp.get('name', ''))
    
    elements.append(Paragraph(f"Всего часов: {total_hours}", subtitle_style))
    elements.append(Paragraph(f"Всего сотрудников: {len(total_employees)}", subtitle_style))
    elements.append(Spacer(1, 0.5*cm))
    
    for day in data.get('days', []):
        day_style = ParagraphStyle('DayStyle', parent=styles['Heading2'], fontSize=13, spaceAfter=6, textColor=colors.darkblue)
        elements.append(Paragraph(f"📅 {day.get('date', '')} — {day.get('location', '')}", day_style))
        elements.append(Paragraph(f"Ответственный: {day.get('responsible', '')}", styles['Normal']))
        elements.append(Paragraph(f"Место: {day.get('workPlace', '')}", styles['Normal']))
        elements.append(Spacer(1, 0.2*cm))
        
        table_data = [['№', 'Сотрудник', 'Часы']]
        for i, emp in enumerate(day.get('employees', []), 1):
            table_data.append([str(i), emp.get('name', ''), str(emp.get('hours', 0))])
        table_data.append(['', 'ИТОГО за день:', str(day.get('totalHours', 0))])
        
        table = Table(table_data, colWidths=[1.5*cm, 10*cm, 3*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.5*cm))
    
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"📊 ИТОГО: {total_hours} человеко-часов", styles['Heading3']))
    
    footer_style = ParagraphStyle('FooterStyle', parent=styles['Normal'], fontSize=8, alignment=1, textColor=colors.grey)
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("Сформировано в системе «ПромСтрой Табель»", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# =============================================
# Обработчики команд
# =============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"🔥 ПОЛУЧЕНА КОМАНДА /start от {update.effective_user.id}")
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 Открыть табель", web_app=WebAppInfo(url=WEB_APP_URL))],
        ],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        "👋 Система учёта табелей ООО «ПромСтрой»\n\n"
        "Нажмите кнопку, чтобы открыть табель.",
        reply_markup=keyboard,
    )

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE, period: str) -> None:
    user_id = update.effective_user.id
    logger.info(f"📨 Запрос отчёта от {user_id}")
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён. Только администратор может экспортировать PDF-отчёты.")
        return
    
    period_labels = {"week": "текущую неделю", "all": "сегодня"}
    await update.message.reply_text(f"⏳ Формирую PDF-отчёт за {period_labels.get(period, period)}...")
    
    try:
        url = f"{SITE_URL}/bot_api.php?key={API_KEY}&type={period}"
        logger.info(f"Запрос к {url}")
        
        # Увеличиваем таймаут и добавляем заголовки
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; TelegramBot/1.0)',
            'Accept': 'application/json',
            'Connection': 'close'
        }
        
        response = requests.get(url, timeout=60, headers=headers)
        logger.info(f"Статус ответа: {response.status_code}")
        
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Ошибка: сервер вернул код {response.status_code}")
            return
            
        data = response.json()
        
        if data.get('error'):
            await update.message.reply_text(f"❌ Ошибка: {data['error']}")
            return
        
        if not data.get('days'):
            await update.message.reply_text("❌ Нет данных за выбранный период")
            return
        
        period_label = data.get('period', period)
        pdf_bytes = generate_pdf_report(data, period_label)
        
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=f"otchet_{period}_{data.get('days', [{}])[0].get('date', 'today')}.pdf",
            caption=f"📊 Отчёт за {period_label}"
        )
        
    except requests.exceptions.Timeout:
        logger.error("Таймаут при запросе к сайту")
        await update.message.reply_text("❌ Ошибка: сайт не отвечает (таймаут). Попробуйте позже.")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Ошибка соединения: {e}")
        await update.message.reply_text("❌ Ошибка: не удалось подключиться к сайту. Проверьте, что сайт доступен.")
    except Exception as e:
        logger.error(f"Ошибка при формировании отчёта: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_week_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_report(update, context, "week")

async def handle_today_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_report(update, context, "all")

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if "неделя" in text.lower():
        await handle_week_pdf(update, context)
    elif "сегодня" in text.lower():
        await handle_today_pdf(update, context)
    elif "/week" in text:
        await handle_week_pdf(update, context)
    elif "/today" in text:
        await handle_today_pdf(update, context)
    else:
        await update.message.reply_text(f"Получил: {text}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"❌ ОШИБКА: {context.error}")

def main() -> None:
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    request = HTTPXRequest(connect_timeout=30, read_timeout=90, write_timeout=30, pool_timeout=30)
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("week", handle_week_pdf))
    app.add_handler(CommandHandler("today", handle_today_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message))
    app.add_error_handler(error_handler)
    logger.info("🚀 Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
