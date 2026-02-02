import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import instaloader
import shutil

# خواندن توکن از متغیر محیطی
BOT_TOKEN = os.environ.get("BOT_TOKEN")

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
            download_video_thumbnails=False
        )
        
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # پوشه موقت
        download_dir = f"/tmp/insta_{shortcode}"
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir)
        os.makedirs(download_dir, exist_ok=True)
        
        # دانلود
        L.download_post(post, target=download_dir)
        
        # ارسال فایل‌ها
        sent_count = 0
        for file in os.listdir(download_dir):
            file_path = os.path.join(download_dir, file)
            
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
                            supports_streaming=True
                        )
                elif file.endswith(('.jpg', '.png', '.jpeg')):
                    with open(file_path, 'rb') as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption=f"@{post.owner_username}" if sent_count == 0 else None
                        )
                
                sent_count += 1
                logger.info(f"فایل ارسال شد: {file}")
                
            except Exception as e:
                logger.error(f"خطا در ارسال {file}: {e}")
        
        # پاکسازی
        shutil.rmtree(download_dir, ignore_errors=True)
        
        if sent_count > 0:
            await msg.edit_text(f"✅ {sent_count} فایل ارسال شد!")
        else:
            await msg.edit_text("❌ فایلی ارسال نشد. ممکن است حجم زیاد باشد.")
        
    except Exception as e:
        logger.error(f"خطا: {e}")
        error_msg = str(e)[:150]
        await msg.edit_text(f"❌ خطا: {error_msg}")

def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN تنظیم نشده!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))
    
    logger.info("🤖 ربات روی سرور فعال شد...")
    
    app.run_polling()

if __name__ == "__main__":
    main()
