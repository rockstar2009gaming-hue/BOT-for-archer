import discord
from discord.ext import commands, tasks
import random
import json
import os
import asyncio
from flask import Flask
from threading import Thread

# ─── FLASK KEEP ALIVE ─────────────────────────
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=run).start()

# ─── CONFIG ───────────────────────────────────
TOKEN = os.environ.get("TOKEN")

FEEDBACK_CHANNEL_ID = 1461396837599543529
CONFIG_FILE = "config.json"

GUILD_ID = 1461388342968189116
VOUCH_CHANNEL_ID = 1461391779164323892

MIDDLEMAN_IDS = [
      1486574884439195690,
    1468675859480051928,
    1394312770194767922,
    1196708751827279964,
    1486574884439195690,
    1475744103454085140,
    1458045646115307623,
    1479405527795630181,
    1160512569455419402,
    1471819926191734938,
    1430531999243702345,
    1468675859480051928,
    1248260884090982411,
    1412441771249762466,
    1486342293173567500,
    1175361046760935476,
]

VOUCHES_FILE = "vouches.json"

# ─── EMBED COLOR (GREY BLUE) ──────────────────
EMBED_COLOR = 0x5865F2  # discord blurple

# ─── DATA SYSTEM ──────────────────────────────
def load_vouches():
    if os.path.exists(VOUCHES_FILE):
        try:
            with open(VOUCHES_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_vouches(data):
    with open(VOUCHES_FILE, "w") as f:
        json.dump(data, f, indent=2)

def add_vouch(user_id, voucher_id, reason):
    data = load_vouches()
    user_id = str(user_id)

    if user_id not in data:
        data[user_id] = {"count": 0, "log": []}

    data[user_id]["count"] += 1
    data[user_id]["log"].append({
        "by": voucher_id,
        "reason": reason or "No reason"
    })

    save_vouches(data)
    return data[user_id]["count"]

def get_vouches(user_id):
    data = load_vouches()
    return data.get(str(user_id), {}).get("count", 0)

# ─── CONFIG SAVE SYSTEM ───────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_vouch_role():
    return load_config().get("vouch_role")

def set_vouch_role(role_id):
    data = load_config()
    data["vouch_role"] = role_id
    save_config(data)

# ─── BOT SETUP ────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

# ─── AUTO VOUCH ───────────────────────────────
@tasks.loop(minutes=3)
async def auto_vouch():
    guild = bot.get_guild(GUILD_ID)
    channel = bot.get_channel(VOUCH_CHANNEL_ID)

    if not guild or not channel:
        return

    user_id = random.choice(MIDDLEMAN_IDS)

    try:
        member = await guild.fetch_member(user_id)
    except:
        return

    total = add_vouch(user_id, bot.user.id, "Auto vouch")

    embed = discord.Embed(
        title="⭐ Auto Vouch",
        color=EMBED_COLOR
    )
    embed.add_field(name="User", value=member.mention, inline=False)
    embed.add_field(name="Total Vouches", value=f"{total} (+1)", inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)

    await channel.send(embed=embed)

@auto_vouch.before_loop
async def before_auto():
    await bot.wait_until_ready()

# ─── EVENTS ───────────────────────────────────
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    auto_vouch.start()

# ─── COMMANDS ─────────────────────────────────

# ✅ SET VOUCH (FIXED PERMISSION)
@bot.command()
@commands.has_permissions(administrator=True)
async def setvouch(ctx, role: discord.Role = None):
    if not role:
        embed = discord.Embed(description="❌ Mention a role", color=EMBED_COLOR)
        return await ctx.send(embed=embed)

    set_vouch_role(role.id)

    embed = discord.Embed(
        description=f"✅ Vouch role set to {role.mention}",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)


# ✅ VOUCH
@bot.command()
async def vouch(ctx, member: discord.Member = None, *, reason=None):
    if not member:
        return await ctx.send(embed=discord.Embed(
            description="❌ Mention a user", color=EMBED_COLOR))

    role_id = get_vouch_role()
    role = ctx.guild.get_role(role_id) if role_id else None

    if not role or role not in member.roles:
        return await ctx.send(embed=discord.Embed(
            description="❌ User must have vouch role", color=EMBED_COLOR))

    total = add_vouch(member.id, ctx.author.id, reason)

    embed = discord.Embed(title="⭐ New Vouch!", color=EMBED_COLOR)
    embed.add_field(name="User", value=member.mention, inline=False)
    embed.add_field(name="Total", value=f"{total} (+1)", inline=True)

    embed.set_thumbnail(url=member.display_avatar.url)

    await ctx.send(embed=embed)

    feedback = bot.get_channel(FEEDBACK_CHANNEL_ID)
    if feedback:
        await feedback.send(embed=discord.Embed(
            description=f"📊 {member.mention} now has **{total} vouches**",
            color=EMBED_COLOR
        ))


# ✅ VOUCHES (NOW EMBED)
@bot.command()
async def vouches(ctx, member: discord.Member = None):
    member = member or ctx.author
    total = get_vouches(member.id)

    embed = discord.Embed(
        title="📊 Vouch Stats",
        description=f"{member.mention} has **{total} vouches**",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)


# ✅ HI
@bot.command()
async def hi(ctx):
    embed = discord.Embed(
        description=f"👋 Hello {ctx.author.mention}",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)


# ✅ DELETE
@bot.command()
async def delete(ctx):
    if not ctx.message.reference:
        return await ctx.send(embed=discord.Embed(
            description="❌ Reply to a bot message",
            color=EMBED_COLOR))

    msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)

    if msg.author == bot.user:
        await msg.delete()
        await ctx.message.delete()


# ─── ERROR HANDLER ────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    embed = discord.Embed(color=EMBED_COLOR)

    if isinstance(error, commands.MissingRequiredArgument):
        embed.description = "❌ Missing argument"
    elif isinstance(error, commands.MemberNotFound):
        embed.description = "❌ User not found"
    elif isinstance(error, commands.MissingPermissions):
        embed.description = "❌ You need administrator permission"

    await ctx.send(embed=embed)

# ─── RUN ─────────────────────────────────────
keep_alive()
bot.run(TOKEN)
