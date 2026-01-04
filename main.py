#!/usr/bin/env python3
"""
🤖 ربات شناسایی حیوانات با Google Gemini
"""

import os
import logging
import asyncio
import google.generativeai as genai
from datetime import datetime

import telebot
from telebot import apihelper
from PIL import Image
import requests
from io import BytesIO

# ==================== CONFIGURATION ====================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8365956718:AAEcJGYB8kI875BRaFRmW0x1WTmm_G3qTGE')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyC06j93jtQ8TajCa173Z-V9fO8rIoRj1XU')  # 🔥 کلید خودت را اینجا بذار

# تنظیم Gemini
genai.configure(api_key=GEMINI_API_KEY)

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode='HTML')
user_requests = {}

# ==================== HELPER FUNCTIONS ====================
def compress_image(image_bytes, max_size_kb=500):
    """فشرده‌سازی عکس"""
    try:
        img = Image.open(BytesIO(image_bytes))
        
        # اگر حجم کم است برگردان
        if len(image_bytes) <= max_size_kb * 1024:
            return image_bytes
        
        # فشرده‌سازی
        output = BytesIO()
        img.convert('RGB').save(output, format='JPEG', quality=85, optimize=True)
        
        return output.getvalue()
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return image_bytes

async def analyze_with_gemini(image_bytes):
    """تحلیل عکس با Gemini"""
    try:
        # ابتدا مدل‌های در دسترس را چک کن
        available_models = []
        for m in genai.list_models():
            if 'vision' in m.name.lower() or 'gemini' in m.name.lower():
                available_models.append(m.name)
        
        logger.info(f"Available models: {available_models}")
        
        # انتخاب مدل (اولویت‌بندی)
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
            model_name = 'gemini-pro'  # مدل پیش‌فرض
        
        logger.info(f"Using model: {model_name}")
        
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
        
        return response.text if response.text else "⚠️ مدل پاسخی نداد. لطفاً عکس واضح‌تری بفرستید."
    
    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        return f"❌ خطا در تحلیل: {str(e)}"

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start', 'help'])
def handle_start(message):
    welcome_text = """
👋 **به ربات هوشمند شناسایی حیوانات خوش آمدید!**

🐾 **نحوه استفاده:**
۱. یک عکس واضح از حیوان بفرستید
۲. ربات با هوش مصنوعی Google Gemini عکس را تحلیل می‌کند
۳. اطلاعات کامل حیوان را دریافت می‌کنید

📋 **اطلاعات دریافتی:**
• نام فارسی و علمی
• خانواده و رده‌بندی  
• زیستگاه طبیعی
• رژیم غذایی
• ویژگی‌های فیزیکی
• وضعیت حفاظت
• حقایق جالب
• طول عمر متوسط

⚡ **تکنولوژی:** Google Gemini Pro Vision
🌐 **میزبانی:** Railway.app

📌 **دستورات:**
/start - نمایش این راهنما
/about - درباره ربات
/stats - آمار استفاده

🚀 **یک عکس بفرستید و شروع کنید!**
    """
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['about'])
def handle_about(message):
    about_text = """
🤖 **درباره ربات شناسایی حیوانات**

🧠 **فناوری به کار رفته:**
• موتور هوش مصنوعی: Google Gemini Pro Vision
• قابلیت: تحلیل پیشرفته تصاویر
• زبان: فارسی و انگلیسی

🎯 **هدف پروژه:**
کمک به شناخت بهتر حیوانات و محیط زیست

⚙️ **مشخصات فنی:**
• زبان برنامه‌نویسی: Python 3.10
• کتابخانه اصلی: pyTelegramBotAPI
• میزبانی: Railway.app
• دیتابیس: Gemini AI

📊 **محدودیت‌ها:**
• حداکثر حجم عکس: ۱۰ مگابایت
• تعداد درخواست: ۱۵ در دقیقه (رایگان)
• زمان تحلیل: ۱۰-۲۰ ثانیه

👨‍💻 **توسعه‌دهنده:**
ربات با ❤️ توسط جامعه توسعه‌دهندگان ایرانی

🔗 **پشتیبانی:**
برای گزارش مشکل پیام دهید.
    """
    bot.reply_to(message, about_text)

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    user_name = message.from_user.username or message.from_user.first_name
    stats_text = f"""
📊 **آمار استفاده**

👤 کاربر: {user_name}
🆔 شناسه: {message.from_user.id}
📅 تاریخ: {datetime.now().strftime('%Y/%m/%d')}
⏰ زمان: {datetime.now().strftime('%H:%M')}

⚡ **وضعیت سرویس:**
• Gemini API: ✅ فعال
• تلگرام: ✅ متصل
• سرور: ✅ آنلاین

💡 **نکته:** از بات به درستی استفاده کنید.
    """
    bot.reply_to(message, stats_text)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        user_id = message.from_user.id
        user_name = message.from_user.username or message.from_user.first_name
        
        logger.info(f"📸 دریافت عکس از {user_name} ({user_id})")
        
        # پیام پردازش
        processing_msg = bot.send_message(
            message.chat.id,
            "🔍 **در حال دریافت و پردازش عکس...**\nلطفاً کمی صبر کنید ⏳",
            reply_to_message_id=message.message_id
        )
        
        # دریافت عکس
        photo_info = message.photo[-1]
        file_info = bot.get_file(photo_info.file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_info.file_path}"
        
        logger.info(f"📥 دانلود از: {file_info.file_path}")
        
        # دانلود
        response = requests.get(file_url, timeout=15)
        response.raise_for_status()
        image_bytes = response.content
        
        # بررسی حجم
        if len(image_bytes) > 10 * 1024 * 1024:  # 10MB
            bot.edit_message_text(
                "❌ **حجم عکس زیاد است!**\nحداکثر حجم: ۱۰ مگابایت",
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id
            )
            return
        
        # فشرده‌سازی
        compressed = compress_image(image_bytes)
        
        # به روزرسانی پیام
        bot.edit_message_text(
            "🤖 **در حال تحلیل با هوش مصنوعی Gemini...**\nاین ممکنه ۱۰-۲۰ ثانیه طول بکشد ☕",
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id
        )
        
        # تحلیل با Gemini
        analysis = asyncio.run(analyze_with_gemini(compressed))
        
        # حذف پیام پردازش
        bot.delete_message(processing_msg.chat.id, processing_msg.message_id)
        
        # ساخت پاسخ نهایی
        response_text = f"""
🐾 **نتایج تحلیل هوش مصنوعی**

{analysis}

━━━━━━━━━━━━━━━━━━━━
📌 **اطلاعات تحلیل:**
👤 کاربر: {user_name}
📅 تاریخ: {datetime.now().strftime('%Y/%m/%d %H:%M')}
🤖 مدل: Google Gemini Pro Vision
⚡ سرور: Railway.app

💡 *اطلاعات بر اساس هوش مصنوعی تولید شده و ممکن است نیاز به تأیید داشته باشد.*
        """
        
        # ارسال پاسخ
        bot.send_message(
            message.chat.id,
            response_text,
            reply_to_message_id=message.message_id,
            parse_mode='Markdown'
        )
        
        logger.info(f"✅ پاسخ ارسال شد به {user_name}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"دانلود خطا: {e}")
        bot.reply_to(message, "❌ **خطا در دریافت عکس.**\nلطفاً دوباره تلاش کنید.")
    
    except Exception as e:
        logger.error(f"خطای کلی: {e}")
        bot.reply_to(message, f"⚠️ **خطای غیرمنتظره:**\n{str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    bot.reply_to(message, 
        "📸 **لطفاً یک عکس از حیوان بفرستید!**\n\n"
        "برای راهنمایی /start را تایپ کنید."
    )

# ==================== RUN BOT ====================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 راه‌اندازی ربات شناسایی حیوانات")
    logger.info(f"🔑 Gemini Key: {'✅' if GEMINI_API_KEY else '❌'}")
    logger.info("=" * 50)
    
    try:
        bot_info = bot.get_me()
        print("\n" + "="*50)
        print(f"🤖 بات: @{bot_info.username}")
        print(f"📛 نام: {bot_info.first_name}")
        print(f"🆔 شناسه: {bot_info.id}")
        print("="*50)
        print("✅ بات فعال و آماده دریافت پیام...")
        print("🛑 برای توقف: Ctrl+C")
        print("="*50 + "\n")
        
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
        
    except telebot.apihelper.ApiTelegramException as e:
        logger.error(f"خطای تلگرام: {e}")
        print(f"❌ خطای تلگرام: {e}")
        
    except KeyboardInterrupt:
        logger.info("توقف دستی")
        print("\n🛑 بات متوقف شد")
        
    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {e}")
        print(f"❌ خطا: {e}")