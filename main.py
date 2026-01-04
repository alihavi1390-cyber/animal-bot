#!/usr/bin/env python3
"""
🤖 ربات هوشمند شناسایی حیوانات - نسخه OpenRouter
📸 کاربر عکس می‌فرستد → ربات اطلاعات حیوان را برمی‌گرداند
"""

import os
import json
import logging
import asyncio
import aiohttp
import base64
from io import BytesIO
from typing import Optional, Dict, Any
from datetime import datetime

import telebot
from telebot import apihelper, types
import requests

# ==================== CONFIGURATION ====================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8365956718:AAEcJGYB################8kI875BRaFRmW0x1WTmm_G3qTGE')

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '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')
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Rate limiting
MAX_REQUESTS_PER_USER = 10
MAX_IMAGE_SIZE_MB = 10
REQUEST_TIMEOUT = 30

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('animal_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== BOT INITIALIZATION ====================
apihelper.SESSION_TIME_TO_LIVE = 5 * 60
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode='HTML')
user_requests = {}

# ==================== HELPER FUNCTIONS ====================
def check_rate_limit(user_id: int) -> bool:
    """بررسی محدودیت تعداد درخواست کاربر"""
    now = datetime.now()
    
    if user_id not in user_requests:
        user_requests[user_id] = []
    
    user_requests[user_id] = [
        req_time for req_time in user_requests[user_id]
        if (now - req_time).seconds < 60
    ]
    
    if len(user_requests[user_id]) >= MAX_REQUESTS_PER_USER:
        return False
    
    user_requests[user_id].append(now)
    return True

def encode_image_to_base64(image_bytes: bytes) -> str:
    """تبدیل عکس به base64"""
    encoded = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded}"

