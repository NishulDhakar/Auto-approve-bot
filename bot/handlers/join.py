"""
bot/handlers/join.py
────────────────────
Handles ChatJoinRequest events:
  1. Approves the request immediately
  2. Saves the user to the database (non-blocking)
  3. Sends a welcome DM (non-blocking – fails silently if user blocked bot)
"""

import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from bot.config import settings
from bot.database import save_user

logger = logging.getLogger(__name__)


async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    request = update.chat_join_request
    if not request:
        return

    user    = request.from_user
    chat_id = request.chat.id
    uid     = user.id

    if not settings.is_channel_authorized(chat_id):
        logger.warning(
            "Unauthorized join request → chat=%s user=%s. Ignoring.",
            chat_id, uid
        )
        return

    logger.info(
        "Join request → chat=%s user=%s (@%s)",
        chat_id, uid, user.username or "—",
    )

    # ── 1. Approve first – always ─────────────────────────────────────────────
    try:
        await request.approve()
        logger.info("Approved user %d into chat %s.", uid, chat_id)
    except Exception as exc:
        logger.error("Failed to approve user %d: %s", uid, exc)
        return  # Nothing else to do if approve failed

    # ── 2. Save to DB (fire-and-forget; don't block approval on DB errors) ────
    await save_user(
        telegram_id=uid,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        source=f"channel_{chat_id}",
    )

    # ── 3. Welcome DM ─────────────────────────────────────────────────────────
    welcome_config = settings.get_welcome_for_channel(chat_id)
    
    if welcome_config:
        text = welcome_config.get("message", "Hey {first_name}! Welcome! 🎉").replace("{first_name}", user.first_name or "User")
        button_text = welcome_config.get("button_text")
        button_url = welcome_config.get("button_url")
        
        reply_markup = None
        if button_text and button_url:
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(button_text, url=button_url)]
            ])
            
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=text,
                reply_markup=reply_markup,
            )
            logger.info("Welcome DM sent to user %d for chat %s.", uid, chat_id)
        except Exception as exc:
            # Common: user hasn't started the bot / has blocked it
            logger.warning("Could not DM user %d: %s", uid, exc)
