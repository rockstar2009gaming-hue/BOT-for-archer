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
    t = Thread(target=run)
    t.start()

# ─── CONFIG ───────────────────────────────────
TOKEN = os.environ.get("TOKEN")

FEEDBACK_CHANNEL_ID = 1461396837599543529
ADMIN_ROLE_ID = 1461388680076722176
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
        title="✅ Auto Vouch",
        description=f"{member.mention} got auto-vouched!",
        color=discord.Color.green()
    )
    embed.add_field(name="Total", value=total)

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

@bot.command()
async def setvouch(ctx, role: discord.Role = None):
    if not role:
        return await ctx.send("❌ Mention a role")

    if ADMIN_ROLE_ID not in [r.id for r in ctx.author.roles]:
        return await ctx.send("❌ No permission")

    set_vouch_role(role.id)
    await ctx.send(f"✅ Vouch role set to {role.mention}")


@bot.command()
async def vouch(ctx, member: discord.Member = None, *, reason=None):
    if not member:
        return await ctx.send("❌ Mention a user")

    role_id = get_vouch_role()
    role = ctx.guild.get_role(role_id) if role_id else None

    if not role or role not in member.roles:
        return await ctx.send("❌ User must have vouch role")

    total = add_vouch(member.id, ctx.author.id, reason)

    if total >= 200:
        rank = "🏆 Elite Middleman"
    elif total >= 100:
        rank = "💎 Trusted Middleman"
    elif total >= 50:
        rank = "⭐ Verified"
    else:
        rank = "🔰 Beginner"

    embed = discord.Embed(title="⭐ New Vouch!", color=discord.Color.gold())
    embed.add_field(name="Vouched User", value=member.mention, inline=False)
    embed.add_field(name="Total Vouches", value=f"{total} (+1)", inline=True)
    embed.add_field(name="Current Rank", value=rank, inline=True)

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=ctx.guild.name)

    await ctx.send(embed=embed)

    feedback = bot.get_channel(FEEDBACK_CHANNEL_ID)
    if feedback:
        await feedback.send(f"📊 {member.mention} now has **{total} vouches**")


@bot.command()
async def vouches(ctx, member: discord.Member = None):
    member = member or ctx.author
    total = get_vouches(member.id)
    await ctx.send(f"📊 {member.mention} has **{total} vouches**")


@bot.command()
async def hi(ctx):
    await ctx.send(f"👋 Hello {ctx.author.mention}")


@bot.command()
async def delete(ctx):
    if not ctx.message.reference:
        return await ctx.send("❌ Reply to a bot message")

    msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)

    if msg.author == bot.user:
        await msg.delete()
        await ctx.message.delete()


# ─── DM SYSTEM ────────────────────────────────
class ConfirmView(discord.ui.View):
    def __init__(self, role, message, author):
        super().__init__(timeout=30)
        self.role = role
        self.message = message
        self.author = author

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction, button):
        if interaction.user != self.author:
            return await interaction.response.send_message("Not yours", ephemeral=True)

        await interaction.response.send_message("Sending...")

        for m in self.role.members:
            if m.bot:
                continue
            try:
                await m.send(self.message)
                await asyncio.sleep(0.3)
            except:
                pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction, button):
        await interaction.response.send_message("Cancelled")

@bot.command()
async def dm(ctx, role: discord.Role = None, *, message=None):
    if not role or not message:
        return await ctx.send("Usage: .dm @role message")

    view = ConfirmView(role, message, ctx.author)
    await ctx.send(f"Send DM to {len(role.members)} users?", view=view)

# ─── ERROR HANDLER ────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ User not found")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing argument")

# ─── RUN ─────────────────────────────────────
keep_alive()
bot.run(TOKEN)
