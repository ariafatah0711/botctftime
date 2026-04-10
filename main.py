import os
import logging
import asyncio
from typing import List

import discord
from discord.ext import commands


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int_list(name: str) -> List[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []

    out: List[int] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        out.append(int(item))
    return out


def _build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = _env_flag("DISCORD_ENABLE_MESSAGE_CONTENT", False)

    return commands.Bot(command_prefix="!", intents=intents, help_command=None)


bot = _build_bot()
logger = logging.getLogger("botctf")


@bot.event
async def on_ready() -> None:
    user = bot.user
    if user is not None:
        print(f"Logged in as {user} (ID: {user.id})")
    else:
        print("Logged in, but bot user is not available yet.")
    print("Bot is ready.")

    guild_ids = _env_int_list("DISCORD_SYNC_GUILD_IDS")
    if guild_ids:
        synced_total = 0
        for guild_id in guild_ids:
            guild = discord.Object(id=guild_id)
            synced = await bot.tree.sync(guild=guild)
            synced_total += len(synced)
        logger.info("Slash commands synced to %s guild(s), total commands: %s", len(guild_ids), synced_total)
    else:
        synced = await bot.tree.sync()
        logger.info("Global slash commands synced: %s", len(synced))


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
            if bot.intents.message_content:
                logger.warning(
                    "Privileged intent not enabled in Developer Portal. Retrying with slash-only mode "
                    "(message content intent disabled)."
                )
                bot.intents.message_content = False
                await bot.start(token)
            else:
                raise RuntimeError(
                    "Privileged intents required. Enable Message Content Intent in Discord Developer Portal "
                    "or keep DISCORD_ENABLE_MESSAGE_CONTENT=false for slash commands only."
                ) from exc
        finally:
            if not bot.is_closed():
                await bot.close()

    asyncio.run(runner())


if __name__ == "__main__":
    main()
