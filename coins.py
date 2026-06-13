import requests
import time
import datetime
import os

TOKEN = os.environ.get("TOKEN")
PROVIDER_TOKEN = os.environ.get("PROVIDER_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN", "0"))

BASE_URL = f"https://tapi.bale.ai/bot{TOKEN}"
last_update_id = 0
CHANNEL_ID = "@Arka_coins"
SERVICE_NAME = "بله"

# =========================
# STATUS START LOG
# =========================
print("===================================")
print("🤖 ARKA BOT STARTING...")
print("⏳ Connecting to Bale API ...")
print("⏰", datetime.datetime.now())
print("===================================")

# =========================
# STATE
# =========================
user_state = {}
user_amount = {}
user_phone = {}
order_id = 0

# داده‌های مرحله‌ای فروش سکه
sell_amount = {}
sell_phone = {}
sell_card = {}

admin_state = {}          # حالت ادمین (مثلاً منتظر ورودی متن)
admin_target_chat = {}    # هدف ارسال پیام مستقیم ادمین
pending_orders = {}       # order_id -> chat_id (برای دکمه ارسال پیام به کاربر)

orders = {}               # order_id -> {chat_id, amount, phone, total, status, type, ...}
blocked_users = set()      # آیدی‌های مسدود شده

# قیمت‌ها (قابل تغییر توسط ادمین)
PRICE_BUY = 35    # نرخ خرید (همین نرخ برای فروش سکه توسط کاربر به ربات استفاده می‌شود)
PRICE_SELL = 40   # نرخ فروش (برای محاسبه فاکتور خرید سکه توسط کاربر استفاده می‌شود)

MIN_COIN = 200
SELL_UNIT = 211
MAX_COIN = 10000

BOT_BALANCE = 0   # موجودی فعلی سکه ربات (با ثبت موجودی توسط ادمین تغییر می‌کند)

services_enabled = True

# =========================
# TICKETS
# =========================
ticket_id = 0
tickets = {}  # ticket_id -> {chat_id, text, status, reply_chat}


def fmt(n):
    return f"{n:,}"


# =========================
# JOIN CHECK
# =========================
def is_member(user_id):
    try:
        r = requests.get(
            f"{BASE_URL}/getChatMember",
            params={"chat_id": CHANNEL_ID, "user_id": user_id}
        ).json()
        status = r.get("result", {}).get("status", "")
        return status in ("member", "administrator", "creator")
    except Exception:
        return False


def send_join_required(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": """*کاربر گرامی⚠️*

عضو خانواده آرکا شو!✔️

بعدش رو *عضو شدم✔️* بزن!🖐""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "〽️ کانال خرید و فروش سکه", "url": "https://ble.ir/Arka_coins"}],
                    [{"text": "عضو شدم✔️", "callback_data": "joined_check"}]
                ]
            }
        }
    )


def send_join_failed(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": """*کاربر گرامی⚠️*

عضویت شما تأیید نشد!✖️

ابتدا در کانال زیر عضو شوید و سپس، مجدد بر روی دکمه *عضو شدم✔️* کلیک نمایید!""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "〽️ کانال خرید و فروش سکه", "url": "https://ble.ir/Arka_coins"}],
                    [{"text": "عضو شدم✔️", "callback_data": "joined_check"}]
                ]
            }
        }
    )


# =========================
# MENU
# =========================
def menu(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"""*✨ به آرکا خوش آمدید! ✨

⚜️ پشتیبانی ویژه آرکا ✔️ 🌹

───────────────

💰 نرخ‌های امروز:

💎 خرید هر 1k سکه: {fmt(PRICE_BUY)} هزار تومان

📈 فروش هر 1k سکه: {fmt(PRICE_SELL)} هزار تومان

───────────────

⚡️ وضعیت خدمات:

🛒 خرید: [ فعال ] 🟢

💵 فروش: [ فعال ] 🟢

───────────────

🚀 عملیات اصلی:

از منوی زیر، انتخاب کنید: 👇*
""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "keyboard": [
                    [{"text": "〽️ خرید سکه کانال بله"}],
                    [{"text": "🛍فروش سکه کانال بله"}],
                    [{"text": "📞 پشتیبانی"}]
                ],
                "resize_keyboard": True
            }
        }
    )


# =========================
# BUY STEP
# =========================
def send_buy(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"""*⚜️ خرید سکه ⚜️

✨ ویژه: بسته به نیاز شما، از 200 تا 10,000 سکه تهیه کنید.

💰 قیمت هر 1000 سکه: فقط {fmt(PRICE_SELL)} هزار تومان!

🚀 پیشنهاد ویژه: 1,000 سکه را فقط با {fmt(PRICE_SELL)} هزار تومان خریداری کنید!

📌 مرحله 1 از 2

💐 لطفاً تعداد سکه دلخواه خود را وارد نمایید:*
""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back"}],
                    [{"text": "✖️لغو خرید سکه", "callback_data": "cancel"}]
                ]
            }
        }
    )


# =========================
# PREVIEW
# =========================
def preview(chat_id):
    amount = user_amount[chat_id]
    phone = user_phone[chat_id]
    total = amount * PRICE_SELL

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"""
*🧾 پیش‌نمایش
 ━━━━━━━━━━━━ 

📦 نام سرویس: خرید سکه بله
✴️ تعداد: {fmt(amount)} سکه
💵 مبلغ قابل پرداخت: {fmt(total)} تومان
📱 مقصد واریز سکه: {phone}

✅️ اگر اطلاعات سفارش درست است، دکمه پرداخت و ثبت سفارش را بزنید.
⚠️ بعد از ثبت سفارش، امکان تغییر اطلاعات وجود ندارد.*
""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "💳 پرداخت", "callback_data": "pay"}],
                    [{"text": "✏️ ویرایش", "callback_data": "edit"}],
                    [{"text": "🔙 منو", "callback_data": "back"}]
                ]
            }
        }
    )


# =========================
# SELL STEP
# =========================
def send_sell(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"""*⚜️ فروش سکه ⚜️

