import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from urllib.parse import urlencode

import aiohttp
import discord
from discord.ext import commands, tasks

# =========================
# FUNCTIONS
# =========================
def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str):
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None

# =========================
# ENVIRONMENT VARIABLES
# =========================
TEAM_NAME = os.getenv("TEAM_NAME", "NFCC")
TEAM_URL = os.getenv("TEAM_URL", "https://ctftime.org/team/390784")
TEAM_DESCRIPTION = os.getenv(
    "TEAM_DESCRIPTION",
    "Komunitas CTF dan Cyber Security untuk belajar, sparring, dan main bareng.",
)
TEAM_CONTACT = os.getenv("TEAM_CONTACT", "Hubungi admin server")
TEAM_DISCORD_INVITE = os.getenv("TEAM_DISCORD_INVITE", "")

CTF_ROLE_ID = _env_int("CTF_ROLE_ID")
FINDTEAM_TAG_EVERYONE = _env_flag("FINDTEAM_TAG_EVERYONE", True)
FINDTEAM_TAG_ROLE = _env_flag("FINDTEAM_TAG_ROLE", True)

CTFTIME_NOTIFIER_ENABLED = _env_flag("CTFTIME_NOTIFIER_ENABLED", True)
CTFTIME_NOTIFY_CHANNEL_ID = _env_int("CTFTIME_NOTIFY_CHANNEL_ID")
CTFTIME_POLL_MINUTES = max(5, _env_int("CTFTIME_POLL_MINUTES") or 60)
CTFTIME_LOOKAHEAD_DAYS = max(1, _env_int("CTFTIME_LOOKAHEAD_DAYS") or 7)
CTFTIME_MAX_EVENTS_PER_POLL = max(1, _env_int("CTFTIME_MAX_EVENTS_PER_POLL") or 3)
CTFTIME_SEND_EXISTING_ON_START = _env_flag("CTFTIME_SEND_EXISTING_ON_START", False)
CTFTIME_NOTIFY_EVERYONE = _env_flag("CTFTIME_NOTIFY_EVERYONE", False)


def _format_discord_timestamp(dt: datetime) -> str:
    unix_ts = int(dt.timestamp())
    return f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _fetch_upcoming_events(limit: int, lookahead_days: int) -> List[Dict]:
    now = datetime.now(timezone.utc)
    finish = now + timedelta(days=lookahead_days)
    params = {
        "limit": str(limit),
        "start": str(int(now.timestamp())),
        "finish": str(int(finish.timestamp())),
    }
    url = f"https://ctftime.org/api/v1/events/?{urlencode(params)}"

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()

    if not isinstance(data, list):
        return []

    upcoming = []
    for event in data:
        try:
            start_dt = _parse_iso_datetime(event["start"])
            if start_dt >= now:
                upcoming.append(event)
        except Exception:
            continue

    upcoming.sort(key=lambda x: x.get("start", ""))
    return upcoming

