from typing import Dict

import discord
from discord.ext import commands, tasks

from config import SETTINGS
from services.ctftime import fetch_upcoming_events, format_discord_timestamp, parse_iso_datetime

# =================================================================
# Keep the main logic of CTF-related commands and CTFtime notifier here.
# =================================================================
class CTFCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.announced_event_ids = set()
        self.notifier_bootstrapped = False
        self.notifier_permission_warning_sent = False

        if SETTINGS.ctftime_notify_channel_id:
            self.ctftime_notifier.change_interval(minutes=SETTINGS.ctftime_poll_minutes)
            self.ctftime_notifier.start()

    def cog_unload(self):
        if self.ctftime_notifier.is_running():
            self.ctftime_notifier.cancel()

    def _format_duration(self, event: Dict) -> str:
        duration = event.get("duration", {})
        days = duration.get("days", 0)
        hours = duration.get("hours", 0)
        return f"{days} hari, {hours} jam"

    def _detect_participation_mode(self, event: Dict) -> str:
        restrictions = str(event.get("restrictions", "")).strip()
        restrictions_lower = restrictions.lower()
        if restrictions and restrictions_lower not in {"open", "unknown"}:
            return restrictions

        description = str(event.get("description", "")).lower()
        if "individual competition" in description or "individual" in description:
            return "Individual"
        if "team" in description:
            return "Team"

        return "Open"

    def _build_event_embed(self, event: Dict) -> discord.Embed:
        start_dt = parse_iso_datetime(event["start"])
        finish_dt = parse_iso_datetime(event["finish"])
        participation_mode = self._detect_participation_mode(event)

        embed = discord.Embed(
            title=f"🚩 {event.get('title', 'Unknown Event')}",
            description=(
                f"**Mulai:** {format_discord_timestamp(start_dt)}\n"
                f"**Selesai:** {format_discord_timestamp(finish_dt)}\n"
                f"**Durasi:** {self._format_duration(event)}\n"
                f"**Format:** {event.get('format', 'Unknown')}\n"
                f"**Mode:** {participation_mode}"
            ),
            url=event.get("ctftime_url") or event.get("url") or SETTINGS.team_url,
            color=0xFFA500,
            timestamp=discord.utils.utcnow(),
        )

        event_url = event.get("url")
        if event_url:
            embed.add_field(name="🌐 Website", value=event_url, inline=False)

        if event.get("logo"):
            embed.set_thumbnail(url=event["logo"])

        embed.set_footer(text="CTFtime Notifier")
        return embed

    async def _send_event_embed(self, channel: discord.TextChannel, event: Dict):
        embed = self._build_event_embed(event)
        role_id = SETTINGS.ctftime_notify_role_id
        mention_text = f"<@&{role_id}> 📢 Event upcoming CTFtime" if role_id else "📢 Event upcoming CTFtime"

        await channel.send(
            content=mention_text,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    @tasks.loop(minutes=60)
    async def ctftime_notifier(self):
        channel_id = SETTINGS.ctftime_notify_channel_id
        if channel_id is None:
            return

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            events = await fetch_upcoming_events(limit=100, lookahead_days=SETTINGS.ctftime_lookahead_days)
        except Exception:
            return

        current_ids = {event.get("id") for event in events if event.get("id") is not None}

        if not self.notifier_bootstrapped:
            self.notifier_bootstrapped = True

            initial_events = events[: SETTINGS.ctftime_max_events_per_poll]
            initial_ids = [event.get("id") for event in initial_events if event.get("id") is not None]
            if initial_events:
                try:
                    for event in initial_events:
                        await self._send_event_embed(channel, event)
                    self.announced_event_ids.update(initial_ids)
                except discord.Forbidden:
                    if not self.notifier_permission_warning_sent:
                        print(
                            "CTFtime notifier cannot send message to target channel "
                            "(missing Send Messages/Embed Links permission)."
                        )
                        self.notifier_permission_warning_sent = True
                    return
                except Exception:
                    pass

            # Mark all current events as announced to avoid duplicate reposts.
            self.announced_event_ids.update(current_ids)
            return

        # Cuma ambil event baru yang belum pernah dipost, urutan sudah paling dekat dulu.
        new_events = [event for event in events if event.get("id") not in self.announced_event_ids]
        new_events = new_events[: SETTINGS.ctftime_max_events_per_poll]

        new_ids = [event.get("id") for event in new_events if event.get("id") is not None]
        if new_events:
            try:
                for event in new_events:
                    await self._send_event_embed(channel, event)
                self.announced_event_ids.update(new_ids)
            except discord.Forbidden:
                if not self.notifier_permission_warning_sent:
                    print(
                        "CTFtime notifier cannot send message to target channel "
                        "(missing Send Messages/Embed Links permission)."
                    )
                    self.notifier_permission_warning_sent = True
                return
            except Exception:
                pass

        self.announced_event_ids.intersection_update(current_ids)

    @ctftime_notifier.before_loop
    async def before_ctftime_notifier(self):
        await self.bot.wait_until_ready()

    # =================================================================
    # Other CTF-related commands can be added here, such as team info, find team, etc.
    # =================================================================
    @commands.hybrid_command(name="ping", description="Cek latency bot")
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Bot Status",
            description="Bot aktif dan siap dipakai.",
            color=0x00FF88,
        )
        embed.add_field(name="Latency", value=f"{latency} ms", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author}")
        embed.timestamp = discord.utils.utcnow()

        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="infoctf", description="Info tim CTF server ini")
    async def infoctf(self, ctx):
        guild = ctx.guild
        if guild is None:
            await ctx.reply("❌ Command ini hanya bisa dipakai di dalam server.")
            return

        embed = discord.Embed(
            title=f"🏆 {SETTINGS.team_name} - Team Info",
            description=SETTINGS.team_description,
            url=SETTINGS.team_url,
            color=0x00C2FF,
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(name="🏆 CTFtime", value=f"[Lihat Profil Tim]({SETTINGS.team_url})", inline=False)
        embed.add_field(name="💬 Contact", value=SETTINGS.team_contact, inline=False)
        embed.add_field(name="🖥 Server", value=guild.name, inline=True)
        embed.add_field(name="👥 Members", value=str(guild.member_count), inline=True)

        if SETTINGS.team_discord_invite:
            embed.add_field(name="🔗 Join Server", value=SETTINGS.team_discord_invite, inline=False)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.set_footer(text="Powered by CTFtime")

        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="findteam", description="Mencari tim untuk CTF")
    async def findteam(
        self,
        ctx,
        nama_ctf: str,
        team: str,
        invite: str,
        website: str,
        note: str = "No note",
    ):
        if ctx.guild is None:
            await ctx.reply("❌ Command ini hanya bisa dipakai di dalam server.")
            return

        role = ctx.guild.get_role(SETTINGS.ctf_role_id) if SETTINGS.ctf_role_id else None

        embed = discord.Embed(
            title=f"🚩 OPEN RECRUITMENT: {nama_ctf}",
            description="Cari member baru untuk push rank bareng. Detail rekrutmen ada di bawah.",
            color=0xFF4444,
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(name="👥 Team", value=f"**{team}**", inline=True)
        embed.add_field(name="🎯 Event", value=nama_ctf, inline=True)

        if invite.startswith("http"):
            embed.add_field(name="🔗 Join", value=invite, inline=False)
        else:
            embed.add_field(name="🔑 Invite Code", value=f"`{invite}`", inline=False)

        embed.add_field(name="🌐 Event URL", value=website, inline=False)
        embed.add_field(name="🏆 Team CTFtime", value=f"[Lihat Profil Tim]({SETTINGS.team_url})", inline=False)
        embed.add_field(name="📝 Catatan", value=note, inline=False)

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        mention_mode = SETTINGS.findteam_mention_mode
        mention_text = ""
        if mention_mode == "everyone":
            mention_text = "@everyone"
        elif mention_mode == "role" and role:
            mention_text = f"<@&{role.id}>"
        else:
            mention_mode = "none"

        if mention_mode == "everyone":
            embed.add_field(name="📣 Mention", value="Everyone", inline=True)
        elif mention_mode == "role" and role:
            embed.add_field(name="📣 Mention", value=f"Role: {role.name}", inline=True)
        else:
            embed.add_field(name="📣 Mention", value="No mention", inline=True)

        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(
            content=mention_text,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=True, roles=True),
        )

async def setup(bot):
    await bot.add_cog(CTFCog(bot))