✨ ویژه: بسته به نیاز شما، از 200 تا 10,000 سکه به فروش بگذارید.

💰 قیمت هر 211 سکه: {fmt(PRICE_BUY)} هزار تومان!

🚀 پیشنهاد ویژه: 211 سکه را با {fmt(PRICE_BUY)} هزار تومان به فروش بگذارید!

📌 مرحله 1 از 4

💐 لطفاً تعداد سکه دلخواه خود را وارد نمایید:*
""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back"}],
                    [{"text": "✖️لغو فروش سکه", "callback_data": "cancel"}]
                ]
            }
        }
    )


# =========================
# SELL PREVIEW (مرحله 3 از 4)
# =========================
def sell_preview(chat_id):
    amount = sell_amount[chat_id]
    phone = sell_phone[chat_id]
    total = round(amount * PRICE_BUY * 1000 / SELL_UNIT)

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"""
*🧾 پیش‌نمایش
 ━━━━━━━━━━━━ 

📦 نام سرویس: فروش سکه {SERVICE_NAME}
✴️ تعداد: {fmt(amount)} سکه
💵 مبلغ قابل پرداخت: {fmt(total)} تومان
📱 مقصد واریز سکه: {phone}

✅️ اکنون اگر اطلاعات درست است شماره کارت خود جهت واریز مبلغ را ارسال نمایید.
⚠️ شماره کارت ارسالی بدون هیچ کاراکتر و فاصله ای ارسال گردد (به صورت عددی)*
""",
            "parse_mode": "Markdown"
        }
    )


# =========================
# SELL FINAL CONFIRM (مرحله 4 از 4)
# =========================
def sell_final(chat_id):
    amount = sell_amount[chat_id]
    phone = sell_phone[chat_id]
    card = sell_card[chat_id]
    total = round(amount * PRICE_BUY * 1000 / SELL_UNIT)

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"""*✅️ شماره کارت ثبت شد: {card}
 ━━━━━━━━━━━━ 

📦 نام سرویس: فروش سکه {SERVICE_NAME} 
✴️ تعداد: {fmt(amount)} سکه
💵 مبلغ قابل دریافت: {fmt(total)} تومان
📱 مبدأ واریز سکه: {phone}
💳 شماره کارت مقصد: {card}

 ━━━━━━━━━━━━ 
📞 شماره تلفنی که باید سکه به آن واریز شود:
09014285820

 ━━━━━━━━━━━━ 

📌 مرحله 4 از 4 - ارسال اسکرین شات

⚠️ لطفاً پس از واریز سکه به شماره 09014285820
🎁 یک اسکرین شات از واریز سکه ارسال کنید.

✅️ روی دکمه ارسال اسکرین شات کلیک کرده و تصویر را ارسال کنید.*""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "📸 ارسال اسکرین شات", "callback_data": "sell_screenshot"}],
                    [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back"}]
                ]
            }
        }
    )


# =========================
# SUPPORT
# =========================
def send_support(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": """*📞 پشتیبانی

✅️ برای ارتباط مستقیم و گفت و گو با پشتیبان میتوانید به آیدی زیر مراجعه نمایید:
‎@ARKA_SUPPORT_IR

〽️ همچنین برای ثبت تیکت و ارسال پیام مستقیماً پیام خود را میتوانید وارد کنید.

⚠️ برای لغو عملیات روی دکمه زیر کلیک کنید.*""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "back"}]
                ]
            }
        }
    )


def notify_admin_ticket(t_id):
    t = tickets[t_id]
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": ADMIN_ID,
            "text": f"""*📩 تیکت جدید ثبت شد!*

📦 کد تیکت: {t_id}
🆔 آیدی عددی کاربر: `{t['chat_id']}`

✉️ متن پیام:
{t['text']}""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "✉️ پاسخ به تیکت", "callback_data": f"ticket_reply_{t_id}"}],
                    [{"text": "✅ بستن تیکت", "callback_data": f"ticket_close_{t_id}"}]
                ]
            }
        }
    )


# =========================
def invoice(chat_id):
    global order_id

    amount = user_amount[chat_id]
    phone = user_phone[chat_id]
    total = amount * PRICE_SELL

    order_id += 1
    current_order = order_id

    orders[current_order] = {
        "chat_id": chat_id,
        "amount": amount,
        "phone": phone,
        "total": total,
        "status": "pending",
        "type": "buy",
        "confirmed": False
    }

    result = requests.post(
        f"{BASE_URL}/sendInvoice",
        json={
            "chat_id": chat_id,

            "title": "💐 خرید سکه بله ✔️",

            "description": f"""📦 کد سفارش: {current_order}
〽️ تعداد سکه: {fmt(amount)}
📱 شماره تلفن: {phone}

💵 مبلغ پرداخت: {fmt(total)} تومان""",

            "photo_url": "https://i.postimg.cc/76QP2ZFL/file-000000001c5c720ab21fbfc8b1a5a9f9.png",

            "payload": f"order_{current_order}",
            "provider_token": PROVIDER_TOKEN,
            "currency": "IRR",

            "prices": [
                {
                    "label": "خرید سکه",
                    "amount": total * 10
                }
            ],

            "start_parameter": "pay_coin"
        }
    ).json()

    print("INVOICE RESULT =", result)


# =========================
# PRE CHECKOUT
# =========================
def pre_ok(qid):
    requests.post(
        f"{BASE_URL}/answerPreCheckoutQuery",
        json={
            "pre_checkout_query_id": qid,
            "ok": True
        }
    )


# =========================
# SUCCESS PAYMENT
# =========================
def success(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": """*مشترک گرامی، پرداخت شما با موفقیت انجام شد!✔️

