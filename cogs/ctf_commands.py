from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set

import discord
from discord.ext import commands, tasks

from config import SETTINGS
from services.ctftime import fetch_upcoming_events, format_discord_timestamp, parse_iso_datetime


@dataclass
class RecruitmentSession:
    guild_id: int
    channel_id: int
    message_id: int
    thread_id: Optional[int]
    nama_ctf: str
    team: str
    invite: str
    website: str
    note: str
    author_id: int
    expires_at: datetime
    claimed_user_ids: Set[int] = field(default_factory=set)


class ClaimRoleView(discord.ui.View):
    def __init__(self, cog: "CTFCog", message_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.message_id = message_id

    @discord.ui.button(label="Join / Leave Event", style=discord.ButtonStyle.primary)
    async def toggle_claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_claim_toggle(interaction, self.message_id)

# =================================================================
# Keep the main logic of CTF-related commands and CTFtime notifier here.
# =================================================================
class CTFCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.announced_event_ids = set()
        self.notifier_bootstrapped = False
        self.notifier_permission_warning_sent = False
        self.recruitment_sessions: Dict[int, RecruitmentSession] = {}

        if SETTINGS.ctftime_notify_channel_id:
            self.ctftime_notifier.change_interval(minutes=SETTINGS.ctftime_poll_minutes)
            self.ctftime_notifier.start()

        self.recruitment_cleanup.start()

    def cog_unload(self):
        if self.ctftime_notifier.is_running():
            self.ctftime_notifier.cancel()
        if self.recruitment_cleanup.is_running():
            self.recruitment_cleanup.cancel()

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _format_discord_time(self, dt: datetime) -> str:
        unix_ts = int(dt.timestamp())
        return f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"

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

    def _build_findteam_embed(
        self,
        session: RecruitmentSession,
        guild: discord.Guild,
        is_closed: bool,
    ) -> discord.Embed:
        status_text = "Closed" if is_closed else "Open"
        status_emoji = "🔒" if is_closed else "🟢"
        thread_text = f"<#{session.thread_id}>" if session.thread_id else "Belum dibuat"

        joined_mentions = []
        for user_id in sorted(session.claimed_user_ids):
            member = guild.get_member(user_id)
            if member is not None:
                joined_mentions.append(member.mention)

        claim_count = len(joined_mentions)
        if joined_mentions:
            preview = joined_mentions[:20]
            joined_text = ", ".join(preview)
            if len(joined_mentions) > len(preview):
                joined_text += f" +{len(joined_mentions) - len(preview)} lagi"
        else:
            joined_text = "Belum ada"

        embed = discord.Embed(
            title=f"🎯 Team Up CTF: {session.nama_ctf}",
            description="Cari squad untuk main CTF bareng. Klik tombol untuk join/leave event.",
            color=0x2ECC71 if not is_closed else 0x7F8C8D,
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="👥 Team", value=session.team, inline=True)
        embed.add_field(name="📌 Status", value=f"{status_emoji} {status_text}", inline=True)
        embed.add_field(name="🙋 Claimed", value=f"{claim_count} orang", inline=True)
        embed.add_field(name="✅ Joined", value=joined_text, inline=False)
        embed.add_field(name="🧵 Thread Event", value=thread_text, inline=False)
        embed.add_field(name="🕒 Ditutup", value=self._format_discord_time(session.expires_at), inline=False)

        if session.invite.startswith("http"):
            embed.add_field(name="🔗 Join", value=session.invite, inline=False)
        else:
            embed.add_field(name="🔑 Invite Code", value=session.invite, inline=False)

        embed.add_field(name="🌐 Event URL", value=session.website, inline=False)
        embed.add_field(name="🏆 Team CTFtime", value=f"[Lihat Profil Tim]({SETTINGS.team_url})", inline=False)
        embed.add_field(name="📝 Catatan", value=session.note, inline=False)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.set_footer(text=f"Requested by <@{session.author_id}>")
        return embed

    async def _refresh_recruitment_message(self, session: RecruitmentSession, is_closed: bool = False):
        guild = self.bot.get_guild(session.guild_id)
        if guild is None:
            return

        channel = guild.get_channel(session.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        embed = self._build_findteam_embed(session, guild, is_closed=is_closed)

        try:
            message = await channel.fetch_message(session.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

        if is_closed:
            await message.edit(embed=embed, view=None)
        else:
            await message.edit(embed=embed, view=ClaimRoleView(self, session.message_id))

    async def _close_recruitment_session(self, session: RecruitmentSession):
        guild = self.bot.get_guild(session.guild_id)
        if guild is None:
            self.recruitment_sessions.pop(session.message_id, None)
            return

        if session.thread_id is not None:
            thread = guild.get_thread(session.thread_id)
            if thread is None:
                try:
                    fetched = await guild.fetch_channel(session.thread_id)
                    if isinstance(fetched, discord.Thread):
                        thread = fetched
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    thread = None

            if isinstance(thread, discord.Thread):
                try:
                    await thread.send("Recruitment ditutup otomatis. Thread akan diarsipkan.")
                except (discord.Forbidden, discord.HTTPException):
                    pass
                try:
                    await thread.delete()
                except (discord.Forbidden, discord.HTTPException):
                    try:
                        await thread.edit(archived=True, locked=True)
                    except (discord.Forbidden, discord.HTTPException):
                        pass

        await self._refresh_recruitment_message(session, is_closed=True)
        self.recruitment_sessions.pop(session.message_id, None)

    async def handle_claim_toggle(self, interaction: discord.Interaction, message_id: int):
        if interaction.guild is None:
            await interaction.response.send_message("Command ini hanya bisa dipakai di server.", ephemeral=True)
            return

        session = self.recruitment_sessions.get(message_id)
        if session is None:
            await interaction.response.send_message("Recruitment ini sudah tidak aktif.", ephemeral=True)
            return

        if self._utc_now() >= session.expires_at:
            await self._close_recruitment_session(session)
            await interaction.response.send_message("Recruitment sudah ditutup.", ephemeral=True)
            return

        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message("Member tidak ditemukan di guild.", ephemeral=True)
            return

        if member.id in session.claimed_user_ids:
            session.claimed_user_ids.remove(member.id)
            text = "Kamu leave dari event ini."
        else:
            session.claimed_user_ids.add(member.id)
            text = "Kamu join ke event ini."

        await interaction.response.send_message(text, ephemeral=True)

        try:
            await self._refresh_recruitment_message(session, is_closed=False)
        except Exception:
            pass

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

    @tasks.loop(minutes=1)
    async def recruitment_cleanup(self):
        now = self._utc_now()
        expired_sessions = [session for session in self.recruitment_sessions.values() if now >= session.expires_at]
        for session in expired_sessions:
            await self._close_recruitment_session(session)

    @recruitment_cleanup.before_loop
    async def before_recruitment_cleanup(self):
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
        durasi_jam: int = 24,
    ):
        if ctx.guild is None:
            await ctx.reply("❌ Command ini hanya bisa dipakai di dalam server.")
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.reply("❌ Pakai command ini di channel text biasa, bukan thread/DM.")
            return

        durasi_jam = max(1, min(168, durasi_jam))
        expires_at = self._utc_now() + timedelta(hours=durasi_jam)

        role = ctx.guild.get_role(SETTINGS.ctf_role_id) if SETTINGS.ctf_role_id else None
        mention_mode = SETTINGS.findteam_mention_mode
        mention_text = ""
        if mention_mode == "everyone":
            mention_text = "@everyone"
        elif mention_mode == "role" and role:
            mention_text = f"<@&{role.id}>"
        else:
            mention_mode = "none"

        temp_session = RecruitmentSession(
            guild_id=ctx.guild.id,
            channel_id=ctx.channel.id,
            message_id=0,
            thread_id=None,
            nama_ctf=nama_ctf,
            team=team,
            invite=invite,
            website=website,
            note=note,
            author_id=ctx.author.id,
            expires_at=expires_at,
        )

        embed = self._build_findteam_embed(temp_session, ctx.guild, is_closed=False)

        try:
            message = await ctx.send(
                content=mention_text,
                embed=embed,
                view=ClaimRoleView(self, 0),
                allowed_mentions=discord.AllowedMentions(everyone=True, roles=True),
            )
        except discord.Forbidden:
            await ctx.reply("❌ Bot tidak punya izin kirim pesan atau attach view.")
            return
        except discord.HTTPException:
            await ctx.reply("❌ Gagal kirim pesan recruitment.")
            return

        session = RecruitmentSession(
            guild_id=ctx.guild.id,
            channel_id=ctx.channel.id,
            message_id=message.id,
            thread_id=None,
            nama_ctf=nama_ctf,
            team=team,
            invite=invite,
            website=website,
            note=note,
            author_id=ctx.author.id,
            expires_at=expires_at,
        )
        self.recruitment_sessions[message.id] = session

        try:
            await message.edit(view=ClaimRoleView(self, message.id))
        except Exception:
            pass

        thread_name = f"CTF {nama_ctf}"[:100]
        try:
            thread = await message.create_thread(name=thread_name, auto_archive_duration=10080)
            session.thread_id = thread.id
            await thread.send(
                f"Thread khusus event {nama_ctf}.\n"
                "Klik tombol Join / Leave Event di pesan utama buat daftar.\n"
                f"Event URL: {website}"
            )
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        try:
            await self._refresh_recruitment_message(session, is_closed=False)
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(CTFCog(bot))