# =========================
# BOT SETUP
# =========================
class Commands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.announced_event_ids = set()
        self.notifier_bootstrapped = False
        self.notifier_permission_warning_sent = False

        if CTFTIME_NOTIFIER_ENABLED and CTFTIME_NOTIFY_CHANNEL_ID:
            self.ctftime_notifier.change_interval(minutes=CTFTIME_POLL_MINUTES)
            self.ctftime_notifier.start()

    def cog_unload(self):
        if self.ctftime_notifier.is_running():
            self.ctftime_notifier.cancel()

    async def _send_event_embed(self, channel: discord.TextChannel, event: Dict):
        start_dt = _parse_iso_datetime(event["start"])
        finish_dt = _parse_iso_datetime(event["finish"])
        duration = event.get("duration", {})
        days = duration.get("days", 0)
        hours = duration.get("hours", 0)

        embed = discord.Embed(
            title=f"📢 Upcoming CTF: {event.get('title', 'Unknown Event')}",
            description=event.get("description", "No description")[:1200],
            url=event.get("ctftime_url") or event.get("url") or TEAM_URL,
            color=0xffa500,
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(name="🕒 Start", value=_format_discord_timestamp(start_dt), inline=False)
        embed.add_field(name="🏁 Finish", value=_format_discord_timestamp(finish_dt), inline=False)
        embed.add_field(name="⏱ Duration", value=f"{days} day(s), {hours} hour(s)", inline=True)
        embed.add_field(name="🎮 Format", value=event.get("format", "Unknown"), inline=True)
        embed.add_field(name="🔓 Restrictions", value=event.get("restrictions", "Unknown"), inline=True)

        event_url = event.get("url") or "Not provided"
        embed.add_field(name="🌐 Event URL", value=event_url, inline=False)
        embed.add_field(name="🏆 CTFtime", value=event.get("ctftime_url", "Not provided"), inline=False)

        if event.get("logo"):
            embed.set_thumbnail(url=event["logo"])

        embed.set_footer(text="CTFtime Upcoming Notifier")

        # Try configured mention behavior first, then fallback without mention.
        try:
            if CTFTIME_NOTIFY_EVERYONE:
                await channel.send(
                    content="@everyone",
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(everyone=True),
                )
            else:
                await channel.send(embed=embed)
        except discord.Forbidden:
            await channel.send(embed=embed)

    @tasks.loop(minutes=60)
    async def ctftime_notifier(self):
        channel = self.bot.get_channel(CTFTIME_NOTIFY_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            events = await _fetch_upcoming_events(limit=100, lookahead_days=CTFTIME_LOOKAHEAD_DAYS)
        except Exception:
            return

        current_ids = {event.get("id") for event in events if event.get("id") is not None}

        # On first run, optionally skip announcing existing events to avoid spam.
        if not self.notifier_bootstrapped:
            self.announced_event_ids.update(current_ids)
            self.notifier_bootstrapped = True
            if CTFTIME_SEND_EXISTING_ON_START:
                for event in events[:CTFTIME_MAX_EVENTS_PER_POLL]:
                    event_id = event.get("id")
                    if event_id is None:
                        continue
                    try:
                        await self._send_event_embed(channel, event)
                    except discord.Forbidden:
                        if not self.notifier_permission_warning_sent:
                            print(
                                "CTFtime notifier cannot send message to target channel "
                                "(missing Send Messages/Embed Links permission)."
                            )
                            self.notifier_permission_warning_sent = True
                        return
                    except Exception:
                        continue
            return

        new_events = [event for event in events if event.get("id") not in self.announced_event_ids]
        new_events = new_events[:CTFTIME_MAX_EVENTS_PER_POLL]

        for event in new_events:
            event_id = event.get("id")
            if event_id is None:
                continue
            try:
                await self._send_event_embed(channel, event)
                self.announced_event_ids.add(event_id)
            except discord.Forbidden:
                if not self.notifier_permission_warning_sent:
                    print(
                        "CTFtime notifier cannot send message to target channel "
                        "(missing Send Messages/Embed Links permission)."
                    )
                    self.notifier_permission_warning_sent = True
                return
            except Exception:
                continue

        # Keep only IDs that are still relevant to prevent unbounded growth.
        self.announced_event_ids.intersection_update(current_ids)

    @ctftime_notifier.before_loop
    async def before_ctftime_notifier(self):
        await self.bot.wait_until_ready()

    # =========================
    # PING
    # =========================

    @commands.hybrid_command(name="ping", description="Cek latency bot")
    async def ping(self, ctx):

        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Bot Status",
            description="Bot aktif dan siap dipakai.",
            color=0x00ff88
        )
        embed.add_field(name="Latency", value=f"{latency} ms", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author}")
        embed.timestamp = discord.utils.utcnow()

        await ctx.reply(embed=embed)

    # =========================
    # INFO CTF
    # =========================

    @commands.hybrid_command(name="infoctf", description="Info tim CTF server ini")
    async def infoctf(self, ctx):

        guild = ctx.guild
        if guild is None:
            await ctx.reply("❌ Command ini hanya bisa dipakai di dalam server.")
            return

        embed = discord.Embed(
            title=f"🏆 {TEAM_NAME} - Team Info",
            description=TEAM_DESCRIPTION,
            url=TEAM_URL,
            color=0x00c2ff,
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(name="🏆 CTFtime", value=f"[Lihat Profil Tim]({TEAM_URL})", inline=False)
        embed.add_field(name="💬 Contact", value=TEAM_CONTACT, inline=False)
        embed.add_field(name="🖥 Server", value=guild.name, inline=True)
        embed.add_field(name="👥 Members", value=str(guild.member_count), inline=True)

        if TEAM_DISCORD_INVITE:
            embed.add_field(name="🔗 Join Server", value=TEAM_DISCORD_INVITE, inline=False)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.set_footer(text="Powered by CTFtime")

        await ctx.reply(embed=embed)

    # =========================
    # FIND TEAM
    # =========================

    @commands.hybrid_command(name="findteam", description="Mencari tim untuk CTF")
    async def findteam(
        self,
        ctx,
        nama_ctf: str,
        team: str,
        invite: str,
        website: str,
        note: str = "No note"
    ):

        if ctx.guild is None:
            await ctx.reply("❌ Command ini hanya bisa dipakai di dalam server.")
            return

        role = ctx.guild.get_role(CTF_ROLE_ID) if CTF_ROLE_ID else None

        embed = discord.Embed(
            title=f"🚩 OPEN RECRUITMENT: {nama_ctf}",
            description="Cari member untuk push rank bareng. Drop info di bawah ini.",
            color=0xff4444
        )

        embed.add_field(name="👥 Team", value=team, inline=True)
        embed.add_field(name="🎯 Event", value=nama_ctf, inline=True)

        if invite.startswith("http"):
            embed.add_field(name="🔗 Join", value=invite, inline=False)
        else:
            embed.add_field(name="🔑 Invite Code", value=f"`{invite}`", inline=False)

        embed.add_field(name="🌐 Event URL", value=website, inline=False)
        embed.add_field(name="🏆 Team CTFtime", value=f"[Lihat Profil Tim]({TEAM_URL})", inline=False)
        embed.add_field(name="📝 Catatan", value=note, inline=False)
        embed.timestamp = discord.utils.utcnow()

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )

        mentions = []
        if FINDTEAM_TAG_EVERYONE:
            mentions.append("@everyone")
        if FINDTEAM_TAG_ROLE and role:
            mentions.append(f"<@&{role.id}>")

        mention = " ".join(mentions)

        await ctx.send(
            content=mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True, roles=True)
        )


# =========================
# LOAD COG
# =========================

async def setup(bot):
    await bot.add_cog(Commands(bot))
