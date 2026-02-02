import os
import logging
import tempfile
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
import moviepy.editor as mp
from urllib.parse import urlparse
import json

# تنظیمات
BOT_TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ذخیره اطلاعات کاربران
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور start با منوی زیبا"""
    keyboard = [
        [InlineKeyboardButton("🎵 استخراج صدا", callback_data="extract_audio")],
        [InlineKeyboardButton("📝 کپی کپشن", callback_data="copy_caption")],
        [InlineKeyboardButton("📥 دانلود همه", callback_data="download_all")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎬 **ربات دانلودر حرفه‌ای اینستاگرام**\n\n"
        "✨ **ویژگی‌ها:**\n"
        "• 🎵 استخراج صدا از ویدیو\n"
        "• 📝 کپی خودکار کپشن\n"
        "• 📥 دانلود تمام مدیاها\n"
        "• 🏷️ استخراج هشتگ‌ها\n"
        "• 👤 اطلاعات پروفایل\n\n"
        "📎 **لینک اینستاگرام را بفرستید...**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش لینک اینستاگرام"""
    url = update.message.text.strip()
    user_id = update.effective_user.id
    
    # بررسی لینک
    if "instagram.com" not in url:
        await update.message.reply_text("❌ لینک اینستاگرام معتبر نیست!")
        return
    
    # ذخیره لینک برای کاربر
    user_data[user_id] = {'url': url}
    
    # پردازش لینک
    msg = await update.message.reply_text("🔍 در حال تحلیل لینک...")
    
    try:
        # دریافت اطلاعات پست
        info = await get_instagram_info(url)
        
        if not info:
            await msg.edit_text("❌ امکان دریافت اطلاعات وجود ندارد!")
            return
        
        # ذخیره اطلاعات
        user_data[user_id]['info'] = info
        
        # ایجاد منوی انتخاب
        keyboard = await create_action_keyboard(info)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        caption = f"""
📊 **اطلاعات پست:**
👤 کاربر: @{info.get('uploader', 'Unknown')}
📝 عنوان: {info.get('title', 'بدون عنوان')[:50]}...
⏱️ مدت: {info.get('duration', 0)} ثانیه
📁 فرمت: {info.get('ext', 'N/A')}
🔢 تعداد مدیا: {len(info.get('formats', []))}
        """
        
        await msg.edit_text(caption, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"خطا: {e}")
        await msg.edit_text(f"❌ خطا: {str(e)[:100]}")

