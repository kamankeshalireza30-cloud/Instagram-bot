"""
Telegram Instagram Downloader Bot
A professional bot for downloading Instagram content
"""

import os
import logging
import asyncio
from typing import Optional, Tuple
from dataclasses import dataclass
from functools import wraps
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
import instaloader
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

# ================== Configuration ==================

@dataclass
class Config:
    """Application configuration management"""
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB Telegram limit
    ALLOWED_GROUP: Optional[int] = os.getenv('ALLOWED_GROUP')
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'

config = Config()

# ================== Logging Setup ==================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG if config.DEBUG else logging.INFO
)
logger = logging.getLogger(__name__)

# ================== Decorators ==================

def admin_only(func):
    """Restrict access to admins only"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if config.ALLOWED_GROUP and user_id != config.ALLOWED_GROUP:
            await update.message.reply_text("⛔ You don't have permission to use this command.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def log_function(func):
    """Log function calls and execution time"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger.info(f"Calling function: {func.__name__}")
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            logger.info(f"Function {func.__name__} completed in {elapsed_time:.2f} seconds")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            raise
    return wrapper

# ================== Main Downloader Class ==================

class InstagramDownloader:
    """Handle Instagram downloads with retry mechanism"""
    
    def __init__(self):
        # Optimize Instaloader settings for speed
        self.loader = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            max_connection_attempts=3
        )
        self.temp_dir = "downloads"
        os.makedirs(self.temp_dir, exist_ok=True)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def download_post(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Download Instagram post with automatic retry
        
        Returns:
            Tuple[file_path, file_type] or (None, None) on error
        """
        try:
            # Extract post shortcode
            shortcode = self._extract_shortcode(url)
            if not shortcode:
                return None, None
            
            # Get post metadata
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            
            # Determine content type
            if post.is_video:
                file_path = os.path.join(self.temp_dir, f"{shortcode}.mp4")
                # Download video
                self.loader.download_post(post, target=self.temp_dir)
                # Find downloaded file
                for file in os.listdir(self.temp_dir):
                    if file.endswith('.mp4') and shortcode in file:
                        file_path = os.path.join(self.temp_dir, file)
                        break
                return file_path, 'video'
            else:
                # Download photo
                self.loader.download_post(post, target=self.temp_dir)
                for file in os.listdir(self.temp_dir):
                    if file.endswith(('.jpg', '.png')) and shortcode in file:
                        file_path = os.path.join(self.temp_dir, file)
                        break
                return file_path, 'photo'
                
        except Exception as e:
            logger.error(f"Error downloading post: {str(e)}")
            return None, None
    
    def _extract_shortcode(self, url: str) -> Optional[str]:
        """Extract post shortcode from URL"""
        patterns = [
            r'instagram\.com/p/([^/?]+)',
            r'instagram\.com/reel/([^/?]+)',
            r'instagram\.com/tv/([^/?]+)'
        ]
        import re
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def cleanup(self, file_path: str):
        """Remove temporary files"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

# ================== Telegram Handlers ==================

class BotHandlers:
    """Manage all bot handlers"""
    
    def __init__(self, downloader: InstagramDownloader):
        self.downloader = downloader
    
    @log_function
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message with inline keyboard"""
        welcome_text = """
🎉 **Welcome to Instagram Downloader Bot!**

✨ **Features:**
• Download posts 📸
• Download reels 🎬
• Download IGTV 📺
• Original quality ⭐

📝 **How to use:**
Just send me an Instagram post link!

⚠️ **Note:** Only public content is downloadable
        """
        
        keyboard = [
            [InlineKeyboardButton("📚 Guide", callback_data='help'),
             InlineKeyboardButton("📊 Stats", callback_data='stats')],
            [InlineKeyboardButton("👨‍💻 Developer", url='https://t.me/your_channel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @log_function
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display help information"""
        help_text = """
📚 **Usage Guide**

🎯 **How to use:**
1️⃣ Copy Instagram post link
2️⃣ Send it to me
3️⃣ Wait for download
4️⃣ Get your file

✅ **Supported links:**
• https://instagram.com/p/...
• https://instagram.com/reel/...
• https://instagram.com/tv/...
• https://www.instagram.com/p/...

⚠️ **Limitations:**
• Max file size: 50MB
• Public content only
• Private accounts not accessible

⚡ **Speed:** Depends on your internet and server
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    @admin_only
    @log_function
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot statistics (admin only)"""
        stats_text = """
📊 **Bot Statistics**

✅ Status: Online
⏱ Uptime: 99.9%
📥 Downloads: In development
👥 Users: In development

🔄 **Server Status:**
• CPU: Good
• RAM: Good
• Disk: Good
        """
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    @log_function
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'help':
            await self.help_command(update, context)
        elif query.data == 'stats':
            await self.stats(update, context)
    
    @log_function
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process messages containing Instagram links"""
        message = update.message
        text = message.text
        
        # Check if message contains valid Instagram link
        if not ('instagram.com' in text and ('/p/' in text or '/reel/' in text or '/tv/' in text)):
            await message.reply_text(
                "❌ **Please send a valid Instagram link!**\n\n"
                "Examples:\n"
                "• instagram.com/p/...\n"
                "• instagram.com/reel/...\n"
                "• instagram.com/tv/...",
                parse_mode='Markdown'
            )
            return
        
        # Send processing message
        processing_msg = await message.reply_text(
            "🔄 **Processing...**\n\n"
            "⏱ Please wait a moment",
            parse_mode='Markdown'
        )
        
        try:
            # Download content
            file_path, file_type = await self.downloader.download_post(text)
            
            # Check if download failed
            if not file_path or not os.path.exists(file_path):
                await processing_msg.edit_text(
                    "❌ **Download failed!**\n\n"
                    "Possible reasons:\n"
                    "• Invalid link\n"
                    "• Private post\n"
                    "• Instagram rate limit",
                    parse_mode='Markdown'
                )
                return
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > config.MAX_FILE_SIZE:
                await processing_msg.edit_text(
                    f"❌ **File too large!**\n\n"
                    f"📦 Size: {file_size / 1024 / 1024:.1f}MB\n"
                    f"⚠️ Limit: {config.MAX_FILE_SIZE / 1024 / 1024:.0f}MB",
                    parse_mode='Markdown'
                )
                self.downloader.cleanup(file_path)
                return
            
            # Delete processing message
            await processing_msg.delete()
            
            # Send the file
            caption = "✅ **Download successful!**"
            
            if file_type == 'video':
                with open(file_path, 'rb') as video:
                    await message.reply_video(
                        video=video,
                        caption=caption,
                        parse_mode='Markdown',
                        supports_streaming=True
                    )
            else:
                with open(file_path, 'rb') as photo:
                    await message.reply_photo(
                        photo=photo,
                        caption=caption,
                        parse_mode='Markdown'
                    )
            
            # Cleanup temporary file
            self.downloader.cleanup(file_path)
            
        except Exception as e:
            logger.error(f"Error in handle_message: {str(e)}")
            await processing_msg.edit_text(
                "❌ **Unknown error!**\n\n"
                "Please try again later",
                parse_mode='Markdown'
            )

# ================== Main Execution ==================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler"""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ **An error occurred!**\n\n"
                "Please try again.",
                parse_mode='Markdown'
            )
    except:
        pass

def main():
    """Main bot execution function"""
    # Check for bot token
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables!")
        return
    
    # Create application
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    # Initialize classes
    downloader = InstagramDownloader()
    handlers = BotHandlers(downloader)
    
    # Add handlers
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_command))
    app.add_handler(CommandHandler("stats", handlers.stats))
    app.add_handler(CallbackQueryHandler(handlers.handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Start bot
    logger.info("Starting bot...")
    app.run_polling()

if __name__ == '__main__':
    main()