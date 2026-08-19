#!/usr/bin/env python3
import logging
import requests
import json
import threading
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

WEB_APP_URL = "https://ps2308.gt.tc"
BOT_TOKEN = "8934688321:AAF22dYMMrQhWSU7fvmGOCt_Igs8bstVdRE"
SITE_URL = "https://ps2308.gt.tc"
PORT = 10000

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
    """Создаёт PDF-файл с отчётом и возвращает bytes"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*cm, bottomMargin=1*cm)
    styles = getSampleStyleSheet()
    
    # Стили
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,  # center
        spaceAfter=12
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=1,
        spaceAfter=12
    )
    
    elements = []
    
    # Заголовок
    elements.append(Paragraph(f"📊 ОТЧЁТ ЗА {period_label.upper()}", title_style))
    elements.append(Spacer(1, 0.3*cm))
    
    # Общая статистика
    total_hours = 0
    total_employees = set()
    
    for day in data.get('days', []):
        total_hours += day.get('totalHours', 0)
        for emp in day.get('employees', []):
            total_employees.add(emp.get('name', ''))
    
    elements.append(Paragraph(f"Всего часов: {total_hours}", subtitle_style))
    elements.append(Paragraph(f"Всего сотрудников: {len(total_employees)}", subtitle_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # По дням
    for day in data.get('days', []):
        # Заголовок дня
        day_style = ParagraphStyle(
            'DayStyle',
            parent=styles['Heading2'],
            fontSize=13,
            spaceAfter=6,
            textColor=colors.darkblue
        )
        elements.append(Paragraph(f"📅 {day.get('date', '')} — {day.get('location', '')}", day_style))
        elements.append(Paragraph(f"Ответственный: {day.get('responsible', '')}", styles['Normal']))
        elements.append(Paragraph(f"Место: {day.get('workPlace', '')}", styles['Normal']))
        elements.append(Spacer(1, 0.2*cm))
        
        # Таблица сотрудников
        table_data = [['№', 'Сотрудник', 'Часы']]
        for i, emp in enumerate(day.get('employees', []), 1):
            table_data.append([str(i), emp.get('name', ''), str(emp.get('hours', 0))])
        
        # Итого за день
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
    
    # Итоговая статистика
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"📊 ИТОГО: {total_hours} человеко-часов", styles['Heading3']))
    
    # Подвал
    elements.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=8,
        alignment=1,
        textColor=colors.grey
    )
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
            [KeyboardButton("📋 Отчёт за неделю (текст)")],
            [KeyboardButton("📄 Отчёт за неделю (PDF)")],
            [KeyboardButton("📋 Отчёт за сегодня (текст)")],
            [KeyboardButton("📄 Отчёт за сегодня (PDF)")]
        ],
        resize_keyboard=True,
    )
    await update.message.reply_text(
        "👋 Система учёта табелей ООО «ПромСтрой»\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
    )
    logger.info("✅ Ответ отправлен")

async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE, period: str, format: str = "text") -> None:
    """Обработчик запроса отчёта"""
    period_labels = {
        "week": "текущую неделю",
        "all": "сегодня"
    }
    await update.message.reply_text(f"⏳ Формирую отчёт за {period_labels.get(period, period)}...")
    
    try:
        url = f"{SITE_URL}/tabel_report_all.php?type={period}"
        logger.info(f"Запрос к {url}")
        
        response = requests.get(url, timeout=30)
        data = response.json()
        
        if not data.get('days'):
            await update.message.reply_text("❌ Нет данных за выбранный период")
            return
        
        if format == "pdf":
            # Генерируем PDF
            period_label = data.get('period', period)
            pdf_bytes = generate_pdf_report(data, period_label)
            
            # Отправляем PDF файл
            await update.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename=f"otchet_{period}_{data.get('days', [{}])[0].get('date', 'today')}.pdf",
                caption=f"📊 Отчёт за {period_label}"
            )
        else:
            # Текстовый отчёт (как раньше)
            report_text = f"📊 ОТЧЁТ ЗА {data.get('period', '').upper()}\n"
            report_text += "=" * 40 + "\n\n"
            
            total_hours = 0
            
            for day in data.get('days', []):
                report_text += f"📅 {day.get('date', '')}\n"
                report_text += f"📍 {day.get('location', '')}\n"
                report_text += f"👤 Ответственный: {day.get('responsible', '')}\n"
                report_text += f"👥 Сотрудников: {day.get('employeeCount', 0)}\n"
                report_text += f"⏱ Часов: {day.get('totalHours', 0)}\n\n"
                
                for emp in day.get('employees', []):
                    report_text += f"  • {emp.get('name', '')}: {emp.get('hours', 0)} ч\n"
                report_text += "\n" + "-" * 30 + "\n\n"
                
                total_hours += day.get('totalHours', 0)
            
            report_text += f"\n📊 ИТОГО: {total_hours} человеко-часов"
            
            if len(report_text) > 4000:
                for i in range(0, len(report_text), 4000):
                    await update.message.reply_text(report_text[i:i+4000])
            else:
                await update.message.reply_text(report_text)
            
    except Exception as e:
        logger.error(f"Ошибка при формировании отчёта: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_week_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_report(update, context, "week", "text")

async def handle_week_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_report(update, context, "week", "pdf")

async def handle_today_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_report(update, context, "all", "text")

async def handle_today_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await handle_report(update, context, "all", "pdf")

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    logger.info(f"📨 Сообщение от {update.effective_user.id}: {text}")
    
    if "PDF" in text and "неделя" in text:
        await handle_week_pdf(update, context)
    elif "PDF" in text and "сегодня" in text:
        await handle_today_pdf(update, context)
    elif "текст" in text and "неделя" in text:
        await handle_week_text(update, context)
    elif "текст" in text and "сегодня" in text:
        await handle_today_text(update, context)
    else:
        await update.message.reply_text(f"Получил: {text}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"❌ ОШИБКА: {context.error}")

def main() -> None:
    # Запускаем HTTP-сервер
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    # Запускаем бота
    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=90,
        write_timeout=30,
        pool_timeout=30
    )
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("week", handle_week_text))
    app.add_handler(CommandHandler("weekpdf", handle_week_pdf))
    app.add_handler(CommandHandler("today", handle_today_text))
    app.add_handler(CommandHandler("todaypdf", handle_today_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_any_message))
    app.add_error_handler(error_handler)
    logger.info("🚀 Бот запущен")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
