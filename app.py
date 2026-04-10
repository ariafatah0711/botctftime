import discord
from discord.ext import commands
import whois

TEAM_URL = "https://ctftime.org/team/414817"

CTF_ROLE_ID = 1461904837842174106

class Commands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # =========================
    # HELP
    # =========================

    @commands.hybrid_command(name="help", description="Daftar command bot")
    async def help(self, ctx):

        embed = discord.Embed(
            title="📚 KTCG Bot Commands",
            description="Gunakan command berikut:",
            color=0x00ff88
        )

        embed.add_field(name="🏓 ping", value="Cek apakah bot aktif\n`/ping`", inline=False)
        embed.add_field(name="🖥 infoserver", value="Informasi server\n`/infoserver`", inline=False)
        embed.add_field(name="🏆 ctftime", value="Profil tim KTCG di CTFtime\n`/ctftime`", inline=False)
        embed.add_field(name="📚 belajar", value="Platform belajar CTF\n`/belajar`", inline=False)
        embed.add_field(name="🌐 whois", value="Lookup domain\n`/whois google.com`", inline=False)
        embed.add_field(name="🧩 kategori", value="Kategori dalam CTF\n`/kategori`", inline=False)
        embed.add_field(name="🚩 findteam", value="Mencari member untuk CTF\n`/findteam`", inline=False)

        embed.set_footer(text="KTCG Cyber Security Community")

        await ctx.reply(embed=embed)

    # =========================
    # PING
    # =========================

    @commands.hybrid_command(name="ping", description="Cek latency bot")
    async def ping(self, ctx):

        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: **{latency} ms**",
            color=0x00ff88
        )

        await ctx.reply(embed=embed)

    # =========================
    # SERVER INFO
    # =========================

    @commands.hybrid_command(name="infoserver", description="Informasi server")
    async def infoserver(self, ctx):

        guild = ctx.guild
        if guild is None:
            await ctx.reply("❌ Command ini hanya bisa dipakai di dalam server.")
            return

        embed = discord.Embed(
            title=f"🖥 Server Info - {guild.name}",
            description=(
                "Server ini dibuat untuk komunitas **CTF, Cyber Security, dan pembelajaran keamanan siber**.\n"
                "Silakan berdiskusi, belajar bersama.\n\n"
                "**Jangan melanggar rules server.**"
            ),
            color=0x00ff88
        )

        embed.add_field(name="👑 Owner", value=guild.owner, inline=False)
        embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
        embed.add_field(name="📅 Created", value=guild.created_at.strftime("%d %B %Y"), inline=True)
        embed.add_field(name="📚 Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="🚀 Boost Level", value=guild.premium_tier, inline=True)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.set_footer(text="KTCG Cyber Security Community")

        await ctx.reply(embed=embed)

    # =========================
    # CTFTIME
    # =========================

    @commands.hybrid_command(name="ctftime", description="Profil tim KTCG di CTFtime")
    async def ctftime(self, ctx):

        embed = discord.Embed(
            title="🏆 KTCG CTFtime Team",
            description="Lihat profil dan ranking tim **KTCG** di CTFtime.",
            url=TEAM_URL,
            color=0x00ff88
        )

        embed.add_field(
            name="🔗 Team Page",
            value=f"[Open Team Page]({TEAM_URL})",
            inline=False
        )

        embed.set_footer(text="Source: ctftime.org")

        await ctx.reply(embed=embed)

    # =========================
    # BELAJAR
    # =========================

    @commands.hybrid_command(name="belajar", description="Platform belajar CTF")
    async def belajar(self, ctx):

        embed = discord.Embed(
            title="📚 CTF Learning Hub",
            description="Platform untuk belajar CTF & Cyber Security",
            color=0x00ff88
        )

        embed.add_field(
            name="🇮🇩 Indonesia",
            value="[FGTE](https://ctf.ariaf.my.id) | [CyberAcademy](https://cyberacademy.id) | [PERSEUS](https://ctf.kamsib.id)",
            inline=False
        )

        embed.add_field(
            name="🌍 Global",
            value=(
                "[picoCTF](https://picoctf.org) | "
                "[HackTheBox](https://hackthebox.com) | "
                "[TryHackMe](https://tryhackme.com)\n"
                "[OverTheWire](https://overthewire.org) | "
                "[PortSwigger](https://portswigger.net/web-security)"
            ),
            inline=False
        )

        embed.set_footer(text="KTCG Cyber Security Community")

        await ctx.reply(embed=embed)

    # =========================
    # WHOIS
    # =========================

    @commands.hybrid_command(name="whois", description="Lookup domain")
    async def whois_lookup(self, ctx, domain: str):

        try:
            data = whois.whois(domain)

            name_servers = data.name_servers
            if isinstance(name_servers, list):
                name_servers = ", ".join(name_servers)

            embed = discord.Embed(
                title="🌐 WHOIS Lookup",
                description=f"Domain: **{domain}**",
                color=0x00ff88
            )

            embed.add_field(name="Registrar", value=data.registrar or "Unknown", inline=False)
            embed.add_field(name="Created", value=str(data.creation_date), inline=False)
            embed.add_field(name="Expires", value=str(data.expiration_date), inline=False)
            embed.add_field(name="Name Servers", value=name_servers or "Unknown", inline=False)

            await ctx.reply(embed=embed)

        except Exception:
            await ctx.reply("❌ Whois lookup gagal. Pastikan domain valid.")

    # =========================
    # KATEGORI CTF
    # =========================

    @commands.hybrid_command(name="kategori", description="Kategori dalam CTF")
    async def kategori(self, ctx):

        embed = discord.Embed(
            title="🧩 Kategori CTF",
            description="Kategori umum dalam CTF:",
            color=0x00ff88
        )

        embed.add_field(name="🌐 Web Exploitation", value="SQLi, XSS, SSRF", inline=False)
        embed.add_field(name="💻 Pwn", value="Binary exploitation", inline=False)
        embed.add_field(name="🔍 Reverse Engineering", value="Analisis binary", inline=False)
        embed.add_field(name="🔐 Cryptography", value="Kriptografi", inline=False)
        embed.add_field(name="📁 Forensics", value="File / memory analysis", inline=False)
        embed.add_field(name="🕵️ OSINT", value="Open Source Intelligence", inline=False)

        embed.set_footer(text="KTCG Cyber Security Community")

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

        role = ctx.guild.get_role(CTF_ROLE_ID)

        embed = discord.Embed(
            title=f"🚩 {nama_ctf}",
            description="Team recruitment untuk CTF",
            color=0xff4444
        )

        embed.add_field(name="👥 Team", value=team, inline=False)

        if invite.startswith("http"):
            embed.add_field(name="🔗 Invite URL", value=invite, inline=False)
        else:
            embed.add_field(name="🔑 Invite Code", value=invite, inline=False)

        embed.add_field(name="🌐 Website", value=website, inline=False)
        embed.add_field(name="📝 Note", value=note, inline=False)

        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.display_avatar.url
        )

        if role:
            mention = f"<@&{role.id}>"
        else:
            mention = ""

        await ctx.send(
            content=mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )


# =========================
# LOAD COG
# =========================

async def setup(bot):
    await bot.add_cog(Commands(bot))
