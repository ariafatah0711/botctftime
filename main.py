import os
import logging
import asyncio

import discord
from discord.ext import commands


def _build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True

    return commands.Bot(command_prefix="!", intents=intents, help_command=None)


bot = _build_bot()


@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
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

    async def runner() -> None:
        await _load_extensions()
        try:
            await bot.start(token)
        except discord.LoginFailure as exc:
            raise RuntimeError("Discord login failed: token is invalid or revoked.") from exc
        finally:
            if not bot.is_closed():
                await bot.close()

    asyncio.run(runner())


if __name__ == "__main__":
    main()
