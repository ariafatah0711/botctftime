import os
import discord
from discord.ext import commands

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

# =========================
# BOT SETUP
# =========================
class Commands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

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
