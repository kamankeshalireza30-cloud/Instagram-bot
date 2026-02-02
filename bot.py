import os
import logging
import asyncio
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import instaloader
import shutil
import tempfile

# تنظیم asyncio برای ویندوز (اگر روی ویندوز اجرا میشه)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# خواندن توکن از متغیر محیطی
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# برای اجرای محلی (اگر متغیر محیطی وجود نداشت)
if not BOT_TOKEN:
    BOT_TOKEN = "توکن_خودت"  # توکن واقعی رو اینجا قرار بده

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام!\n"
        "لینک پست اینستاگرام را بفرستید.\n\n"
        "📌 مثال:\n"
        "• https://www.instagram.com/p/Cxxxxxxx/\n"
        "• https://www.instagram.com/reel/Cxxxxxxx/\n\n"
        "⚠️ فقط پست‌های عمومی"
    )

def extract_shortcode(url):
    url = url.split('?')[0].rstrip('/')
    parts = url.split('/')
    for part in reversed(parts):
        if part and 'instagram.com' not in part:
            return part
    return None

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if "instagram.com" not in url:
        await update.message.reply_text("❌ لینک اینستاگرام بفرستید.")
        return
    
    msg = await update.message.reply_text("⏳ در حال دانلود...")
    
    try:
        shortcode = extract_shortcode(url)
        if not shortcode:
            await msg.edit_text("❌ کد پست نامعتبر!")
            return
        
        logger.info(f"دانلود پست: {shortcode}")
        
        # دانلود از اینستاگرام
        L = instaloader.Instaloader(
            quiet=True,
            download_pictures=True,
            download_videos=True,
            download_video_thumbnails=False,
            compress_json=False,
            save_metadata=False
        )
        
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # ساخت پوشه موقت (متناسب با هر سیستم)
        download_dir = tempfile.mkdtemp(prefix=f"insta_{shortcode}_")
        logger.info(f"پوشه موقت: {download_dir}")
        
        # دانلود
        L.download_post(post, target=download_dir)
        
        # ارسال فایل‌ها
        sent_count = 0
        files_to_cleanup = []
        
        for file in os.listdir(download_dir):
            file_path = os.path.join(download_dir, file)
            
            # فقط فایل‌های مدیا
            if not file.endswith(('.mp4', '.jpg', '.png', '.jpeg')):
                continue
            
            # بررسی حجم (حداکثر 50MB برای تلگرام)
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            if file_size > 50:
                logger.warning(f"فایل حذف شد (حجم زیاد): {file_size:.1f}MB")
                continue
            
            try:
                if file.endswith('.mp4'):
                    with open(file_path, 'rb') as f:
                        await update.message.reply_video(
                            video=f,
                            caption=f"@{post.owner_username}" if sent_count == 0 else None,
                            supports_streaming=True,
                            read_timeout=90,  # افزایش timeout
                            write_timeout=90
                        )
                elif file.endswith(('.jpg', '.png', '.jpeg')):
                    with open(file_path, 'rb') as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption=f"@{post.owner_username}" if sent_count == 0 else None
                        )
                
                sent_count += 1
                logger.info(f"✅ فایل ارسال شد: {file} ({file_size:.1f}MB)")
                
            except Exception as e:
                logger.error(f"❌ خطا در ارسال {file}: {e}")
            finally:
                # علامت برای پاکسازی
                files_to_cleanup.append(file_path)
        
        # پاکسازی فایل‌ها
        for file_path in files_to_cleanup:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"خطا در پاکسازی {file_path}: {e}")
        
        # پاکسازی پوشه اگر خالی است
        try:
            if os.path.exists(download_dir) and not os.listdir(download_dir):
                os.rmdir(download_dir)
        except Exception as e:
            logger.error(f"خطا در پاکسازی پوشه: {e}")
        
        if sent_count > 0:
            await msg.edit_text(f"✅ {sent_count} فایل ارسال شد!")
        else:
            await msg.edit_text("❌ فایلی ارسال نشد. ممکن است حجم زیاد باشد.")
        
    except Exception as e:
        logger.error(f"خطا: {e}", exc_info=True)
        error_msg = str(e)
        
        # تشخیص نوع خطا برای کاربر
        if "shortcode" in error_msg.lower():
            error_msg = "کد پست نامعتبر است"
        elif "login" in error_msg.lower():
            error_msg = "پست خصوصی است یا نیاز به لاگین دارد"
        elif "403" in error_msg:
            error_msg = "دسترسی محدود شده است"
        elif "404" in error_msg:
            error_msg = "پست پیدا نشد"
        
        await msg.edit_text(f"❌ {error_msg[:100]}")

def main():
    if not BOT_TOKEN or BOT_TOKEN == "توکن_خودت":
        logger.error("❌ BOT_TOKEN تنظیم نشده!")
        logger.error("لطفاً توکن را در Railway Variables قرار دهید")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))
    
    logger.info("=" * 50)
    logger.info("🤖 ربات دانلود از اینستاگرام")
    logger.info("🚀 روی سرور فعال شد...")
    logger.info("📱 منتظر درخواست‌ها...")
    logger.info("=" * 50)
    
    app.run_polling(
        poll_interval=1.0,
        timeout=30,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
