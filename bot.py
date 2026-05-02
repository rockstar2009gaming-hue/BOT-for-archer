from flask import Flask
from threading import Thread

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

import discord
from discord.ext import commands, tasks
import random
import json
import os
import asyncio

# ─── CONFIG ─────────────────────────────────────────────
TOKEN = os.environ.get("TOKEN")

GUILD_ID = 1461388342968189116
VOUCH_CHANNEL_ID = 1461391779164323892
VOUCH_ROLE_ID = 1461400480352567317

MIDDLEMAN_IDS = [
    1486574884439195690,
    1468675859480051928,
    1394312770194767922,
]

VOUCHES_FILE = "vouches.json"

# ─── DATA SYSTEM ────────────────────────────────────────
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

# ─── BOT SETUP ──────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

# ─── AUTO VOUCH ─────────────────────────────────────────
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

# ─── EVENTS ─────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    auto_vouch.start()

# ─── COMMANDS ───────────────────────────────────────────

@bot.command()
async def vouch(ctx, member: discord.Member = None, *, reason=None):
    if not member:
        return await ctx.send("❌ Mention a user")

    role = ctx.guild.get_role(VOUCH_ROLE_ID)

    if role not in member.roles:
        return await ctx.send("❌ User must have vouch role")

    total = add_vouch(member.id, ctx.author.id, reason)

    embed = discord.Embed(title="✅ Vouch Added", color=discord.Color.green())
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="By", value=ctx.author.mention)
    embed.add_field(name="Total", value=total)

    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)

    await ctx.send(embed=embed)


@bot.command()
async def vouches(ctx, member: discord.Member = None):
    member = member or ctx.author
    total = get_vouches(member.id)

    await ctx.send(f"📊 {member.mention} has **{total}** vouches")


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


# ─── DM ROLE SYSTEM ─────────────────────────────────────
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


# ─── ERROR HANDLER ──────────────────────────────────────
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ User not found")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing argument")

# ─── RUN ────────────────────────────────────────────────
keep_alive()
bot.run(TOKEN)