تا دقایقی دیگر سفارش شما واریز می گردد!📱

آرکا، راه خرید امن شماست!💐*""",
            "parse_mode": "Markdown"
        }
    )


# =========================
# SUCCESS SELL
# =========================
def success_sell(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": """*مشترک گرامی، پرداخت شما با موفقیت انجام شد!✔️

تا دقایقی دیگر سفارش شما واریز می گردد!📱

آرکا، راه فروش امن شماست!💐*""",
            "parse_mode": "Markdown"
        }
    )


# =========================
# ADMIN PANEL - MAIN MENU
# =========================
def admin_menu(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "*🛠 پنل مدیریت آرکا*\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "📊 آمار کلی", "callback_data": "admin_stats"}],
                    [{"text": "👥 لیست کاربران", "callback_data": "admin_users"}],
                    [{"text": "📢 ارسال پیام همگانی", "callback_data": "admin_broadcast"}],
                    [{"text": "💰 تغییر نرخ سکه", "callback_data": "admin_price"}],
                    [{"text": "📦 ثبت موجودی", "callback_data": "admin_balance"}],
                    [{"text": "🟡 سفارش‌های فعال", "callback_data": "admin_orders_pending"}],
                    [{"text": "🟢 سفارش‌های تکمیل‌شده", "callback_data": "admin_orders_done"}],
                    [{"text": "📩 تیکت‌های فعال", "callback_data": "admin_tickets_pending"}],
                    [{"text": "📋 تمامی تیکت‌ها", "callback_data": "admin_tickets_all"}],
                    [{"text": "🚫 کاربران مسدود", "callback_data": "admin_blocked"}],
                    [{"text": "⛔️ غیرفعال‌سازی خدمات", "callback_data": "admin_disable"}],
                    [{"text": "✅ فعال‌سازی خدمات", "callback_data": "admin_enable"}],
                    [{"text": "🔄 بروزرسانی پنل", "callback_data": "admin_refresh"}],
                ]
            }
        }
    )


def back_button():
    return {"inline_keyboard": [[{"text": "🔙 بازگشت به پنل", "callback_data": "admin_back"}]]}


# =========================
# STATS
# =========================
def admin_stats(chat_id):
    total_users = len(user_state)
    pending_users = sum(1 for s in user_state.values() if s is not None)
    pending_count = sum(1 for o in orders.values() if o["status"] == "pending")
    done_count = sum(1 for o in orders.values() if o["status"] == "completed")
    blocked_count = len(blocked_users)
    pending_tickets = sum(1 for t in tickets.values() if t["status"] == "pending")

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"""*📊 آمار کلی ربات*

👥 تعداد کل کاربران ثبت‌شده: {fmt(total_users)}
⏳ کاربران در حال خرید: {fmt(pending_users)}
🚫 کاربران مسدود: {fmt(blocked_count)}

🧾 تعداد کل سفارش‌ها: {fmt(order_id)}
🟡 سفارش‌های فعال (در انتظار پرداخت): {fmt(pending_count)}
🟢 سفارش‌های تکمیل‌شده: {fmt(done_count)}

📩 تیکت‌های فعال: {fmt(pending_tickets)}
📋 تعداد کل تیکت‌ها: {fmt(ticket_id)}

💎 نرخ خرید: {fmt(PRICE_BUY)} هزار تومان
📈 نرخ فروش: {fmt(PRICE_SELL)} هزار تومان

📦 موجودی فعلی ربات: {fmt(BOT_BALANCE)} سکه""",
            "parse_mode": "Markdown",
            "reply_markup": back_button()
        }
    )


# =========================
# USERS LIST
# =========================
def admin_users(chat_id):
    if not user_state:
        requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "هیچ کاربری ثبت نشده است.",
                "reply_markup": back_button()
            }
        )
        return

    keyboard = []
    for uid in list(user_state.keys())[-30:]:
        label = f"🆔 {uid}"
        if uid in blocked_users:
            label += " 🚫"
        keyboard.append([{"text": label, "callback_data": f"user_{uid}"}])

    keyboard.append([{"text": "🔙 بازگشت به پنل", "callback_data": "admin_back"}])

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "*👥 لیست کاربران (حداکثر ۳۰ مورد آخر):*\n\nروی هر کاربر بزنید تا گزینه‌های مدیریت آن نمایش داده شود.",
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": keyboard}
        }
    )


def admin_user_detail(chat_id, uid):
    is_blocked = uid in blocked_users
    block_btn_text = "✅ رفع مسدودیت" if is_blocked else "🚫 مسدود کردن"
    block_btn_data = f"unblock_{uid}" if is_blocked else f"block_{uid}"

    status_text = "🚫 مسدود" if is_blocked else "🟢 آزاد"
    amount_info = user_amount.get(uid)
    phone_info = user_phone.get(uid)

    text = f"""*👤 اطلاعات کاربر*

🆔 آیدی عددی: `{uid}`
📌 وضعیت: {status_text}"""

    if amount_info:
        text += f"\n✴️ آخرین تعداد سکه واردشده: {fmt(amount_info)}"
    if phone_info:
        text += f"\n📱 آخرین شماره ثبت‌شده: {phone_info}"

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "💬 رفتن به پیوی کاربر / ارسال پیام", "callback_data": f"goto_{uid}"}],
                    [{"text": block_btn_text, "callback_data": block_btn_data}],
                    [{"text": "🔙 بازگشت به لیست کاربران", "callback_data": "admin_users"}],
                    [{"text": "🔙 بازگشت به پنل", "callback_data": "admin_back"}]
                ]
            }
        }
    )


# =========================
# BROADCAST
# =========================
def admin_broadcast_prompt(chat_id):
    admin_state[chat_id] = "broadcast"
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "*📢 پیام همگانی خود را ارسال کنید تا برای تمام کاربران فوروارد شود.*\n\nبرای لغو، /admin را بزنید.",
            "parse_mode": "Markdown"
        }
    )


def broadcast_message(text):
    sent = 0
    for uid in list(user_state.keys()):
        if uid in blocked_users:
            continue
        try:
            requests.post(
                f"{BASE_URL}/sendMessage",
                json={
                    "chat_id": uid,
                    "text": f"*📢 پیام از طرف ادمین:*\n\n{text}",
                    "parse_mode": "Markdown"
                }
            )
            sent += 1
        except Exception:
            pass
    return sent


# =========================
# PRICE MENU
# =========================
def admin_price_menu(chat_id):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"""*💰 تغییر نرخ سکه*

