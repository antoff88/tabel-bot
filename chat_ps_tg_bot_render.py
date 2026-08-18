#!/usr/bin/env python3
import asyncio
import json
import os
import time
import base64
import sys
from telegram import Bot
from telegram.request import HTTPXRequest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# =============================================
# Конфигурация через переменные окружения
# =============================================

BOT_TOKEN = os.environ.get('BOT_TOKEN', '8767742799:AAGuJfV_8v2Df7Hnm6g68FOZuYhQ7tBAwgs')
GROUP_ID = int(os.environ.get('GROUP_ID', '-1004384870669'))
GENERAL_TOPIC = int(os.environ.get('GENERAL_TOPIC', '4'))
LOG_TOPIC = int(os.environ.get('LOG_TOPIC', '60'))

# Пути (на Render они будут в /opt/render/project/src/)
BASE_DIR = os.environ.get('BASE_DIR', '/opt/render/project/src')
CHAT_DIR = os.environ.get('CHAT_DIR', f'{BASE_DIR}/chat_data')
LOG_DIR = os.environ.get('LOG_DIR', f'{BASE_DIR}/log/data')
STATE_FILE = os.environ.get('STATE_FILE', f'{BASE_DIR}/state.json')
TG_LAST_ID_FILE = os.environ.get('TG_LAST_ID_FILE', f'{BASE_DIR}/tg_last_id.txt')
LOG_LAST_TIME_FILE = os.environ.get('LOG_LAST_TIME_FILE', f'{BASE_DIR}/log_last_time.txt')

