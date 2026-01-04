#!/usr/bin/env python3
"""
🤖 ربات هوشمند شناسایی حیوانات - نسخه نهایی بدون ارور
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
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyChHdBakOesxzYzvG6_GD5kgAjy_8T1oyQ')

# تنظیم Gemini با کلید شما
genai.configure(api_key=GEMINI_API_KEY)

# Rate limiting
MAX_REQUESTS_PER_USER = 10
MAX_IMAGE_SIZE_MB = 5  # کاهش برای صرفه‌جویی
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
    """
    # اگر حجم عکس از حد مجاز کمتر است، برگردان
    if len(image_bytes) <= max_size_kb * 1024:
        return image_bytes
    
    # اگر حجم زیاد است، فقط قسمت اول را بفرست
    logger.warning(f"حجم عکس زیاد است: {len(image_bytes) / 1024 / 1024:.2f}MB - کاهش به 1MB")
    return image_bytes[:1024 * 1024]  # حداکثر 1MB

async def analyze_with_gemini(image_bytes: bytes) -> str:
    """تحلیل عکس با Gemini 2.0 Flash - بدون ارور"""
    try:
        # استفاده از مدل رایگان و مطمئن Gemini 2.0 Flash
        model_name = "gemini-2.0-flash-exp"
        
        logger.info(f"استفاده از مدل: {model_name}")
        
        # ساخت مدل
        model = genai.GenerativeModel(model_name)
        
        # ساخت prompt فارسی بهینه
        prompt = """شما یک متخصص حیوانات و حیات وحش هستید. لطفاً عکس زیر را تحلیل کنید و اطلاعات زیر را به زبان فارسی ساده و روان ارائه دهید:

🐾 **نام حیوان**: (اسم فارسی + اسم علمی لاتین)
🏠 **خانواده**: (رده‌بندی و خانواده)
🌍 **زیستگاه**: (مناطق طبیعی که زندگی می‌کند)
🍖 **رژیم غذایی**: (چه می‌خورد؟)
🔍 **ویژگی‌های بارز**: (مشخصات فیزیکی مهم)
🛡️ **وضعیت حفاظت**: (آیا در خطر انقراض است؟)
💡 **حقایق جالب**: (2-3 نکته جالب درباره این حیوان)
⏳ **طول عمر**: (متوسط طول عمر در طبیعت و اسارت)

اگر حیوان را به وضوح نمی‌بینید یا شناسایی دقیق ممکن نیست، صادقانه بگویید و حیوانات مشابه را پیشنهاد دهید.

لطفاً پاسخ را با ایموجی‌های مناسب زیبا کنید و ساختار منظم داشته باشد."""

        # تحلیل عکس
        response = model.generate_content([
            prompt,
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])
        
        if response.text:
            return response.text
        else:
            return "⚠️ متأسفانه مدل پاسخی نداد. لطفاً عکس واضح‌تری بفرستید."
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"خطا در Gemini API: {error_msg}")
        
        if "quota" in error_msg.lower():
            return "⏳ سهمیه API امروز تمام شده. لطفاً فردا تلاش کنید."
        elif "not found" in error_msg.lower():
            return "🔧 مشکل فنی: مدل در دسترس نیست. لطفاً بعداً تلاش کنید."
        else:
            return f"❌ خطا در تحلیل عکس: {error_msg[:80]}"

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    """هندلر دستور /start و /help"""
    
    welcome_text = """
<b>🤖 به ربات هوشمند شناسایی حیوانات خوش آمدید!</b>

<b>📸 نحوه استفاده:</b>
۱. یک عکس واضح از حیوان بفرستید
۲. ربات با هوش مصنوعی Gemini عکس را تحلیل می‌کند
۳. اطلاعات کامل حیوان را دریافت می‌کنید

<b>📋 اطلاعات دریافتی:</b>
• نام فارسی و علمی حیوان
• خانواده و رده‌بندی  
• زیستگاه طبیعی
• رژیم غذایی
• ویژگی‌های فیزیکی
• وضعیت حفاظت
• حقایق جالب
• طول عمر متوسط

<b>⚡ نکات مهم:</b>
• عکس باید واضح و روشن باشد
• حیوان در مرکز عکس باشد
• پاسخ ۱۰-۱۵ ثانیه طول می‌کشد
• حداکثر حجم عکس: ۵ مگابایت

<b>🔧 دستورات:</b>
/start - نمایش راهنما
/about - درباره ربات
/stats - آمار استفاده

<b>🐾 برای شروع، یک عکس بفرستید!</b>
    """
    
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['about'])
def handle_about(message):
    """درباره ربات"""
    about_text = """
<b>🤖 درباره ربات شناسایی حیوانات</b>

<b>🧠 فناوری پیشرفته:</b>
• موتور هوش مصنوعی: Google Gemini 2.0 Flash
• قابلیت: تحلیل تصاویر حیوانات
• زبان: فارسی کامل

<b>⚡ میزبانی:</b>
• پلتفرم: Railway.app
• سرور: ابری و همیشه آنلاین

<b>🎯 هدف پروژه:</b>
کمک به شناخت بهتر حیوانات و طبیعت برای همه

<b>📞 پشتیبانی:</b>
در صورت مشکل با بات، پیام دهید.
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

👤 <b>کاربر:</b> {user_name}
🆔 <b>شناسه:</b> {user_id}
📨 <b>درخواست‌های اخیر:</b> {request_count}
📈 <b>حداکثر مجاز:</b> {MAX_REQUESTS_PER_USER} درخواست/دقیقه

⚡ <b>وضعیت سرویس:</b> ✅ آنلاین
🤖 <b>مدل:</b> Gemini 2.0 Flash
🕒 <b>زمان:</b> {datetime.now().strftime('%H:%M')}
    """
    
    bot.reply_to(message, stats_text)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    """هندلر دریافت عکس"""
    
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    logger.info(f"📸 دریافت عکس از {user_name} ({user_id})")
    
    # بررسی rate limit
    if not check_rate_limit(user_id):
        bot.reply_to(message, "⏸️ تعداد درخواست‌های شما در دقیقه گذشته زیاد است. لطفاً ۶۰ ثانیه صبر کنید.")
        return
    
    try:
        # پیام پردازش
        processing_msg = bot.send_message(
            message.chat.id,
            "🔍 <b>در حال دریافت و پردازش عکس...</b>\nلطفاً کمی صبر کنید ⏳",
            reply_to_message_id=message.message_id
        )
        
        # دریافت عکس
        photo_info = message.photo[-1]
        file_info = bot.get_file(photo_info.file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"
        
        logger.info(f"📥 دانلود عکس: {file_info.file_path}")
        
        # دانلود عکس
        response = requests.get(file_url, timeout=15)
        response.raise_for_status()
        image_bytes = response.content
        
        # بررسی حجم
        if len(image_bytes) > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            bot.edit_message_text(
                "❌ <b>حجم عکس زیاد است!</b>\nحداکثر حجم مجاز: ۵ مگابایت",
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id
            )
            return
        
        # به‌روزرسانی پیام
        bot.edit_message_text(
            "🤖 <b>در حال تحلیل با هوش مصنوعی...</b>\nمدل: Gemini 2.0 Flash ⚡",
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id
        )
        
        # فشرده‌سازی ساده
        compressed_image = compress_image_simple(image_bytes)
        
        # تحلیل عکس
        analysis = asyncio.run(analyze_with_gemini(compressed_image))
        
        # حذف پیام پردازش
        bot.delete_message(processing_msg.chat.id, processing_msg.message_id)
        
        # ساخت پاسخ نهایی
        response_text = f"""
<b>🐾 نتایج تحلیل هوش مصنوعی</b>

{analysis}

━━━━━━━━━━━━━━━━━━━━
📌 <b>اطلاعات تحلیل:</b>
👤 کاربر: {user_name}
🕒 زمان: {datetime.now().strftime('%Y/%m/%d %H:%M')}
🤖 مدل: Google Gemini 2.0 Flash
⚡ سرور: Railway.app

💡 <i>اطلاعات بر اساس هوش مصنوعی تولید شده و ممکن است نیاز به تأیید داشته باشد.</i>
        """
        
        # ارسال پاسخ
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
        
        logger.info(f"✅ پاسخ ارسال شد به {user_name}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"خطای دانلود: {e}")
        bot.reply_to(message, "❌ خطا در دریافت عکس از تلگرام. لطفاً دوباره تلاش کنید.")
    
    except Exception as e:
        logger.error(f"خطای کلی: {e}")
        bot.reply_to(message, f"⚠️ خطای غیرمنتظره:\n{str(e)[:100]}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """هندلر سایر پیام‌های متنی"""
    bot.reply_to(
        message,
        "📸 <b>لطفاً یک عکس از حیوان بفرستید!</b>\n\n"
        "برای راهنمایی /start را تایپ کنید."
    )

@bot.message_handler(func=lambda message: True, content_types=['audio', 'voice', 'video', 'sticker', 'document'])
def handle_unsupported(message):
    """هندلر انواع پیام پشتیبانی نشده"""
    bot.reply_to(
        message,
        "⚠️ <b>این نوع پیام پشتیبانی نمی‌شود.</b>\n"
        "لطفاً فقط عکس از حیوان بفرستید."
    )

# ==================== MAIN EXECUTION ====================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 راه‌اندازی ربات شناسایی حیوانات - نسخه نهایی")
    logger.info(f"🔑 Gemini Key: {'✅' if GEMINI_API_KEY else '❌'}")
    logger.info("=" * 50)
    
    try:
        # تست اتصال Gemini
        try:
            models = genai.list_models()
            vision_models = [m.name for m in models if 'flash' in m.name.lower()]
            logger.info(f"مدل‌های Vision موجود: {vision_models[:3]}")
        except Exception as e:
            logger.warning(f"تست Gemini: {e}")
        
        # اطلاعات بات
        bot_info = bot.get_me()
        print("\n" + "="*50)
        print(f"🤖 بات: @{bot_info.username}")
        print(f"📛 نام: {bot_info.first_name}")
        print(f"🆔 شناسه: {bot_info.id}")
        print("="*50)
        print("✅ بات فعال و آماده دریافت پیام...")
        print("⚡ مدل: Gemini 2.0 Flash")
        print("🌐 میزبانی: Railway.app")
        print("🛑 برای توقف: Ctrl+C")
        print("="*50 + "\n")
        
        # شروع بات
        bot.infinity_polling(timeout=60, long_polling_timeout=30, logger_level=logging.WARNING)
        
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"خطای تلگرام: {e}")
        print(f"❌ خطای تلگرام: {e}")
        print("بررسی کن: 1. توکن درست باشد 2. اینترنت وصل باشد")
        
    except KeyboardInterrupt:
        logger.info("توقف دستی توسط کاربر")
        print("\n🛑 بات متوقف شد")
        
    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {e}")
        print(f"❌ خطای غیرمنتظره: {e}")
