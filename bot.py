import os
import logging
import asyncio
import yt_dlp
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 ربات دانلود از اینستاگرام (نسخه yt-dlp)\n"
        "لینک پست، ریل یا ویدیو را بفرستید.\n\n"
        "✅ پشتیبانی از:\n"
        "• پست‌های عکس\n"
        "• ریل‌ها (ویدیوهای کوتاه)\n"
        "• IGTV\n"
        "• استوری‌های عمومی"
    )

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if "instagram.com" not in url:
        await update.message.reply_text("❌ لینک اینستاگرام بفرستید.")
        return
    
    msg = await update.message.reply_text("⏳ در حال پردازش...")
    
    try:
        # تنظیمات yt-dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
            'format': 'best',
            'socket_timeout': 30,
            'retries': 3,
        }
        
        logger.info(f"دانلود لینک: {url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # دریافت اطلاعات بدون دانلود اولیه
            info = ydl.extract_info(url, download=False)
            
            if not info:
                await msg.edit_text("❌ اطلاعات پست پیدا نشد")
                return
            
            title = info.get('title', 'Instagram Media')
            formats = info.get('formats', [])
            
            if not formats:
                await msg.edit_text("❌ فرمت ویدیو/عکس پیدا نشد")
                return
            
            # بهترین کیفیت را انتخاب کن
            best_format = max(formats, key=lambda x: x.get('quality', 0))
            video_url = best_format.get('url')
            
            if not video_url:
                await msg.edit_text("❌ لینک دانلود پیدا نشد")
                return
            
            # دانلود فایل
            logger.info(f"دانلود از: {video_url[:100]}...")
            ydl.download([url])
            
            # پیدا کردن فایل دانلود شده
            filename = ydl.prepare_filename(info)
            
            if os.path.exists(filename):
                file_size = os.path.getsize(filename) / (1024 * 1024)
                logger.info(f"فایل دانلود شد: {filename} ({file_size:.1f}MB)")
                
                # ارسال به تلگرام
                with open(filename, 'rb') as f:
                    if filename.endswith('.mp4') or filename.endswith('.webm'):
                        await update.message.reply_video(
                            video=f,
                            caption=title[:1000],
                            supports_streaming=True,
                            read_timeout=60,
                            write_timeout=60
                        )
                    else:
                        await update.message.reply_document(
                            document=f,
                            caption=title[:1000]
                        )
                
                # پاکسازی
                os.remove(filename)
                await msg.edit_text("✅ دانلود و ارسال کامل شد!")
                
            else:
                await msg.edit_text("❌ فایل دانلود نشد")
        
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"خطای yt-dlp: {e}")
        await msg.edit_text("❌ دانلود ممکن نیست. لینک عمومی است؟")
        
    except Exception as e:
        logger.error(f"خطای کلی: {e}")
        await msg.edit_text(f"❌ خطا: {str(e)[:100]}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download))
    
    logger.info("🤖 ربات yt-dlp فعال شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