async def get_instagram_info(url):
    """دریافت اطلاعات پست اینستاگرام"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except:
        return None

async def create_action_keyboard(info):
    """ایجاد کیبورد اقدامات"""
    keyboard = []
    
    # بررسی نوع محتوا
    if info.get('duration', 0) > 0:  # ویدیو دارد
        keyboard.append([InlineKeyboardButton("🎬 دانلود ویدیو", callback_data="download_video")])
        keyboard.append([InlineKeyboardButton("🎵 استخراج صدا (MP3)", callback_data="extract_audio")])
    
    # اگر عکس است
    if info.get('ext') in ['jpg', 'png', 'jpeg']:
        keyboard.append([InlineKeyboardButton("🖼️ دانلود عکس", callback_data="download_photo")])
    
    # اگر کپشن دارد
    if info.get('description') or info.get('title'):
        keyboard.append([InlineKeyboardButton("📝 کپی کپشن", callback_data="copy_caption")])
    
    # استخراج هشتگ‌ها
    keyboard.append([InlineKeyboardButton("🏷️ استخراج هشتگ‌ها", callback_data="extract_tags")])
    
    keyboard.append([InlineKeyboardButton("📊 اطلاعات پروفایل", callback_data="profile_info")])
    
    return keyboard

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if user_id not in user_data:
        await query.edit_message_text("❌ لینک منقضی شده. لطفا دوباره لینک بفرستید.")
        return
    
    url = user_data[user_id]['url']
    info = user_data[user_id].get('info')
    
    # پیام در حال پردازش
    await query.edit_message_text("⏳ در حال پردازش...")
    
    try:
        if data == "download_video":
            await download_video(query, url)
        
        elif data == "extract_audio":
            await extract_audio(query, url)
        
        elif data == "download_photo":
            await download_photo(query, url)
        
        elif data == "copy_caption":
            await copy_caption(query, info)
        
        elif data == "extract_tags":
            await extract_tags(query, info)
        
        elif data == "profile_info":
            await profile_info(query, info)
        
        elif data == "download_all":
            await download_all(query, url)
        
        elif data == "help":
            await help_command(query)
    
    except Exception as e:
        logger.error(f"خطا در پردازش {data}: {e}")
        await query.edit_message_text(f"❌ خطا: {str(e)[:100]}")

async def download_video(query, url):
    """دانلود ویدیو"""
    msg = await query.edit_message_text("📥 در حال دانلود ویدیو...")
    
    temp_dir = tempfile.mkdtemp()
    ydl_opts = {
        'quiet': True,
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'format': 'best[filesize<50M]',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
            # پیدا کردن فایل دانلود شده
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv')):
                    file_path = os.path.join(temp_dir, file)
                    
                    with open(file_path, 'rb') as f:
                        await query.message.reply_video(
                            video=f,
                            caption="🎬 ویدیو دانلود شد",
                            supports_streaming=True
                        )
                    
                    os.remove(file_path)
                    break
        
        await msg.edit_text("✅ ویدیو ارسال شد!")
        
    finally:
        # پاکسازی
        try:
            os.rmdir(temp_dir)
        except:
            pass

async def extract_audio(query, url):
    """استخراج صدا از ویدیو"""
    msg = await query.edit_message_text("🎵 در حال استخراج صدا...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # اول ویدیو را دانلود کن
        ydl_opts = {
            'quiet': True,
            'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
            'format': 'best[filesize<50M]',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)
        
        # استخراج صدا
        if os.path.exists(video_path):
            audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
            
            # تبدیل به MP3
            video = mp.VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path)
            video.close()
            
            # ارسال فایل صوتی
            with open(audio_path, 'rb') as f:
                await query.message.reply_audio(
                    audio=f,
                    caption="🎵 صدای استخراج شده از ویدیو",
                    title=info.get('title', 'Audio')[:64],
                    performer="@Instagram"
                )
            
            await msg.edit_text("✅ صدا استخراج و ارسال شد!")
        
        else:
            await msg.edit_text("❌ ویدیو دانلود نشد!")
    
    except Exception as e:
        await msg.edit_text(f"❌ خطا در استخراج صدا: {str(e)[:100]}")
    
    finally:
        # پاکسازی
        for file in os.listdir(temp_dir):
            try:
                os.remove(os.path.join(temp_dir, file))
            except:
                pass
        try:
            os.rmdir(temp_dir)
        except:
            pass

async def copy_caption(query, info):
    """کپی کپشن"""
    caption = info.get('description') or info.get('title') or info.get('uploader', '')
    
    if not caption:
        await query.edit_message_text("❌ کپشنی برای کپی کردن وجود ندارد!")
        return
    
    # کوتاه کردن اگر طولانی است
    if len(caption) > 4000:
        caption = caption[:4000] + "..."
    
    # ایجاد دکمه کپی (تلگرام خودش کپی می‌کند اگر متن ساده باشد)
    await query.edit_message_text(
        f"📝 **کپشن پست:**\n\n"
        f"`{caption}`\n\n"
        "✅ متن بالا را انتخاب و کپی کنید.",
        parse_mode='Markdown'
    )

async def extract_tags(query, info):
    """استخراج هشتگ‌ها"""
    text = info.get('description') or info.get('title') or ''
    
    # پیدا کردن هشتگ‌ها
    import re
    hashtags = re.findall(r'#(\w+)', text)
    
    if not hashtags:
        await query.edit_message_text("❌ هشتگی در این پست پیدا نشد!")
        return
    
    hashtags_text = " ".join([f"#{tag}" for tag in hashtags[:20]])  # حداکثر 20 هشتگ
    
    await query.edit_message_text(
        f"🏷️ **هشتگ‌های پست:**\n\n"
        f"`{hashtags_text}`\n\n"
        f"📊 تعداد: {len(hashtags)}",
        parse_mode='Markdown'
    )

async def profile_info(query, info):
    """نمایش اطلاعات پروفایل"""
    profile_info = f"""
👤 **اطلاعات پروفایل:**

📛 نام: {info.get('uploader', 'Unknown')}
🔗 آیدی: @{info.get('uploader_id', 'N/A')}
📊 تعداد دنبال‌کنندگان: {info.get('channel_follower_count', 'N/A')}

📝 **آخرین پست:**
{info.get('title', 'بدون عنوان')[:200]}...
        """
    
    await query.edit_message_text(profile_info, parse_mode='Markdown')

async def download_all(query, url):
    """دانلود همه مدیاها"""
    await query.edit_message_text("📦 در حال آماده‌سازی تمام مدیاها...")
    
    # این قسمت می‌تواند برای پست‌های کاروسل توسعه یابد
    await query.message.reply_text(
        "✨ **این ویژگی به زودی اضافه می‌شود!**\n\n"
        "در حال حاضر می‌توانید:\n"
        "• 🎬 دانلود ویدیو\n"
        "• 🎵 استخراج صدا\n"
        "• 📝 کپی کپشن\n\n"
        "برای پست‌های کاروسل، هر عکس/ویدیو جداگانه دانلود می‌شود."
    )

async def help_command(query):
    """راهنمای استفاده"""
    help_text = """
🎯 **راهنمای استفاده:**

1. **لینک اینستاگرام را بفرستید**
   - پست، ریل، IGTV یا استوری عمومی

2. **انتخاب عمل مورد نظر:**
   - 🎬 دانلود ویدیو
   - 🎵 استخراج صدا (MP3)
   - 📝 کپی کپشن
   - 🏷️ استخراج هشتگ‌ها
   - 👤 اطلاعات پروفایل

3. **محدودیت‌ها:**
   - حداکثر حجم: 50MB
   - فقط پست‌های عمومی
   - بدون نیاز به لاگین

🔧 **پشتیبانی:** @YourUsername
        """
    
    await query.edit_message_text(help_text)

def main():
    """تابع اصلی"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN تنظیم نشده!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن هندلرها
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🤖 ربات حرفه‌ای اینستاگرام فعال شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