# Создаём папки, если их нет
os.makedirs(CHAT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# =============================================
# Ключ шифрования (из переменной окружения)
# =============================================

CHAT_KEY_HEX = os.environ.get('CHAT_KEY', '')
if not CHAT_KEY_HEX:
    print("❌ Ошибка: переменная CHAT_KEY не установлена!")
    sys.exit(1)

try:
    CHAT_KEY = bytes.fromhex(CHAT_KEY_HEX)
except ValueError:
    print("❌ Ошибка: CHAT_KEY должна быть в hex-формате (например, 00112233445566778899aabbccddeeff)")
    sys.exit(1)

# =============================================
# Данные пользователей
# =============================================

USER_TOPICS = {
    'EAV':5,'NDS':6,'EON':7,'PES':8,'NVD':15,'MAA':4,
    'DEK':73,'HAV':74,'VDA':75,'TIA':76,'TAA':77,'SVI':78,'EAVn':79,
    'ZAI':80,'IVG':81,'TMR':82,'AAV':83,'IYV':84,'PSV':85,'OAA':86,
    'NBA':87,'AvM':88,'NAT':89,'GVV':90,'NGS':91,'KAP':92,'GMV':93,
    'MGY':94,'KSN':95,'KSA':96
}
TOPIC_TO_LOGIN = {v:k for k,v in USER_TOPICS.items()}
TOPIC_TO_LOGIN[4] = 'general'
TOPIC_TO_LOGIN[60] = 'logs'

LOGIN_NAMES = {
    'EON':'Егорова О. Н.','EAV':'Егоров А. В.','MAA':'Марычев А. А.',
    'NDS':'Нерозин Д. С.','NVD':'Нерозин В. Д.','PES':'Панков Э. С.',
    'DEK':'Дроботько Е. К.','HAV':'Херувимов А. В.','VDA':'Волковский Д. А.',
    'TIA':'Талдонов И. А.','TAA':'Титаренко А. А.','SVI':'Схакумидов В. И.',
    'EAVn':'Егоров А. В.','ZAI':'Золотарёв А. И.','IVG':'Ильин В. Г.',
    'TMR':'Тонян М. Р.','AAV':'Абрамянц А. В.','IYV':'Ильин Ю. В.',
    'PSV':'Политаев С. В.','OAA':'Озоян А. А.','NBA':'Надоян Б. А.',
    'AvM':'Авдоян М. А.','NAT':'Надоян А. Т.','GVV':'Горбатенко В. В.',
    'NGS':'Наумович Г. С.','KAP':'Коробейников А. П.','GMV':'Горбатенко М. В.',
    'MGY':'Меньшаков Г. Ю.','KSN':'Кокин С. Н.','KSA':'Курбаков С. А.',
    'EVA':'Егоров В. А.'
}

# =============================================
# Функции шифрования
# =============================================

def decrypt_text(encrypted):
    try:
        data = base64.b64decode(encrypted)
        iv, cipher = data[:16], data[16:]
        c = Cipher(algorithms.AES(CHAT_KEY), modes.CBC(iv))
        dec = c.decryptor().update(cipher) + c.decryptor().finalize()
        pad = dec[-1]
        if pad > 0 and pad <= 16:
            return dec[:-pad].decode('utf-8')
        return encrypted
    except:
        return encrypted

# =============================================
# Бот (без прокси)
# =============================================

bot = Bot(token=BOT_TOKEN)

# =============================================
# Функции работы с состоянием
# =============================================

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f: 
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f: 
        json.dump(state, f)

def load_last_time():
    try:
        with open(LOG_LAST_TIME_FILE) as f: 
            return float(f.read().strip())
    except: 
        return 0

def save_last_time(t):
    with open(LOG_LAST_TIME_FILE, 'w') as f: 
        f.write(str(t))

def load_tg_last_id():
    try:
        with open(TG_LAST_ID_FILE) as f: 
            return int(f.read().strip())
    except: 
        return 0

def save_tg_last_id(uid):
    with open(TG_LAST_ID_FILE, 'w') as f: 
        f.write(str(uid))

def get_new_messages(filepath, key):
    if not os.path.exists(filepath): 
        return []
    with open(filepath) as f: 
        messages = json.load(f)
    state = load_state()
    last_idx = state.get(key, 0)
    new_msgs = messages[last_idx:]
    if new_msgs:
        state[key] = len(messages)
        save_state(state)
    return new_msgs

def add_message_to_chat(filepath, msg):
    messages = []
    if os.path.exists(filepath):
        with open(filepath) as f:
            try: messages = json.load(f)
            except: messages = []
    messages.append(msg)
    with open(filepath, 'w') as f: 
        json.dump(messages, f, ensure_ascii=False)

# =============================================
# Основные задачи
# =============================================

async def forward_from_chat():
    all_logins = ['EON','EAV','MAA','NDS','NVD','PES','DEK','HAV','VDA','TIA','TAA','SVI','EAVn','ZAI','IVG','TMR','AAV','IYV','PSV','OAA','NBA','AvM','NAT','GVV','NGS','KAP','GMV','MGY','KSN','KSA']
    
    while True:
        try:
            # Общие сообщения
            for msg in get_new_messages(f'{CHAT_DIR}/general.json', 'general'):
                msg_text = msg.get('text','')
                if msg.get('encrypted') and msg_text:
                    msg_text = decrypt_text(msg_text)
                text = f"📢 {msg['fromName']}:\n{msg_text}"
                await bot.send_message(GROUP_ID, text, message_thread_id=GENERAL_TOPIC)

            # Личные сообщения
            for i in range(len(all_logins)):
                for j in range(i+1, len(all_logins)):
                    a,b = sorted([all_logins[i], all_logins[j]])
                    fpath = f'{CHAT_DIR}/{a}_{b}.json'
                    for msg in get_new_messages(fpath, f'{a}_{b}'):
                        sender = msg['fromName']
                        rlogin = msg.get('to','')
                        if not rlogin:
                            for l in all_logins:
                                if l != msg['from'] and l in fpath: 
                                    rlogin = l; break
                        msg_text = msg.get('text','')
                        if msg.get('encrypted') and msg_text:
                            msg_text = decrypt_text(msg_text)
                        text = f"💬 {sender} → {LOGIN_NAMES.get(rlogin,rlogin)}:\n{msg_text}"
                        tid = USER_TOPICS.get(rlogin, GENERAL_TOPIC)
                        await bot.send_message(GROUP_ID, text, message_thread_id=tid)
        except Exception as e:
            print(f'Fwd err: {e}')
        await asyncio.sleep(3)

async def forward_logs():
    while True:
        try:
            last_time = load_last_time()
            today_file = f'{LOG_DIR}/{time.strftime("%Y-%m-%d")}.json'
            if os.path.exists(today_file):
                logs = None
                for attempt in range(3):
                    try:
                        with open(today_file) as f: 
                            logs = json.load(f)
                        break
                    except:
                        await asyncio.sleep(0.5)
                if logs is None: 
                    continue
                today_str = time.strftime("%Y-%m-%d")
                new_logs = [l for l in logs if time.mktime(time.strptime(today_str + ' ' + l['time'], '%Y-%m-%d %H:%M:%S')) > last_time]
                for l in new_logs:
                    text = f"🕐 {l['time']} | {l['login']} | {l['action']} | {l.get('details','')} | IP: {l['ip']} | {l.get('device','')} | {l.get('location','')}"
                    await bot.send_message(GROUP_ID, text, message_thread_id=LOG_TOPIC)
                if new_logs:
                    save_last_time(time.time())
        except Exception as e:
            print(f'Log err: {e}')
        await asyncio.sleep(10)

async def receive_from_tg():
    last_id = load_tg_last_id()
    while True:
        try:
            updates = await bot.get_updates(offset=last_id+1, timeout=10)
            for u in updates:
                msg = u.message
                if not msg or not msg.text: 
                    continue
                last_id = u.update_id
                save_tg_last_id(last_id)
                tid = msg.message_thread_id
                text = msg.text
                if not tid: 
                    continue
                if text.startswith('/logs') and tid == LOG_TOPIC:
                    today_file = f'{LOG_DIR}/{time.strftime("%Y-%m-%d")}.json'
                    if os.path.exists(today_file):
                        logs = json.load(open(today_file))
                        logs = logs[-10:]
                        resp = "📋 Последние логи:\n" + "\n".join([f"{l['time']} {l['login']} {l['action']}" for l in logs])
                        await bot.send_message(GROUP_ID, resp, message_thread_id=LOG_TOPIC)
                    continue
                if tid == GENERAL_TOPIC:
                    fpath = f'{CHAT_DIR}/general.json'
                    cm = {
                        'from':'TG',
                        'fromName':'Telegram',
                        'text':text,
                        'time':msg.date.strftime('%H:%M'),
                        'timestamp':int(msg.date.timestamp())
                    }
                    add_message_to_chat(fpath, cm)
                elif tid in TOPIC_TO_LOGIN:
                    target = TOPIC_TO_LOGIN[tid]
                    if target != 'MAA':
                        pair = sorted(['MAA', target])
                        fpath = f'{CHAT_DIR}/{pair[0]}_{pair[1]}.json'
                        cm = {
                            'from':'MAA',
                            'fromName':'Антон Александрович',
                            'text':text,
                            'to':target,
                            'time':msg.date.strftime('%H:%M'),
                            'timestamp':int(msg.date.timestamp())
                        }
                        add_message_to_chat(fpath, cm)
        except Exception as e:
            print(f'Recv err: {e}')
        await asyncio.sleep(1)

async def main():
    print('🚀 Бот запущен на Render')
    await asyncio.gather(forward_from_chat(), forward_logs(), receive_from_tg())

if __name__ == '__main__':
    asyncio.run(main())