💎 نرخ خرید فعلی (هر 211 سکه): {fmt(PRICE_BUY)} هزار تومان
📈 نرخ فروش فعلی (هر 1000 سکه): {fmt(PRICE_SELL)} هزار تومان

کدام نرخ را می‌خواهید تغییر دهید؟""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "💎 تغییر نرخ خرید سکه", "callback_data": "price_buy"}],
                    [{"text": "📈 تغییر نرخ فروش سکه", "callback_data": "price_sell"}],
                    [{"text": "🔙 بازگشت به پنل", "callback_data": "admin_back"}]
                ]
            }
        }
    )


def admin_price_prompt(chat_id, which):
    admin_state[chat_id] = f"price_{which}"
    current = PRICE_BUY if which == "buy" else PRICE_SELL
    label = "خرید" if which == "buy" else "فروش"

    unit = "211" if which == "buy" else "1000"

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"*💰 نرخ فعلی {label} هر {unit} سکه: {fmt(current)} هزار تومان*\n\nنرخ جدید را به‌صورت عدد ارسال کنید:",
            "parse_mode": "Markdown"
        }
    )


# =========================
# BOT BALANCE (موجودی)
# =========================
def admin_balance_prompt(chat_id):
    admin_state[chat_id] = "balance"
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"*📦 موجودی فعلی ربات: {fmt(BOT_BALANCE)} سکه*\n\nموجودی جدید را به‌صورت عدد ارسال کنید:",
            "parse_mode": "Markdown"
        }
    )


# =========================
# SERVICES TOGGLE
# =========================
def admin_set_services(chat_id, enabled):
    global services_enabled
    services_enabled = enabled
    status = "✅ فعال" if enabled else "⛔️ غیرفعال"
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": f"*وضعیت خدمات با موفقیت روی {status} تغییر کرد.*",
            "parse_mode": "Markdown"
        }
    )
    admin_menu(chat_id)


# =========================
# ORDERS LIST
# =========================
def admin_orders_list(chat_id, status):
    filtered = [(oid, o) for oid, o in orders.items() if o["status"] == status]

    if not filtered:
        text = "هیچ سفارشی در این بخش وجود ندارد."
        requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": back_button()
            }
        )
        return

    title = "🟡 سفارش‌های فعال" if status == "pending" else "🟢 سفارش‌های تکمیل‌شده"

    keyboard = []
    lines = [f"*{title}*\n"]

    for oid, o in filtered[-20:]:
        order_type = o.get("type", "buy")
        confirm_mark = " ✅" if o.get("confirmed") else ""

        if order_type == "sell":
            type_label = "🛍 فروش"
            lines.append(
                f"📦 کد: {oid}{confirm_mark} | {type_label} | 🆔 `{o['chat_id']}` | "
                f"✴️ {fmt(o['amount'])} سکه | 💵 {fmt(o['total'])} تومان | 💳 {o.get('card', '-')}"
            )
        else:
            type_label = "〽️ خرید"
            status_note = "" if status == "completed" else " (در انتظار پرداخت)"
            lines.append(
                f"📦 کد: {oid}{confirm_mark} | {type_label}{status_note} | 🆔 `{o['chat_id']}` | "
                f"✴️ {fmt(o['amount'])} سکه | 💵 {fmt(o['total'])} تومان"
            )

        if status == "pending":
            if order_type == "sell" and not o.get("confirmed"):
                keyboard.append([{"text": f"✅ تأیید و ارسال سفارش {oid} به کانال", "callback_data": f"confirm_{oid}"}])
                keyboard.append([{"text": f"✉️ ارسال پیام برای سفارش {oid}", "callback_data": f"reply_{oid}"}])

        if status == "completed":
            keyboard.append([{"text": f"✉️ ارسال پیام برای سفارش {oid}", "callback_data": f"reply_{oid}"}])
            if order_type == "buy" and not o.get("confirmed"):
                keyboard.append([{"text": f"✅ تأیید پرداخت سفارش {oid}", "callback_data": f"confirm_{oid}"}])

    keyboard.append([{"text": "🔙 بازگشت به پنل", "callback_data": "admin_back"}])

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "\n".join(lines),
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": keyboard}
        }
    )


# =========================
# TICKETS LIST
# =========================
def admin_tickets_list(chat_id, only_pending):
    if only_pending:
        filtered = [(tid, t) for tid, t in tickets.items() if t["status"] == "pending"]
        title = "📩 تیکت‌های فعال"
    else:
        filtered = list(tickets.items())
        title = "📋 تمامی تیکت‌ها"

    if not filtered:
        requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "هیچ تیکتی در این بخش وجود ندارد.",
                "reply_markup": back_button()
            }
        )
        return

    keyboard = []
    lines = [f"*{title}*\n"]

    for tid, t in filtered[-20:]:
        status_label = "🟡 باز" if t["status"] == "pending" else "🟢 بسته"
        msg_preview = t["text"]
        if len(msg_preview) > 60:
            msg_preview = msg_preview[:60] + "..."

        lines.append(
            f"📦 کد: {tid} | {status_label} | 🆔 `{t['chat_id']}`\n✉️ {msg_preview}"
        )

        if t["status"] == "pending":
            keyboard.append([{"text": f"✉️ پاسخ به تیکت {tid}", "callback_data": f"ticket_reply_{tid}"}])
            keyboard.append([{"text": f"✅ بستن تیکت {tid}", "callback_data": f"ticket_close_{tid}"}])

    keyboard.append([{"text": "🔙 بازگشت به پنل", "callback_data": "admin_back"}])

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "\n\n".join(lines),
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": keyboard}
        }
    )