async def analyze_with_openrouter(image_base64: str) -> str:
    """
    تحلیل عکس با استفاده از OpenRouter API
    استفاده از مدل Qwen یا هر مدل Vision دیگر
    """
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/alihavi1390-cyber/animal-bot",  # برای OpenRouter لازم است
            "X-Title": "Animal Identification Bot"
        }
        
        prompt = """شما یک کارشناس حیات وحش هستید. این عکس را تحلیل کنید و اطلاعات زیر را به زبان فارسی ارائه دهید:

1. **نام حیوان** (فارسی و لاتین)
2. **خانواده/رده** (Family/Tribe)
3. **زیستگاه طبیعی** (Natural Habitat)
4. **رژیم غذایی** (Diet)
5. **ویژگی‌های فیزیکی بارز** (Physical Characteristics)
6. **وضعیت حفاظت** (Conservation Status)
7. **حقایق جالب** (2-3 مورد)
8. **طول عمر متوسط** (Average Lifespan)

اگر حیوان قابل شناسایی نیست، صادقانه بگویید و در مورد حیوانات مشابه توضیح دهید.

لطفاً پاسخ را با ساختار واضح و با ایموجی‌های مناسب ارائه دهید."""

        payload = {
            "model": "qwen/qwen-2.5-vl-7b-instruct:free",  # مدل قوی‌تر
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_base64}}
                    ]
                }
            ],
            "max_tokens": 1500,
            "temperature": 0.7,
            "stream": False
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return data['choices'][0]['message']['content']
                else:
                    error_text = await response.text()
                    logger.error(f"OpenRouter API Error {response.status}: {error_text}")
                    
                    if response.status == 429:
                        return "⏳ محدودیت Rate Limit. لطفاً یک دقیقه صبر کنید."
                    elif response.status == 401:
                        return "🔑 مشکل در کلید API. لطفاً بررسی کنید."
                    else:
                        return "⚠️ خطا در تحلیل عکس. لطفاً دوباره تلاش کنید."

    except asyncio.TimeoutError:
        logger.error("OpenRouter request timeout")
        return "⏱️ زمان تحلیل عکس به پایان رسید. لطفاً دوباره تلاش کنید."
    except aiohttp.ClientError as e:
        logger.error(f"Network error: {e}")
        return "🌐 خطای شبکه. لطفاً اتصال اینترنت را بررسی کنید."
    except Exception as e:
        logger.error(f"OpenRouter API call failed: {e}")
        return "❌ خطا در ارتباط با سرور تحلیل عکس."

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    """هندلر دستور /start و /help"""
    
    welcome_text = """
<b>🤖 به ربات شناسایی حیوانات خوش آمدید!</b>

<b>📌 نحوه استفاده:</b>
۱. یک عکس واضح از حیوان بفرستید
۲. ربات عکس را با هوش مصنوعی تحلیل می‌کند
۳. اطلاعات کامل حیوان را دریافت می‌کنید

<b>🧠 فناوری:</b>
• موتور: OpenRouter AI
• مدل: Qwen 2.5 Vision
• قابلیت: تحلیل تصاویر پیشرفته

<b>📋 اطلاعات دریافتی:</b>
• نام فارسی و لاتین
• خانواده/رده
• زیستگاه طبیعی
• رژیم غذایی
• ویژگی‌های فیزیکی
• وضعیت حفاظت
• حقایق جالب
• طول عمر متوسط

<b>⚠️ نکات مهم:</b>
• عکس باید واضح و روشن باشد
• حیوان باید در کادر عکس باشد
• پاسخ ممکن است ۱۰-۲۰ ثانیه طول بکشد
• حداکثر حجم عکس: ۱۰ مگابایت

<b>🔧 دستورات:</b>
/start - نمایش این پیام
/stats - آمار استفاده
/about - درباره ربات

<b>🔄 برای شروع، یک عکس بفرستید!</b>
    """
    
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['about'])
def handle_about(message):
    """درباره ربات"""
    about_text = """
<b>🤖 درباره ربات شناسایی حیوانات</b>

<b>🧠 فناوری:</b>
• پلتفرم: OpenRouter.ai
• مدل: Qwen 2.5 Vision 72B
• قابلیت: تحلیل تصاویر و متن
• زبان: فارسی و انگلیسی

<b>🎯 هدف:</b>
کمک به شناخت بهتر حیوانات و طبیعت

<b>⚡ میزبانی:</b>
Railway.app - سرویس ابری قدرتمند

<b>⚠️ محدودیت‌ها:</b>
• فقط حیوانات قابل شناسایی هستند
• عکس‌های تار ممکن است خطا دهند
• تعداد درخواست محدود است

<b>📞 پشتیبانی:</b>
برای گزارش مشکل یا پیشنهاد، پیام دهید.
    """
    bot.reply_to(message, about_text)

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    """نمایش آمار استفاده"""
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    if user_id in user_requests:
        request_count = len(user_requests[user_id])
    else:
        request_count = 0
    
    stats_text = f"""
<b>📊 آمار استفاده شما</b>

<b>👤 کاربر:</b> {user_name}
<b>🆔 شناسه:</b> {user_id}
<b>📨 تعداد درخواست‌ها (۱ دقیقه اخیر):</b> {request_count}
<b>📈 حداکثر مجاز:</b> {MAX_REQUESTS_PER_USER} درخواست در دقیقه

<b>⚡ وضعیت سرویس:</b>
• OpenRouter API: ✅ فعال
• تلگرام: ✅ متصل
• سرور: Railway.app

<b>🔄 برای استفاده بیشتر، صبر کنید...</b>
    """
    
    bot.reply_to(message, stats_text)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """هندلر دریافت عکس"""
    
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    logger.info(f"📸 دریافت عکس از کاربر {user_name} (ID: {user_id})")
    
    # بررسی rate limit
    if not check_rate_limit(user_id):
        bot.reply_to(message, "⏸️ تعداد درخواست‌های شما زیاد است. لطفاً ۱ دقیقه صبر کنید.")
        return
    
    try:
        # ارسال پیام "در حال پردازش"
        processing_msg = bot.send_message(
            message.chat.id,
            "🔍 <b>در حال تحلیل عکس...</b>\nلطفاً کمی صبر کنید ⏳",
            reply_to_message_id=message.message_id
        )
        
        # دریافت بزرگترین سایز عکس
        photo_info = message.photo[-1]
        file_info = bot.get_file(photo_info.file_id)
        
        # ساخت لینک مستقیم
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"
        logger.info(f"📥 دانلود عکس از: {file_info.file_path}")
        
        # دانلود عکس
        response = requests.get(file_url, timeout=10)
        response.raise_for_status()
        
        image_bytes = response.content
        
        # بررسی حجم عکس
        if len(image_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            bot.edit_message_text(
                "❌ حجم عکس بیش از حد مجاز است (حداکثر ۱۰ مگابایت)",
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id
            )
            return
        
        # تبدیل به base64
        image_base64 = encode_image_to_base64(image_bytes)
        
        # ویرایش پیام به "در حال تحلیل"
        bot.edit_message_text(
            "🤖 <b>در حال تحلیل با هوش مصنوعی...</b>\nمدل: Qwen 2.5 Vision ⚡",
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id
        )
        
        # تحلیل عکس با OpenRouter (به صورت همزمان)
        analysis = asyncio.run(analyze_with_openrouter(image_base64))
        
        # حذف پیام پردازش
        bot.delete_message(processing_msg.chat.id, processing_msg.message_id)
        
        # ارسال پاسخ نهایی
        response_text = f"""
<b>🐾 نتیجه تحلیل حیوان</b>

{analysis}

<b>🔬 فناوری:</b> OpenRouter + Qwen 2.5 Vision
<b>👤 کاربر:</b> {user_name}
<b>🕒 زمان:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<i>⚠️ توجه: این اطلاعات بر اساس هوش مصنوعی تولید شده و نیاز به تأیید دارد.</i>
        """
        
        # اگر پاسخ خیلی طولانی است، به چند قسمت تقسیم کن
        if len(response_text) > 4000:
            chunks = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
            for chunk in chunks:
                bot.send_message(
                    message.chat.id,
                    chunk,
                    reply_to_message_id=message.message_id
                )
        else:
            bot.send_message(
                message.chat.id,
                response_text,
                reply_to_message_id=message.message_id
            )
        
        logger.info(f"✅ پاسخ ارسال شد به کاربر {user_name}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ خطا در دانلود عکس: {e}")
        bot.reply_to(message, "❌ خطا در دریافت عکس. لطفاً دوباره تلاش کنید.")
    
    except Exception as e:
        logger.error(f"❌ خطای ناشناخته: {e}")
        bot.reply_to(message, "⚠️ خطای غیرمنتظره رخ داد. لطفاً بعداً تلاش کنید.")

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """هندلر سایر پیام‌ها"""
    
    if message.text:
        bot.reply_to(
            message,
            "📸 لطفاً یک عکس از حیوان بفرستید!\n\n"
            "برای راهنمایی /start را تایپ کنید."
        )
    elif message.document:
        bot.reply_to(
            message,
            "⚠️ لطفاً عکس بفرستید، نه فایل!\n"
            "فایل‌های داکیومنت قابل پردازش نیستند."
        )

# ==================== ERROR HANDLERS ====================
@bot.message_handler(func=lambda message: True, content_types=['audio', 'voice', 'video', 'sticker'])
def handle_unsupported(message):
    """هندلر انواع پیام پشتیبانی نشده"""
    bot.reply_to(
        message,
        "⚠️ این نوع پیام پشتیبانی نمی‌شود.\n"
        "لطفاً فقط عکس بفرستید."
    )

# ==================== MAIN EXECUTION ====================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🤖 راه‌اندازی ربات شناسایی حیوانات با OpenRouter")
    logger.info(f"👤 توکن: {TELEGRAM_TOKEN[:10]}...")
    logger.info(f"🔑 OpenRouter: {'✅' if OPENROUTER_API_KEY else '❌'}")
    logger.info("=" * 50)
    
    try:
        # نمایش اطلاعات شروع
        bot_info = bot.get_me()
        print(f"\n{'='*50}")
        print(f"🤖 بات فعال: @{bot_info.username}")
        print(f"📛 نام: {bot_info.first_name}")
        print(f"🆔 شناسه: {bot_info.id}")
        print(f"{'='*50}")
        print("✅ بات آماده دریافت پیام...")
        print("🧠 مدل: Qwen 2.5 Vision via OpenRouter")
        print("🛑 برای توقف: Ctrl+C")
        print(f"{'='*50}\n")
        
        # شروع polling
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
        
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"❌ خطای تلگرام API: {e}")
        print("❌ خطا در اتصال به تلگرام. بررسی کنید:")
        print("1. اینترنت متصل است؟")
        print("2. توکن درست است؟")
        print("3. فیلترینگ نیستید؟")
    
    except KeyboardInterrupt:
        logger.info("⏹️ توقف دستی بات")
        print("\n⏹️ بات متوقف شد")
    
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}")
        print(f"❌ خطا: {e}")
