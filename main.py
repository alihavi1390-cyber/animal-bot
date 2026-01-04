#!/usr/bin/env python3
"""
🤖 ربات هوشمند شناسایی حیوانات - نسخه بدون Pillow
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
import google.generativeai as genai

# ==================== CONFIGURATION ====================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8365956718:AAEcJGYB8kI875BRaFRmW0x1WTmm_G3qTGE')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyC06j93jtQ8TajCa173Z-V9fO8rIoRj1XU')

# تنظیم Gemini
genai.configure(api_key=GEMINI_API_KEY)

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

def compress_image_simple(image_bytes: bytes, max_size_kb: int = 1024) -> bytes:
    """
    فشرده‌سازی ساده عکس بدون Pillow
    فقط بررسی حجم و برگرداندن همان عکس اگر حجمش کم است
    """
    # اگر حجم عکس از حد مجاز کمتر است، برگردان
    if len(image_bytes) <= max_size_kb * 1024:
        return image_bytes
    
    # اگر حجم زیاد است، تلاش می‌کنیم با کاهش کیفیت فشرده کنیم
    # این یک روش ساده است - در نسخه واقعی بهتر است از سرویس ابری استفاده شود
    try:
        # تلاش برای ارسال عکس اصلی (Gemini می‌تواند عکس‌های تا ۴MB را پردازش کند)
        if len(image_bytes) <= 4 * 1024 * 1024:  # 4MB
            return image_bytes
        
        # اگر خیلی بزرگ است، به کاربر اطلاع می‌دهیم
        logger.warning(f"حجم عکس زیاد است: {len(image_bytes) / 1024 / 1024:.2f}MB")
        return image_bytes[:4 * 1024 * 1024]  # فقط ۴MB اول را می‌فرستیم
        
    except Exception as e:
        logger.error(f"خطا در فشرده‌سازی ساده: {e}")
        return image_bytes

def encode_image_to_base64(image_bytes: bytes) -> str:
    """تبدیل عکس به base64"""
    encoded = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded}"

async def analyze_with_gemini(image_bytes: bytes) -> str:
    """تحلیل عکس با Gemini Pro Vision"""
    try:
        # بررسی مدل‌های در دسترس
        available_models = []
        for m in genai.list_models():
            if 'vision' in m.name.lower() or 'gemini' in m.name.lower():
                available_models.append(m.name)
        
        logger.info(f"مدل‌های در دسترس: {available_models}")
        
        # انتخاب مدل
        model_name = None
        preferred_models = [
            'gemini-1.5-pro-vision',
            'gemini-1.5-pro',
            'gemini-1.0-pro-vision',
            'gemini-pro-vision'
        ]
        
        for preferred in preferred_models:
            if any(preferred in model for model in available_models):
                model_name = preferred
                break
        
        if not model_name:
            model_name = 'gemini-pro'
        
        logger.info(f"استفاده از مدل: {model_name}")
        
        # ساخت مدل
        model = genai.GenerativeModel(model_name)
        
        # ساخت prompt فارسی
        prompt = """تو یک متخصص حیات وحش هستی. لطفا عکس زیر را تحلیل کن و اطلاعات زیر را به زبان **فارسی ساده و روان** ارائه بده:

۱. **نام حیوان**: اسم فارسی و اسم علمی (لاتین)
۲. **خانواده**: خانواده و رده‌بندی
۳. **زیستگاه**: مناطق طبیعی که زندگی می‌کند
۴. **غذا**: رژیم غذایی اصلی
۵. **ویژگی‌ها**: مشخصات فیزیکی مهم
۶. **وضعیت حفاظت**: آیا در خطر انقراض است؟
۷. **حقایق جالب**: ۲-۳ نکته جالب
۸. **طول عمر**: متوسط طول عمر

اگر عکس واضح نیست یا حیوان را نمی‌شناسی، صادقانه بگو و حدس بزن ممکنه چه حیوانی باشد.

لطفا پاسخ را با emoji های مناسب زیباتر کن."""

        # تحلیل عکس
        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])
        
        if response.text:
            return response.text
        else:
            return "⚠️ مدل پاسخی نداد. لطفاً عکس واضح‌تری بفرستید."
    
    except Exception as e:
        logger.error(f"خطا در Gemini API: {str(e)}")
        return f"❌ خطا در تحلیل عکس: {str(e)[:100]}"

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    """هندلر دستور /start و /help"""
    
    welcome_text = """
<b>🐾 به ربات شناسایی حیوانات خوش آمدید!</b>

<b>📌 نحوه استفاده:</b>
۱. یک عکس واضح از حیوان بفرستید
۲. ربات عکس را تحلیل می‌کند
۳. اطلاعات کامل حیوان را دریافت می‌کنید

<b>📋 اطلاعات دریافتی:</b>
• نام فارسی و علمی
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
• مدل هوش مصنوعی: Google Gemini Pro Vision
• قابلیت: تحلیل تصاویر پیشرفته
• زبان: فارسی و انگلیسی

<b>⚡ میزبانی:</b>
Railway.app - سرویس ابری قدرتمند

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
        response = requests.get(file_url, timeout=15)
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
        
        # فشرده‌سازی ساده
        compressed_image = compress_image_simple(image_bytes)
        
        # ویرایش پیام به "در حال تحلیل"
        bot.edit_message_text(
            "🤖 <b>در حال تحلیل با هوش مصنوعی Gemini...</b>\nاین ممکنه ۱۰-۲۰ ثانیه طول بکشد ☕",
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id
        )
        
        # تحلیل عکس با Gemini (به صورت همزمان)
        analysis = asyncio.run(analyze_with_gemini(compressed_image))
        
        # حذف پیام پردازش
        bot.delete_message(processing_msg.chat.id, processing_msg.message_id)
        
        # ارسال پاسخ نهایی
        response_text = f"""
<b>🐾 نتیجه تحلیل حیوان</b>

{analysis}

<b>🔬 فناوری:</b> Google Gemini Pro Vision
<b>👤 کاربر:</b> {user_name}
<b>🕒 زمان:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<i>⚠️ توجه: اطلاعات بر اساس هوش مصنوعی تولید شده و نیاز به تأیید دارد.</i>
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
        bot.reply_to(message, f"⚠️ خطای غیرمنتظره رخ داد: {str(e)[:100]}")

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
    logger.info("🤖 راه‌اندازی ربات شناسایی حیوانات (نسخه بدون Pillow)")
    logger.info(f"👤 توکن: {TELEGRAM_TOKEN[:10]}..." if TELEGRAM_TOKEN else "❌ توکن تنظیم نشده")
    logger.info(f"🔑 Gemini: {'✅' if GEMINI_API_KEY else '❌ کلید تنظیم نشده'}")
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
        print("🛑 برای توقف: Ctrl+C")
        print(f"{'='*50}\n")
        
        # شروع polling
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
        
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"❌ خطای تلگرام API: {e}")
        print("❌ خطا در اتصال به تلگرام. بررسی کنید:")
        print("1. توکن درست است؟")
        print("2. اینترنت متصل است؟")
        print(f"3. خطا: {e}")
    
    except KeyboardInterrupt:
        logger.info("⏹️ توقف دستی بات")
        print("\n⏹️ بات متوقف شد")
    
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}")
        print(f"❌ خطا: {e}")
