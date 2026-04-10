import os
import logging
import asyncio

import discord
from discord.ext import commands


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = _env_flag("DISCORD_ENABLE_MESSAGE_CONTENT", True)

    return commands.Bot(command_prefix="!", intents=intents, help_command=None)


bot = _build_bot()


@bot.event
async def on_ready() -> None:
    user = bot.user
    if user is not None:
        print(f"Logged in as {user} (ID: {user.id})")
    else:
        print("Logged in, but bot user is not available yet.")
    print("Bot is ready.")


async def _load_extensions() -> None:
    await bot.load_extension("app")


def main() -> None:
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set. Please set it in your environment or .env file.")

    # Friendly guard to catch common copy/paste mistake from "Bot <token>" format.
    if token.lower().startswith("bot "):
        raise RuntimeError("DISCORD_TOKEN must be raw token only (without 'Bot ' prefix).")

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("botctf")

    if not bot.intents.message_content:
        logger.warning(
            "DISCORD_ENABLE_MESSAGE_CONTENT is disabled. Prefix commands may not work; slash commands remain available."
        )

    async def runner() -> None:
        await _load_extensions()
        try:
            await bot.start(token)
        except discord.LoginFailure as exc:
            raise RuntimeError("Discord login failed: token is invalid or revoked.") from exc
        except discord.PrivilegedIntentsRequired as exc:
            raise RuntimeError(
                "Privileged intents required. Enable Message Content Intent in Discord Developer Portal "
                "or set DISCORD_ENABLE_MESSAGE_CONTENT=false to run slash commands only."
            ) from exc
        finally:
            if not bot.is_closed():
                await bot.close()

    asyncio.run(runner())


if __name__ == "__main__":
    main()