# =========================
# BLOCKED USERS LIST
# =========================
def admin_blocked_list(chat_id):
    if not blocked_users:
        requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "هیچ کاربری مسدود نشده است.",
                "reply_markup": back_button()
            }
        )
        return

    keyboard = []
    for uid in list(blocked_users):
        keyboard.append([{"text": f"🆔 {uid} - رفع مسدودیت", "callback_data": f"unblock_{uid}"}])

    keyboard.append([{"text": "🔙 بازگشت به پنل", "callback_data": "admin_back"}])

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "*🚫 لیست کاربران مسدود:*",
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": keyboard}
        }
    )


# =========================
# NOTIFY ADMIN ON SUCCESSFUL PAYMENT
# =========================
def notify_admin_purchase(order_num):
    o = orders[order_num]

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": ADMIN_ID,
            "text": f"""*💰 خرید جدید ثبت شد!*

📦 کد سفارش: {order_num}
🆔 آیدی عددی کاربر: `{o['chat_id']}`
✴️ تعداد سکه: {fmt(o['amount'])}
📱 شماره تلفن: {o['phone']}
💵 مبلغ پرداختی: {fmt(o['total'])} تومان

✅ پرداخت با موفقیت انجام شده است.""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "✉️ ارسال پیام به کاربر (واریز شد)", "callback_data": f"reply_{order_num}"}]
                ]
            }
        }
    )


# =========================
# NOTIFY ADMIN ON NEW SELL ORDER
# =========================
def notify_admin_sell(order_num):
    o = orders[order_num]

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": ADMIN_ID,
            "text": f"""*🛍 سفارش فروش جدید ثبت شد!*

📦 کد سفارش: {order_num}
🆔 آیدی عددی کاربر: `{o['chat_id']}`
✴️ تعداد سکه: {fmt(o['amount'])}
📱 مبدأ واریز سکه: {o['phone']}
💳 شماره کارت مقصد: {o['card']}
💵 مبلغ قابل دریافت: {fmt(o['total'])} تومان

✅ کاربر اسکرین شات واریز را ارسال کرد. این سفارش در بخش «سفارش‌های فعال» منتظر تأیید شماست.""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "✅ تأیید و ارسال به کانال", "callback_data": f"confirm_{order_num}"}],
                    [{"text": "✉️ ارسال پیام به کاربر", "callback_data": f"reply_{order_num}"}]
                ]
            }
        }
    )


# =========================
# POST TO CHANNEL ON CONFIRM
# =========================
def post_order_to_channel(order_num):
    o = orders[order_num]

    if o.get("type") == "sell":
        post_sell_order_to_channel(order_num)
    else:
        post_buy_order_to_channel(order_num)


def post_buy_order_to_channel(order_num):
    o = orders[order_num]
    now = datetime.datetime.now().strftime("%Y/%m/%d - %H:%M:%S")

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": CHANNEL_ID,
            "text": f"""✅ *یک سفارش جدید ثبت شد!*

🧾 *اطلاعات سفارش:*
🏷 *نام سرویس:* فروش سکه {SERVICE_NAME} 💰
📦 *مقدار:* {fmt(o['amount'])} سکه
💰 *قیمت:* {fmt(o['total'])} تومان
🕒 *زمان فروش:* {now}""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🤖ربات خرید و فروش سکه", "url": "https://ble.ir/Arka_Coin_Bot"}]
                ]
            }
        }
    )


def post_sell_order_to_channel(order_num):
    o = orders[order_num]
    now = datetime.datetime.now().strftime("%Y/%m/%d - %H:%M:%S")

    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id": CHANNEL_ID,
            "text": f"""✅ *یک سفارش جدید ثبت شد!*

