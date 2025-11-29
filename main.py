# main.py - شحن سيرياتيل أوتو 100% بدون أي زر أو تدخل
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import hashlib
import hmac
import requests

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

BOT_TOKEN = "8568967783:AAFpra7NAd0Wx_kEqzpBziv6ntxihyYfg3A"
BOT_USERNAME = "ExpShop_bot"  # غيّرها لاسم بوتك الحقيقي
ADMIN_ID = 7912788214

DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
                )''')
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

# تحقق تسجيل الدخول تليجرام
def check_telegram_auth(data: dict):
    if 'hash' not in data: return False
    check_hash = data.pop('hash')
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(data.items()) if k != 'hash'])
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return calculated_hash == check_hash

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "bot_username": BOT_USERNAME})

@app.get("/login")
async def login(request: Request):
    data = dict(request.query_params)
    if not check_telegram_auth(data):
        return HTMLResponse("فشل تسجيل الدخول!", status_code=403)
    user_id = int(data['id'])
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": {"id": user_id, "name": data.get('first_name', '')},
        "balance": get_balance(user_id)
    })

# API: جلب الرصيد (للتحديث التلقائي)
@app.get("/balance/{user_id}")
async def get_current_balance(user_id: int):
    return {"balance": get_balance(user_id)}

# API: طلب شحن سيرياتيل كاش أوتو
@app.post("/deposit-syriatel-auto")
async def deposit_syriatel_auto(data: dict):
    user_id = data.get("user_id")
    op_id = data.get("operation_id", "").strip()

    if len(op_id) < 8 or not op_id.isdigit():
        return JSONResponse({"success": False, "error": "رقم العملية غير صحيح"})

    # نرسل الرقم مباشرة للبوت كأنه المستخدم كتبه بنفسه
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": user_id,
        "text": op_id  # فقط الرقم، كأنه كتبه المستخدم في حالة waiting_op_id
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        return JSONResponse({"success": False, "error": "فشل الإرسال للبوت"})

    return JSONResponse({
        "success": True,
        "message": "تم إرسال رقم العملية للبوت..<br>جاري التحقق تلقائيًا.."
    })

# باقي الخدمات (سحب، بيع USDT)
@app.post("/withdraw-syriatel")
async def withdraw(data: dict):
    user_id, amount, phone = data["user_id"], data["amount"], data["phone"]
    if amount < 10000: return {"success": False, "error": "الحد الأدنى 10,000 ل.س"}
    if amount > get_balance(user_id): return {"success": False, "error": "رصيد غير كافٍ"}
    add_balance(user_id, -amount)
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={
        "chat_id": ADMIN_ID,
        "text": f"طلب سحب من الموقع\nالمستخدم: {user_id}\nالمبلغ: {amount:,} ل.س\nالرقم: `{phone}`"
    })
    return {"success": True}

@app.post("/sell-usdt-bemo")
async def sell_usdt(data: dict):
    user_id, amount_syp, account = data["user_id"], data["amount_syp"], data["bemo_account"]
    if amount_syp < 10000: return {"error": "الحد الأدنى 10,000 ل.س"}
    if amount_syp > get_balance(user_id): return {"error": "رصيد غير كافٍ"}
    usdt = round(amount_syp / 12700, 2)
    add_balance(user_id, -amount_syp)
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={
        "chat_id": ADMIN_ID,
        "text": f"بيع USDT من الموقع\nالمستخدم: {user_id}\n{amount_syp:,} ل.س = {usdt} USDT\nحساب بيمو: `{account}`"
    })
    return {"success": True, "usdt": usdt}

init_db()
