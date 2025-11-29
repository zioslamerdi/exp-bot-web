from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import os
from telegram import Bot
import hashlib
import hmac
import json

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

BOT_TOKEN = "8568967783:AAFpra7NAd0Wx_kEqzpBziv6ntxihyYfg3A"  # توكن البوت
BOT_USERNAME = "ExpShop_bot"  # غيّرها لاسم بوتك الحقيقي
bot = Bot(token=BOT_TOKEN)

DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_balance(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# تحقق من صحة تسجيل الدخول
def check_telegram_auth(data: dict):
    check_hash = data.pop('hash')
    auth_date = data['auth_date']
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(data.items())])
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return calculated_hash == check_hash

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "bot_username": BOT_USERNAME})

@app.get("/login")
async def login_callback(request: Request):
    data = dict(request.query_params)
    if 'hash' not in data:
        return HTMLResponse("فشل تسجيل الدخول", status_code=400)
    
    if check_telegram_auth(data):
        user = {
            "id": data['id'],
            "name": data.get('first_name', '') + " " + data.get('last_name', ''),
            "username": data.get('username', 'لا يوجد')
        }
        balance = get_balance(int(user['id']))
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user,
            "balance": balance
        })
    else:
        return HTMLResponse("فشل التحقق من الهوية!", status_code=403)

# API للخدمات (مثال: بيع USDT إلى بيمو)
@app.post("/sell-usdt-bemo")
async def sell_usdt_bemo(user_id: int = Form(), amount_syp: int = Form(), bemo_account: str = Form()):
    if amount_syp < 10000:
        return JSONResponse({"error": "الحد الأدنى 10,000 ل.س"})
    if amount_syp > get_balance(user_id):
        return JSONResponse({"error": "رصيدك غير كافٍ"})
    
    add_balance(user_id, -amount_syp)
    usdt = round(amount_syp / 12700, 2)
    
    # إشعار للأدمن
    await bot.send_message(
        chat_id=7912788214,
        text=f"""طلب بيع USDT جديد (من الموقع)

المستخدم: {user_id}
المبلغ: {amount_syp:,} ل.س
USDT: {usdt}
حساب بيمو: `{bemo_account}`
رصيد بعد الخصم: {get_balance(user_id):,}"""
    )
    
    return JSONResponse({"success": True, "usdt": usdt})

init_db()