🧾 *اطلاعات سفارش:*
🏷 *نام سرویس:* خرید سکه {SERVICE_NAME} 💰
📦 *مقدار:* {fmt(o['amount'])} سکه
💰 *قیمت:* {fmt(o['total'])} تومان
🕒 *زمان خرید:* {now}""",
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🤖ربات خرید و فروش سکه", "url": "https://ble.ir/Arka_Coin_Bot"}]
                ]
            }
        }
    )


# =========================
# LOOP
# =========================
while True:
    try:
        r = requests.get(
            f"{BASE_URL}/getUpdates",
            params={"offset": last_update_id + 1},
            timeout=30
        ).json()

        for u in r.get("result", []):
            last_update_id = u["update_id"]

            # ================= MESSAGE =================
            if "message" in u:

                msg = u["message"]
                text = msg.get("text", "")
                chat_id = msg["chat"]["id"]
                chat_type = msg["chat"].get("type", "private")

                # ===== فقط چت‌های خصوصی پاسخ داده شوند (جلوگیری از پاسخ اشتباه در کانال/گروه) =====
                if chat_type != "private":
                    continue

                # ===== ADMIN COMMAND =====
                if text == "/admin":
                    if chat_id == ADMIN_ID:
                        admin_menu(chat_id)
                    else:
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": "*❌ شما ادمین نیستید!*",
                                "parse_mode": "Markdown"
                            }
                        )
                    continue

                # ===== ADMIN TEXT INPUT HANDLING =====
                if chat_id == ADMIN_ID and admin_state.get(chat_id):

                    state = admin_state.get(chat_id)

                    if state == "broadcast":
                        admin_state[chat_id] = None
                        count = broadcast_message(text)
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": f"*✅ پیام برای {fmt(count)} کاربر ارسال شد.*",
                                "parse_mode": "Markdown"
                            }
                        )
                        admin_menu(chat_id)
                        continue

                    if state == "balance":
                        if text.isdigit():
                            BOT_BALANCE = int(text)
                            admin_state[chat_id] = None
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"*✅ موجودی ربات با موفقیت به {fmt(BOT_BALANCE)} سکه تغییر کرد.*",
                                    "parse_mode": "Markdown"
                                }
                            )
                            admin_menu(chat_id)
                        else:
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": "*❌ لطفاً فقط عدد ارسال کنید.*",
                                    "parse_mode": "Markdown"
                                }
                            )
                        continue

                    if state in ("price_buy", "price_sell"):
                        if text.isdigit():
                            new_price = int(text)

                            if state == "price_buy":
                                PRICE_BUY = new_price
                                label = "خرید"
                            else:
                                PRICE_SELL = new_price
                                label = "فروش"

                            admin_state[chat_id] = None

                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"*✅ نرخ {label} با موفقیت به {fmt(new_price)} هزار تومان تغییر کرد.*\n\nاین تغییر در منوی اصلی، صفحه خرید و محاسبه مبلغ سفارش‌ها به‌صورت خودکار اعمال می‌شود.",
                                    "parse_mode": "Markdown"
                                }
                            )
                            admin_menu(chat_id)
                        else:
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": "*❌ لطفاً فقط عدد ارسال کنید.*",
                                    "parse_mode": "Markdown"
                                }
                            )
                        continue

                    if state.startswith("ticket_reply_"):
                        t_id = int(state.split("_")[2])
                        t = tickets.get(t_id)
                        admin_state[chat_id] = None

                        if t:
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": t["chat_id"],
                                    "text": f"*📩 پاسخ پشتیبانی به تیکت شما:*\n\n{text}",
                                    "parse_mode": "Markdown"
                                }
                            )
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"*✅ پاسخ برای تیکت {t_id} ارسال شد.*",
                                    "parse_mode": "Markdown"
                                }
                            )
                        continue

                    if state.startswith("reply_"):
                        target_chat = admin_target_chat.get(chat_id)
                        admin_state[chat_id] = None

                        if target_chat:
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": target_chat,
                                    "text": text,
                                    "parse_mode": "Markdown"
                                }
                            )
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": "*✅ پیام برای کاربر ارسال شد.*",
                                    "parse_mode": "Markdown"
                                }
                            )
                        continue

                # ===== BLOCKED USER CHECK =====
                if chat_id in blocked_users:
                    requests.post(
                        f"{BASE_URL}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": "*⛔️ دسترسی شما به ربات مسدود شده است.*",
                            "parse_mode": "Markdown"
                        }
                    )
                    continue

                # ===== JOIN CHECK (every message) =====
                if text != "/start" and not is_member(chat_id):
                    user_state[chat_id] = None
                    send_join_required(chat_id)
                    continue

                if "successful_payment" in msg:
                    user_state[chat_id] = None

                    amount_for_admin = user_amount.get(chat_id)
                    phone_for_admin = user_phone.get(chat_id)

                    # پیدا کردن آخرین سفارش در انتظار این کاربر و تکمیل آن
                    target_order = None
                    for oid, o in orders.items():
                        if o["chat_id"] == chat_id and o["status"] == "pending" and o.get("type", "buy") == "buy":
                            target_order = oid

                    if target_order:
                        orders[target_order]["status"] = "completed"
                        pending_orders[target_order] = chat_id
                        notify_admin_purchase(target_order)

                    if chat_id in user_amount:
                        del user_amount[chat_id]

                    if chat_id in user_phone:
                        del user_phone[chat_id]

                    success(chat_id)
                    continue

                if text == "/start":
                    user_state[chat_id] = None
                    if is_member(chat_id):
                        menu(chat_id)
                    else:
                        send_join_required(chat_id)
                    continue

                # ===================== SUPPORT FLOW =====================
                if user_state.get(chat_id) == "support":
                    ticket_id += 1
                    current_ticket = ticket_id

                    tickets[current_ticket] = {
                        "chat_id": chat_id,
                        "text": text,
                        "status": "pending"
                    }

                    notify_admin_ticket(current_ticket)

                    requests.post(
                        f"{BASE_URL}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": """*✅️ کاربر گرامی، پیام شما با موفقیت ارسال گردید.
منتظر پاسخ پشتیبانان ما بمانید!💐*""",
                            "parse_mode": "Markdown"
                        }
                    )

                    user_state[chat_id] = None
                    continue

                if user_state.get(chat_id) is None:

                    if text == "〽️ خرید سکه کانال بله":
                        user_state[chat_id] = "amount"
                        send_buy(chat_id)
                    elif text == "🛍فروش سکه کانال بله":
                        user_state[chat_id] = "sell_amount"
                        send_sell(chat_id)
                    elif text == "📞 پشتیبانی":
                        user_state[chat_id] = "support"
                        send_support(chat_id)
                    else:
                        if text != "/start":
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": "*لطفاً از دکمه های منو استفاده کنید!❌️*",
                                    "parse_mode": "Markdown"
                                }
                            )
                    continue

                if user_state.get(chat_id) == "amount":

                    if not text.isdigit():
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": "*لطفاً تعداد سکه را به صورت عدد وارد کنید.❌️*",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

                    amount = int(text)

                    if amount < MIN_COIN:
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": """*❌ حداقل خرید ۲۰۰ سکه است.
لطفاً دوباره تعداد را وارد کنید:*""",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

                    if amount > BOT_BALANCE:
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": f"""*〽️کاربر گرامی، موجودی ربات معادل {fmt(BOT_BALANCE)} سکه است.✅️
لطفاً تعداد سکه جهت خرید را وارد نمایید.💐*""",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

                    user_amount[chat_id] = amount
                    user_state[chat_id] = "phone"

                    requests.post(
                        f"{BASE_URL}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": "*شماره تلفن خود را وارد کنید:📱*",
                            "parse_mode": "Markdown"
                        }
                    )
                    continue

                if user_state.get(chat_id) == "phone":

                    if not text.isdigit() or len(text) != 11:
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": """*❌ شماره تلفن نامعتبر است!
لطفاً یک شماره ۱۱ رقمی معتبر وارد کنید.
مثال: 09123456789

