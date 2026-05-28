"""
bot/handlers/commands.py
────────────────────────
Command handlers for all bot interactions.
"""

import logging
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes

from bot.config import settings
from bot.database import get_global_stats, get_user_stats, save_user

logger = logging.getLogger(__name__)

# ── /start ───────────────────────────────────────────────────────────────────
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome card with inline buttons."""
    user = update.effective_user
    name = user.first_name or "User"
    is_admin = settings.is_admin(user.id)

    # Save user who started the bot
    await save_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        source="start"
    )

    text = (
        f"👋 Welcome {name} to the Auto-Approve Bot!\n\n"
        "Manage your channel's join requests effortlessly. Select an option below to get started:"
    )

    keyboard = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="addchannel")],
        [InlineKeyboardButton("📝 Set Welcome Message", callback_data="setwelcome")],
        [InlineKeyboardButton("📊 My Stats", callback_data="stats")],
    ]

    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 Admin Stats", callback_data="admin_stats")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

# ── Callback Query Handler ───────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button clicks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    if data == "addchannel":
        context.user_data["state"] = "awaiting_forward"
        await query.message.reply_text(
            "➕ **Add a Channel**\n\n"
            "1️⃣ Add me as an Admin to your channel with the **'Invite Users'** permission.\n"
            "2️⃣ Forward **any message** from that channel to me here.\n\n"
            "Waiting for your forwarded message...",
            parse_mode=constants.ParseMode.MARKDOWN
        )

    elif data == "setwelcome":
        context.user_data["state"] = "awaiting_welcome"
        await query.message.reply_text(
            "📝 **Set Welcome Message**\n\n"
            "Send me the message you want to send to users when they join your channel. "
            "You can use `{first_name}` as a placeholder for their name.\n\n"
            "**Want a button?**\n"
            "Use the format: `Your Message | Button Text | https://link.com`\n\n"
            "Waiting for your message...",
            parse_mode=constants.ParseMode.MARKDOWN
        )

    elif data == "stats":
        config = settings.get_user_config(user_id)
        channels = config.get("channels", [])
        total, today = await get_user_stats(channels)
        
        await query.message.reply_text(
            f"📊 **Your Stats**\n\n"
            f"Channels Connected: `{len(channels)}`\n"
            f"Today Joined: `{today}`\n"
            f"Total Joined: `{total}`",
            parse_mode=constants.ParseMode.MARKDOWN
        )

    elif data == "admin_stats":
        if not settings.is_admin(user_id):
            return
        
        total, today = await get_global_stats()
        all_channels = settings.get_all_authorized_channels()
        
        await query.message.reply_text(
            f"👑 **Admin Stats**\n\n"
            f"Total users who started bot: `{total}`\n"
            f"Total channels all connected: `{len(all_channels)}`",
            parse_mode=constants.ParseMode.MARKDOWN
        )

def _is_valid_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

# ── Message Handler ──────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text and forwarded messages based on user state."""
    state = context.user_data.get("state")
    user_id = update.effective_user.id

    if state == "awaiting_forward":
        # Check if it's a forwarded message from a channel
        origin = update.message.forward_origin
        
        # PTB 20+ uses forward_origin
        if origin and origin.type == constants.MessageOriginType.CHANNEL:
            chat_id = origin.chat.id
            title = origin.chat.title
            
            # Check if bot is admin
            try:
                member = await context.bot.get_chat_member(chat_id, context.bot.id)
                if member.status not in (constants.ChatMemberStatus.ADMINISTRATOR, constants.ChatMemberStatus.OWNER):
                    await update.message.reply_text(f"❌ I am not an admin in **{title}**. Please make me an admin first and try again.", parse_mode=constants.ParseMode.MARKDOWN)
                    return
            except Exception as e:
                logger.warning(f"Failed to verify admin status for chat {chat_id}: {e}")
                await update.message.reply_text("❌ Could not verify admin status. Ensure I am added to the channel as an admin and try again.")
                return

            settings.add_channel_for_user(user_id, chat_id)
            context.user_data["state"] = None
            await update.message.reply_text(f"✅ **Success!**\n\nChannel **{title}** has been connected. I will now auto-approve join requests for it.", parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("❌ This doesn't look like a forwarded message from a channel. Please try again.")

    elif state == "awaiting_welcome":
        if not update.message.text:
            await update.message.reply_text("❌ Please send text only.")
            return

        raw_value = update.message.text.strip()
        segments = [segment.strip() for segment in raw_value.split("|")]
        message_text = segments[0]

        if not message_text:
            await update.message.reply_text("❌ Welcome message cannot be empty.")
            return

        button_text = None
        button_url = None

        if len(segments) == 3:
            candidate_text = segments[1]
            candidate_url = segments[2]
            
            if candidate_text.lower() != "none" or candidate_url.lower() != "none":
                if not candidate_text or not candidate_url:
                    await update.message.reply_text("❌ Button text and URL must both be provided.", parse_mode=constants.ParseMode.MARKDOWN)
                    return
                if not _is_valid_http_url(candidate_url):
                    await update.message.reply_text("❌ Button URL must start with http:// or https://")
                    return
                button_text = candidate_text
                button_url = candidate_url
        elif len(segments) != 1:
            await update.message.reply_text("❌ Use either only the message, or `message | button text | button url`.", parse_mode=constants.ParseMode.MARKDOWN)
            return

        settings.set_welcome_for_user(user_id, message_text, button_text, button_url)
        context.user_data["state"] = None

        response_lines = ["✅ **Welcome message updated!**", "", f"📝 **Message:**\n{message_text}"]
        if button_text and button_url:
            response_lines.extend(["", f"🔘 **Button:** {button_text}", f"🔗 **URL:** {button_url}"])
        else:
            response_lines.append("\n🔘 **Button:** None")

        await update.message.reply_text("\n".join(response_lines), parse_mode=constants.ParseMode.MARKDOWN)
