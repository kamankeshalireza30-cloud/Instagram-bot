import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp
import tempfile
import json

# توکن از متغیر محیطی
BOT_TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ذخیره موقت اطلاعات کاربر
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی اصلی با دکمه‌های زیبا"""
    keyboard = [
        [
            InlineKeyboardButton("🎬 دانلود ویدیو", callback_data="download_video"),
            InlineKeyboardButton("🎵 استخراج صدا", callback_data="extract_audio")
        ],
        [
            InlineKeyboardButton("📝 کپی کپشن", callback_data="copy_caption"),
            InlineKeyboardButton("🏷️ هشتگ‌ها", callback_data="get_hashtags")
        ],
        [
            InlineKeyboardButton("ℹ️ راهنما", callback_data="help"),
            InlineKeyboardButton("⭐ امتیاز", url="https://t.me/YourChannel")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✨ **ربات دانلودر حرفه‌ای اینستاگرام** ✨\n\n"
        "🎯 **ویژگی‌های ویژه:**\n"
        "• 🎬 دانلود ویدیو با کیفیت اصلی\n"
        "• 🎵 استخراج صدا به صورت MP3\n"
        "• 📝 کپی خودکار کپشن + هشتگ‌ها\n"
        "• 📊 اطلاعات کامل پست\n"
        "• ⚡ سرعت بالا\n\n"
        "📎 **لینک اینستاگرام را بفرستید...**",
        reply_markup=reply_markup,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت لینک از کاربر"""
    user_id = update.effective_user.id
    url = update.message.text.strip()
    
    # بررسی لینک
    if not url or "instagram.com" not in url:
        await update.message.reply_text(
            "❌ **لینک معتبر نیست!**\n\n"
            "✅ مثال لینک صحیح:\n"
            "• https://www.instagram.com/p/Cxxxxxxx/\n"
            "• https://www.instagram.com/reel/Cxxxxxxx/\n"
            "• https://www.instagram.com/tv/Cxxxxxxx/"
        )
        return
    
    # ذخیره لینک کاربر
    user_sessions[user_id] = {'url': url}
    
    # تحلیل لینک
    msg = await update.message.reply_text(
        "🔍 **در حال تحلیل لینک...**\n"
        "⏳ لطفاً کمی صبر کنید..."
    )
    
    try:
        # دریافت اطلاعات اولیه
        ydl_opts = {'quiet': True, 'extract_flat': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            await msg.edit_text("❌ **لینک نامعتبر یا دسترسی محدود است!**")
            return
        
        # ذخیره اطلاعات
        user_sessions[user_id]['info'] = info
        
        # ایجاد دکمه‌های اقدام
        keyboard = []
        
        # بررسی نوع محتوا
        if info.get('duration'):
            keyboard.append([
                InlineKeyboardButton("🎬 دانلود ویدیو", callback_data="action_download_video"),
                InlineKeyboardButton("🎵 استخراج صدا", callback_data="action_extract_audio")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("🖼️ دانلود عکس", callback_data="action_download_photo")
            ])
        
        keyboard.append([
            InlineKeyboardButton("📝 کپی کپشن", callback_data="action_copy_caption"),
            InlineKeyboardButton("📊 اطلاعات پست", callback_data="action_post_info")
        ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 لینک دیگر", callback_data="action_new_link")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # نمایش اطلاعات اولیه
        title = info.get('title', 'بدون عنوان')[:100]
        duration = info.get('duration', 0)
        uploader = info.get('uploader', 'ناشناس')
        
        info_text = f"""
📊 **تحلیل لینک موفق!**

📛 **عنوان:** {title}
👤 **کاربر:** @{uploader}
⏱️ **مدت زمان:** {duration} ثانیه
🔗 **نوع:** {'ویدیو' if duration > 0 else 'عکس'}

🎯 **لطفاً عمل مورد نظر را انتخاب کنید:**
        """
        
        await msg.edit_text(info_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"خطا در تحلیل لینک: {e}")
        await msg.edit_text(
            "❌ **خطا در تحلیل لینک!**\n\n"
            "⚠️ دلایل احتمالی:\n"
            "• پست خصوصی است\n"
            "• اکانت خصوصی است\n"
            "• لینک نامعتبر\n"
            "• محدودیت دسترسی\n\n"
            "🔧 لینک دیگری امتحان کنید..."
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی دکمه‌ها"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    action = query.data
    
    if user_id not in user_sessions:
        await query.edit_message_text("❌ **سشن منقضی شده!**\nلطفاً دوباره لینک بفرستید.")
        return
    
    url = user_sessions[user_id]['url']
    info = user_sessions[user_id].get('info', {})
    
    # پردازش هر عمل
    if action == "action_download_video":
        await download_media(query, url, 'video')
    
    elif action == "action_extract_audio":
        await extract_audio(query, url)
    
    elif action == "action_download_photo":
        await download_media(query, url, 'photo')
    
    elif action == "action_copy_caption":
        await copy_caption(query, info)
    
    elif action == "action_post_info":
        await show_post_info(query, info)
    
    elif action == "action_new_link":
        await query.edit_message_text("📎 **لینک جدید اینستاگرام را بفرستید...**")
    
    elif action == "help":
        await show_help(query)
    
    elif action == "download_video":
        await query.edit_message_text("📎 **لینک اینستاگرام را بفرستید...**")

async def download_media(query, url, media_type):
    """دانلود مدیا"""
    msg = await query.edit_message_text(
        f"⏳ **در حال دانلود {media_type}...**\n"
        "📥 لطفاً صبر کنید..."
    )
    
    try:
        temp_dir = tempfile.mkdtemp()
        ydl_opts = {
            'quiet': True,
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'format': 'best[filesize<50M]' if media_type == 'video' else 'best',
            'socket_timeout': 30,
            'retries': 3,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
            # پیدا کردن فایل دانلود شده
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.webm', '.mkv', '.jpg', '.png', '.jpeg')):
                    file_path = os.path.join(temp_dir, file)
                    
                    with open(file_path, 'rb') as f:
                        if file.endswith(('.mp4', '.webm', '.mkv')):
                            await query.message.reply_video(
                                video=f,
                                caption="🎬 **دانلود شده توسط ربات**",
                                supports_streaming=True,
                                read_timeout=60,
                                write_timeout=60
                            )
                        else:
                            await query.message.reply_photo(
                                photo=f,
                                caption="🖼️ **دانلود شده توسط ربات**"
                            )
                    
                    os.remove(file_path)
                    break
        
        await msg.edit_text("✅ **دانلود با موفقیت انجام شد!**\n✨ لینک دیگری بفرستید...")
        
    except Exception as e:
        logger.error(f"خطا در دانلود: {e}")
        await msg.edit_text(
            "❌ **خطا در دانلود!**\n\n"
            f"⚠️ دلیل: {str(e)[:150]}\n\n"
            "🔧 لینک دیگری امتحان کنید..."
        )
    
    finally:
        # پاکسازی
        import shutil
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

async def extract_audio(query, url):
    """استخراج صدا از ویدیو"""
    msg = await query.edit_message_text(
        "🎵 **در حال استخراج صدا...**\n"
        "⚙️ این عملیات ممکن است کمی طول بکشد..."
    )
    
    try:
        # اول ویدیو را دانلود کن
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, 'video.mp4')
        
        ydl_opts = {
            'quiet': True,
            'outtmpl': video_path.replace('.mp4', '.%(ext)s'),
            'format': 'best[filesize<50M]',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.download([url])
        
        # تبدیل به MP3
        from moviepy.editor import VideoFileClip
        
        video = VideoFileClip(video_path)
        audio_path = video_path.replace('.mp4', '.mp3')
        video.audio.write_audiofile(audio_path)
        video.close()
        
        # ارسال فایل صوتی
        with open(audio_path, 'rb') as f:
            await query.message.reply_audio(
                audio=f,
                title="استخراج شده از اینستاگرام",
                performer="@Instagram",
                caption="🎵 **صدا استخراج شد**"
            )
        
        await msg.edit_text("✅ **صدا با موفقیت استخراج شد!**")
        
    except Exception as e:
        logger.error(f"خطا در استخراج صدا: {e}")
        await msg.edit_text(
            "❌ **خطا در استخراج صدا!**\n\n"
            "⚠️ این ویژگی فقط برای ویدیوها کار می‌کند.\n"
            "🔧 لینک ویدیویی دیگری امتحان کنید..."
        )
    
    finally:
        # پاکسازی
        import shutil
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

async def copy_caption(query, info):
    """نمایش و کپی کپشن"""
    caption = info.get('description') or info.get('title') or 'کپشنی وجود ندارد'
    
    # استخراج هشتگ‌ها
    import re
    hashtags = re.findall(r'#(\w+)', caption)
    hashtags_text = ' '.join([f'#{tag}' for tag in hashtags[:10]]) if hashtags else 'هشتگی ندارد'
    
    # متن برای کپی
    copy_text = f"""
{caption}

{hashtags_text}

📎 دانلود شده توسط @{query.message.chat.username}
    """
    
    await query.edit_message_text(
        f"📝 **کپشن پست:**\n\n"
        f"`{copy_text}`\n\n"
        "✅ **متن بالا را انتخاب و کپی کنید.**\n"
        "📋 برای کپی: متن را انتخاب → Copy\n\n"
        f"🏷️ **هشتگ‌ها ({len(hashtags)}):**\n{hashtags_text}",
        parse_mode='Markdown'
    )

async def show_post_info(query, info):
    """نمایش اطلاعات کامل پست"""
    title = info.get('title', 'بدون عنوان')
    uploader = info.get('uploader', 'ناشناس')
    duration = info.get('duration', 0)
    view_count = info.get('view_count', 0)
    like_count = info.get('like_count', 0)
    comment_count = info.get('comment_count', 0)
    
    info_text = f"""
📊 **اطلاعات کامل پست:**

📛 **عنوان:** {title[:200]}
👤 **کاربر:** @{uploader}
⏱️ **مدت زمان:** {duration} ثانیه
👁️ **بازدید:** {view_count:,}
❤️ **لایک:** {like_count:,}
💬 **کامنت:** {comment_count:,}
🔗 **آدرس:** {info.get('webpage_url', 'N/A')[:50]}...

📈 **وضعیت:** {'فعال' if info.get('availability') else 'نامشخص'}
🎬 **نوع:** {'ویدیو' if duration > 0 else 'عکس'}
        """
    
    await query.edit_message_text(info_text, parse_mode='Markdown')

async def show_help(query):
    """نمایش راهنما"""
    help_text = """
🎯 **راهنمای استفاده از ربات:**

📌 **مراحل کار:**
1. لینک اینستاگرام را بفرستید
2. عمل مورد نظر را انتخاب کنید
3. نتیجه را دریافت کنید

✨ **ویژگی‌ها:**
• 🎬 دانلود ویدیو با کیفیت اصلی
• 🎵 استخراج صدا به صورت MP3
• 📝 کپی خودکار کپشن و هشتگ‌ها
• 📊 اطلاعات کامل پست
• ⚡ سرعت بالا و بدون محدودیت

⚠️ **محدودیت‌ها:**
• فقط پست‌های عمومی
• حداکثر حجم: 50 مگابایت
• بدون نیاز به لاگین

🔗 **پشتیبانی:** @YourUsername
📢 **کانال:** @YourChannel
⭐ **امتیاز دهید:** /rate

💡 **نکته:** برای بهترین نتیجه از لینک‌های عمومی استفاده کنید.
        """
    
    await query.edit_message_text(help_text, parse_mode='Markdown')

def main():
    """تابع اصلی اجرای ربات"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN تنظیم نشده!")
        logger.error("لطفاً در Render Environment Variables قرار دهید.")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن هندلرها
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("=" * 50)
    logger.info("🤖 ربات حرفه‌ای اینستاگرام")
    logger.info("🚀 فعال شد و منتظر درخواست...")
    logger.info("=" * 50)
    
    app.run_polling(
        poll_interval=1.0,
        timeout=30,
        drop_pending_updates=True,
        allowed_updates=['message', 'callback_query']
    )

if __name__ == "__main__":
    main()
    