⚠️ توجه: این شماره باید شماره شما در نرم‌افزار خارجی باشد که سکه به آن واریز می‌شود.*""",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

                    user_phone[chat_id] = text
                    preview(chat_id)
                    continue

                # ===================== SELL FLOW =====================
                if user_state.get(chat_id) == "sell_amount":

                    if not text.isdigit():
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": "*لطفاً تعداد سکه را به صورت عدد وارد کنید.❌️*",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

                    amount = int(text)

                    if amount < MIN_COIN:
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": """*❌ حداقل خرید ۲۰۰ سکه است.
لطفاً دوباره تعداد را وارد کنید:*""",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

                    if amount > MAX_COIN:
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": """*❌ حداکثر فروش ۱۰,۰۰۰ سکه است.
لطفاً دوباره تعداد را وارد کنید:*""",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

                    sell_amount[chat_id] = amount
                    user_state[chat_id] = "sell_phone"

                    requests.post(
                        f"{BASE_URL}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": "*شماره تلفن خود را وارد کنید:📱*",
                            "parse_mode": "Markdown"
                        }
                    )
                    continue

                if user_state.get(chat_id) == "sell_phone":

                    if not text.isdigit() or len(text) != 11:
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": """*❌ شماره تلفن نامعتبر است!
لطفاً یک شماره ۱۱ رقمی معتبر وارد کنید.
مثال: 09123456789

⚠️ توجه: این شماره باید شماره شما در نرم‌افزار خارجی باشد که سکه به آن واریز می‌شود.*""",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

                    sell_phone[chat_id] = text
                    user_state[chat_id] = "sell_card"
                    sell_preview(chat_id)
                    continue

                if user_state.get(chat_id) == "sell_card":

                    if not text.isdigit() or len(text) != 16:
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": """*❌ شماره کارت نامعتبر است!

📌 شماره کارت باید ۱۶ رقم باشد.

✅ مثال صحیح:
5022291552222455

⚠️ لطفاً شماره کارت معتبر خود را وارد کنید (بدون فاصله):*""",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

                    sell_card[chat_id] = text
                    user_state[chat_id] = "sell_wait_screenshot_button"
                    sell_final(chat_id)
                    continue

                if user_state.get(chat_id) == "sell_screenshot":

                    if "photo" in msg:
                        order_id += 1
                        current_order = order_id

                        amount = sell_amount.get(chat_id)
                        phone = sell_phone.get(chat_id)
                        card = sell_card.get(chat_id)
                        total = round(amount * PRICE_BUY * 1000 / SELL_UNIT)

                        orders[current_order] = {
                            "chat_id": chat_id,
                            "amount": amount,
                            "phone": phone,
                            "card": card,
                            "total": total,
                            "status": "pending",
                            "type": "sell",
                            "confirmed": False
                        }

                        pending_orders[current_order] = chat_id

                        notify_admin_sell(current_order)
                        success_sell(chat_id)

                        user_state[chat_id] = None
                        sell_amount.pop(chat_id, None)
                        sell_phone.pop(chat_id, None)
                        sell_card.pop(chat_id, None)
                        continue
                    else:
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": "*❌️در صفحه ارسال عکس مجاز است.*",
                                "parse_mode": "Markdown"
                            }
                        )
                        continue

            # ================= CALLBACK =================
            if "callback_query" in u:
                cb = u["callback_query"]
                data = cb["data"]
                chat_id = cb["message"]["chat"]["id"]

                if data != "joined_check" and chat_id != ADMIN_ID and not is_member(chat_id):
                    user_state[chat_id] = None
                    send_join_required(chat_id)
                    continue

                if data == "joined_check":
                    if is_member(chat_id):
                        user_state[chat_id] = None
                        menu(chat_id)
                    else:
                        send_join_failed(chat_id)

                elif data == "back":
                    user_state[chat_id] = None
                    menu(chat_id)

                elif data == "edit":
                    user_state[chat_id] = "amount"
                    send_buy(chat_id)

                elif data == "cancel":
                    user_state[chat_id] = None
                    menu(chat_id)

                elif data == "pay":
                    invoice(chat_id)

                elif data == "sell_screenshot":
                    user_state[chat_id] = "sell_screenshot"
                    requests.post(
                        f"{BASE_URL}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": """*📸 لطفاً اسکرین شات رسید واریز سکه را ارسال کنید.

