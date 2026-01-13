"""
Telegram bot interface for RAG AI Decision Assistant
Uses modern python-telegram-bot v20+ API
"""
import logging
import os
from typing import Dict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import requests

from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API configuration
def get_api_url() -> str:
    """Get API URL based on environment"""
    api_host = os.getenv("API_HOST", "localhost")
    api_port = settings.api_port
    return f"http://{api_host}:{api_port}/ask"

API_URL = get_api_url()

# In-memory session storage per user (user_id -> session_id)
user_sessions: Dict[int, str] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command"""
    user = update.effective_user
    welcome_message = (
        f"Привет, {user.first_name}! 👋\n\n"
        f"Я AI-ассистент для принятия решений в волейболе.\n"
        f"Задавайте мне вопросы на русском или английском языке.\n\n"
        f"Я отвечаю только на основе предоставленной базы знаний.\n\n"
        f"Начните с вопроса!"
    )
    await update.message.reply_text(welcome_message)
    logger.info(f"User {user.id} ({user.username}) started the bot")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages from users"""
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    question = update.message.text.strip()
    
    # Get or create session for user
    session_id = user_sessions.get(user.id)
    
    try:
        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        # Prepare request payload
        payload = {
            "user_id": str(user.id),
            "question": question,
            "session_id": session_id
        }
        
        logger.info(f"User {user.id} asked: {question[:100]}...")
        
        # Call API
        response = requests.post(
            API_URL,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Update session ID
        user_sessions[user.id] = result.get("session_id", session_id)
        
        # Extract answer
        answer = result.get("answer", "Не удалось получить ответ.")
        confidence = result.get("confidence", 0.0)
        
        # Format response with confidence indicator
        if confidence < 0.5:
            answer += "\n\n⚠️ Низкая уверенность в ответе. Проверьте информацию в базе знаний."
        
        # Send answer
        await update.message.reply_text(answer)
        
        logger.info(f"Answer sent to user {user.id} (confidence: {confidence:.2f})")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for user {user.id}: {str(e)}")
        error_message = (
            "Извините, произошла ошибка при обработке вашего вопроса. "
            "Пожалуйста, попробуйте еще раз через несколько секунд."
        )
        await update.message.reply_text(error_message)
        
    except Exception as e:
        logger.error(f"Unexpected error for user {user.id}: {str(e)}")
        error_message = "Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже."
        await update.message.reply_text(error_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command"""
    help_text = (
        "📚 **Помощь**\n\n"
        "Я AI-ассистент для принятия решений в волейболе.\n\n"
        "**Команды:**\n"
        "/start - Начать работу\n"
        "/help - Показать эту справку\n\n"
        "**Как использовать:**\n"
        "Просто задайте мне вопрос на русском или английском языке. "
        "Я отвечу на основе предоставленной базы знаний.\n\n"
        "**Важно:** Я отвечаю только на основе знаний из базы данных. "
        "Если информации нет в базе, я сообщу об этом."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


def main() -> None:
    """Start the bot"""
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set in environment variables")
        raise ValueError("Telegram bot token is required. Set TELEGRAM_BOT_TOKEN in .env file")
    
    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    
    # Start bot
    logger.info("Starting Telegram bot...")
    logger.info(f"API URL: {API_URL}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
