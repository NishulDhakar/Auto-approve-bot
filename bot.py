"""
bot.py
──────
Entry point. Run with: python bot.py
"""

import asyncio
import logging

from telegram import BotCommand
from telegram.ext import (
    Application,
    ChatJoinRequestHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.config import settings
from bot.handlers.commands import (
    handle_start,
    button_callback,
    handle_message,
)
from bot.handlers.join import handle_join_request

logger = logging.getLogger(__name__)

_COMMANDS = [
    BotCommand("start", "Show the main menu"),
]

async def _post_init(app: Application) -> None:
    """
    Called once after the bot connects.
    Registers global commands.
    """
    try:
        await app.bot.set_my_commands(commands=_COMMANDS)
        logger.info("Global commands registered.")
    except Exception as exc:
        logger.warning("Could not set global commands: %s", exc)


def build_app() -> Application:
    app = (
        Application.builder()
        .token(settings.bot_token)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .post_init(_post_init)
        .build()
    )

    # Join requests (public)
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    # Main menu command
    app.add_handler(CommandHandler("start", handle_start))

    # Callback Query for inline buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Catch-all for text and forwarded messages (used for /setwelcome and /addchannel)
    app.add_handler(MessageHandler(filters.TEXT | filters.FORWARDED, handle_message))

    return app


def main() -> None:
    logger.info("Bot starting… admins=%s", settings.admin_ids)
    app = build_app()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