⚠️ فقط تصویر ارسال شود.*""",
                            "parse_mode": "Markdown"
                        }
                    )

                # ===== ADMIN CALLBACKS =====
                elif data == "admin_back" or data == "admin_refresh":
                    if chat_id == ADMIN_ID:
                        admin_menu(chat_id)

                elif data == "admin_balance":
                    if chat_id == ADMIN_ID:
                        admin_balance_prompt(chat_id)

                elif data == "admin_stats":
                    if chat_id == ADMIN_ID:
                        admin_stats(chat_id)

                elif data == "admin_users":
                    if chat_id == ADMIN_ID:
                        admin_users(chat_id)

                elif data == "admin_broadcast":
                    if chat_id == ADMIN_ID:
                        admin_broadcast_prompt(chat_id)

                elif data == "admin_price":
                    if chat_id == ADMIN_ID:
                        admin_price_menu(chat_id)

                elif data == "price_buy":
                    if chat_id == ADMIN_ID:
                        admin_price_prompt(chat_id, "buy")

                elif data == "price_sell":
                    if chat_id == ADMIN_ID:
                        admin_price_prompt(chat_id, "sell")

                elif data == "admin_orders_pending":
                    if chat_id == ADMIN_ID:
                        admin_orders_list(chat_id, "pending")

                elif data == "admin_orders_done":
                    if chat_id == ADMIN_ID:
                        admin_orders_list(chat_id, "completed")

                elif data == "admin_tickets_pending":
                    if chat_id == ADMIN_ID:
                        admin_tickets_list(chat_id, True)

                elif data == "admin_tickets_all":
                    if chat_id == ADMIN_ID:
                        admin_tickets_list(chat_id, False)

                elif data == "admin_blocked":
                    if chat_id == ADMIN_ID:
                        admin_blocked_list(chat_id)

                elif data == "admin_disable":
                    if chat_id == ADMIN_ID:
                        admin_set_services(chat_id, False)

                elif data == "admin_enable":
                    if chat_id == ADMIN_ID:
                        admin_set_services(chat_id, True)

                # ===== USER DETAIL =====
                elif data.startswith("user_"):
                    if chat_id == ADMIN_ID:
                        target_uid = int(data.split("_")[1])
                        admin_user_detail(chat_id, target_uid)

                # ===== GO TO USER PV / DIRECT MESSAGE =====
                elif data.startswith("goto_"):
                    if chat_id == ADMIN_ID:
                        target_uid = int(data.split("_")[1])
                        admin_target_chat[chat_id] = target_uid
                        admin_state[chat_id] = "reply_direct"
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": f"*✍️ پیام خود را برای ارسال مستقیم به کاربر `{target_uid}` بنویسید:*",
                                "parse_mode": "Markdown"
                            }
                        )

                # ===== BLOCK / UNBLOCK =====
                elif data.startswith("block_"):
                    if chat_id == ADMIN_ID:
                        target_uid = int(data.split("_")[1])
                        blocked_users.add(target_uid)
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": f"*✅ کاربر `{target_uid}` مسدود شد.*",
                                "parse_mode": "Markdown"
                            }
                        )
                        admin_user_detail(chat_id, target_uid)

                elif data.startswith("unblock_"):
                    if chat_id == ADMIN_ID:
                        target_uid = int(data.split("_")[1])
                        blocked_users.discard(target_uid)
                        requests.post(
                            f"{BASE_URL}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": f"*✅ کاربر `{target_uid}` رفع مسدودیت شد.*",
                                "parse_mode": "Markdown"
                            }
                        )
                        admin_user_detail(chat_id, target_uid)

                # ===== TICKET REPLY / CLOSE =====
                elif data.startswith("ticket_reply_"):
                    if chat_id == ADMIN_ID:
                        t_id = int(data.split("_")[2])
                        t = tickets.get(t_id)
                        if t:
                            admin_state[chat_id] = f"ticket_reply_{t_id}"
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"*✍️ پاسخ خود را برای تیکت {t_id} (کاربر `{t['chat_id']}`) بنویسید:*",
                                    "parse_mode": "Markdown"
                                }
                            )
                        else:
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": "*❌ تیکت پیدا نشد.*",
                                    "parse_mode": "Markdown"
                                }
                            )

                elif data.startswith("ticket_close_"):
                    if chat_id == ADMIN_ID:
                        t_id = int(data.split("_")[2])
                        t = tickets.get(t_id)
                        if t:
                            t["status"] = "closed"
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"*✅ تیکت {t_id} بسته شد.*",
                                    "parse_mode": "Markdown"
                                }
                            )
                        else:
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": "*❌ تیکت پیدا نشد.*",
                                    "parse_mode": "Markdown"
                                }
                            )

                # ===== CONFIRM PAYMENT -> POST TO CHANNEL =====
                elif data.startswith("confirm_"):
                    if chat_id == ADMIN_ID:
                        order_num = int(data.split("_")[1])
                        o = orders.get(order_num)

                        if o and not o.get("confirmed"):
                            o["confirmed"] = True

                            if o.get("type") == "sell":
                                o["status"] = "completed"
                                BOT_BALANCE += o["amount"]
                            else:
                                BOT_BALANCE = max(0, BOT_BALANCE - o["amount"])

                            post_order_to_channel(order_num)
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"*✅ سفارش {order_num} تأیید و در کانال منتشر شد.*",
                                    "parse_mode": "Markdown"
                                }
                            )
                            admin_orders_list(chat_id, "completed")
                        else:
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": "*❌ این سفارش قبلاً تأیید شده یا پیدا نشد.*",
                                    "parse_mode": "Markdown"
                                }
                            )

                # ===== REPLY TO ORDER =====
                elif data.startswith("reply_"):
                    if chat_id == ADMIN_ID:
                        order_num = int(data.split("_")[1])
                        target_chat = pending_orders.get(order_num) or orders.get(order_num, {}).get("chat_id")

                        if target_chat:
                            admin_target_chat[chat_id] = target_chat
                            admin_state[chat_id] = data
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": f"*✍️ پیام خود را برای ارسال به کاربر `{target_chat}` بنویسید:*",
                                    "parse_mode": "Markdown"
                                }
                            )
                        else:
                            requests.post(
                                f"{BASE_URL}/sendMessage",
                                json={
                                    "chat_id": chat_id,
                                    "text": "*❌ کاربر مربوط به این سفارش پیدا نشد.*",
                                    "parse_mode": "Markdown"
                                }
                            )

                continue

            # ================= PAYMENT (pre-checkout) =================
            if "pre_checkout_query" in u:
                pre_ok(u["pre_checkout_query"]["id"])
                continue

    except Exception as e:
        print("ERROR:", e)
        time.sleep(2)
