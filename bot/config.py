"""
bot/config.py
─────────────
Single source of truth for all environment-based settings.
Raises EnvironmentError on startup if required vars are missing.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config File Path ─────────────────────────────────────────────────────────
CONFIG_FILE = "config.json"

# ── Settings dataclass ────────────────────────────────────────────────────────
@dataclass
class Settings:
    bot_token: str
    supabase_url: str
    supabase_key: str
    admin_ids: List[int] = field(default_factory=list)
    users_config: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    def get_user_config(self, user_id: int) -> Dict[str, Any]:
        key = str(user_id)
        if key not in self.users_config:
            self.users_config[key] = {
                "channels": [],
                "welcome": {
                    "message": "Hey {first_name}! Welcome! 🎉",
                    "button_text": None,
                    "button_url": None
                }
            }
        return self.users_config[key]

    def add_channel_for_user(self, user_id: int, channel_id: int) -> None:
        config = self.get_user_config(user_id)
        if channel_id not in config["channels"]:
            config["channels"].append(channel_id)
            self._save_dynamic_config()

    def set_welcome_for_user(self, user_id: int, message: str, button_text: Optional[str] = None, button_url: Optional[str] = None) -> None:
        config = self.get_user_config(user_id)
        config["welcome"]["message"] = message
        config["welcome"]["button_text"] = button_text
        config["welcome"]["button_url"] = button_url
        self._save_dynamic_config()

    def get_channel_owner(self, channel_id: int) -> Optional[int]:
        for uid_str, config in self.users_config.items():
            if channel_id in config.get("channels", []):
                return int(uid_str)
        return None

    def get_welcome_for_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        owner_id = self.get_channel_owner(channel_id)
        if owner_id:
            return self.get_user_config(owner_id).get("welcome")
        return None

    def get_all_authorized_channels(self) -> Set[int]:
        channels = set()
        for config in self.users_config.values():
            for ch in config.get("channels", []):
                channels.add(ch)
        return channels

    def is_channel_authorized(self, chat_id: int) -> bool:
        return chat_id in self.get_all_authorized_channels()

    def _save_dynamic_config(self) -> None:
        """Persist dynamic settings to JSON."""
        data = {
            "users_config": self.users_config,
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
            logger.info("Dynamic config saved to %s", CONFIG_FILE)
        except Exception as exc:
            logger.error("Failed to save dynamic config: %s", exc)


def _load_dynamic_config() -> dict:
    """Load dynamic settings from JSON if they exist."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load dynamic config from %s: %s", CONFIG_FILE, exc)
    return {}


def _load_settings() -> Settings:
    missing: List[str] = []

    bot_token    = os.getenv("BOT_TOKEN", "").strip()
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()

    for name, val in [
        ("BOT_TOKEN", bot_token),
        ("SUPABASE_URL", supabase_url),
        ("SUPABASE_KEY", supabase_key),
    ]:
        if not val:
            missing.append(name)

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Check your .env file."
        )

    # Parse ADMIN_IDS – comma-separated integers
    admin_ids: List[int] = []
    raw_ids = os.getenv("ADMIN_IDS", "")
    for part in raw_ids.split(","):
        part = part.strip()
        if part:
            try:
                admin_ids.append(int(part))
            except ValueError:
                logger.warning("Skipping non-integer ADMIN_ID value: %r", part)

    # Load dynamic config
    dynamic_config = _load_dynamic_config()
    users_config = dynamic_config.get("users_config", {})

    settings = Settings(
        bot_token=bot_token,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        admin_ids=admin_ids,
        users_config=users_config,
    )

    logger.info(
        "Config loaded. Admins: %s | Total Authorized Channels: %d",
        settings.admin_ids,
        len(settings.get_all_authorized_channels())
    )
    return settings


# Module-level singleton – imported everywhere as `from bot.config import settings`
settings: Settings = _load_settings()
