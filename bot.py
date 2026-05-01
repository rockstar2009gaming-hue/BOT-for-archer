from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

Thread(target=run_web).start()

import discord
from discord.ext import commands
import os
import sqlite3

TOKEN = os.getenv("TOKEN")


conn = sqlite3.connect("tickets.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY,
    claimed_by INTEGER,
    opened_by INTEGER
)
""")

conn.commit()


CATEGORY_ID = 1461407188567330917
MM_ROLE_ID = 1461400480352567317
TRANSCRIPT_CHANNEL_ID = 1461392288952357111

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- MODAL ----------
class TicketModal(discord.ui.Modal, title="Middleman Request"):
    other_user = discord.ui.TextInput(label="Other User ID", required=True)
    trade = discord.ui.TextInput(label="What is the trade?", style=discord.TextStyle.paragraph, required=True)
    value = discord.ui.TextInput(label="Trade Value", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user

        category = guild.get_channel(CATEGORY_ID)
        mm_role = guild.get_role(MM_ROLE_ID)

        # One ticket per user
        for ch in category.channels:
            if ch.name == f"mm-{user.name}".lower():
                await interaction.response.send_message("❌ You already have an open ticket.", ephemeral=True)
                return

        # Create channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            mm_role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=f"mm-{user.name}".lower(),
            category=category,
            overwrites=overwrites
        )
        # ✅ SAVE TICKET TO DATABASE
        cursor.execute(
            "INSERT INTO tickets (channel_id, claimed_by, opened_by) VALUES (?, ?, ?)",
            (channel.id, None, user.id)
        )
        conn.commit()

        # -------- USER TRACKING (ONLY ID WORKS) --------
        other_input = self.other_user.value.strip()
        mentioned_user = None

        if other_input.isdigit():
            try:
                mentioned_user = await guild.fetch_member(int(other_input))
            except:
                mentioned_user = None
        else:
            mentioned_user = None

        if not mentioned_user:
            await interaction.followup.send(
                "❌ Invalid user. Please enter a valid USER ID (not username).",
                ephemeral=True
            )
            return

        other_display = mentioned_user.mention
        # -------- MAIN EMBED --------
        embed = discord.Embed(
            title="👑 Middleman Ticket",
            description=f"Welcome {user.mention}, please wait for a middleman.",
            color=0x2b2d31
        )

        embed.add_field(name="Trade", value=self.trade.value, inline=False)
        embed.add_field(name="Trade Value", value=self.value.value, inline=False)
        embed.add_field(name="Other User", value=other_display, inline=False)

        embed.set_image(url="https://cdn.discordapp.com/attachments/1499704965021700116/1499705524885913670/file_00000000371871f4b1400c668285ac002.png?ex=69f5c51c&is=69f4739c&hm=4890800b4094b9f5bedb812326a33b304c9a796b43ed3f91dc0b1b27a2708fa2&")

        # -------- SEND --------
        await channel.send(f"<@&{MM_ROLE_ID}>")

        if mentioned_user:
            await channel.send(mentioned_user.mention)

        view = ControlView()

        view.opened_by = user
        view.opened_at = interaction.created_at

        await channel.send(embed=embed, view=view)

        # -------- USER FOUND (LIKE ELDORADO) --------
        if mentioned_user:
            user_embed = discord.Embed(
                title="✅ User Found",
                description=f"User {mentioned_user.mention} (ID: {mentioned_user.id}) was found.\n\nUse ➕ Add User button to add them.",
                color=0x2ecc71
            )
            user_embed.set_thumbnail(url=mentioned_user.display_avatar.url)

            await channel.send(embed=user_embed)

        # -------- RESPONSE --------
        
        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
    label="Open Ticket",
    style=discord.ButtonStyle.gray,
    emoji="<:emoji_47:1493014663879725087>"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())
# ---------- BUTTON ----------
class ControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.claimed_by = None
        self.opened_by = None
        self.claimed_at = None
        self.opened_at = None

    def is_mm(self, interaction: discord.Interaction):
        return any(role.id == MM_ROLE_ID for role in interaction.user.roles)

    # ✅ CLAIM

    @discord.ui.button(label="✅ Claim", style=discord.ButtonStyle.green)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        if not self.is_mm(interaction):
            await interaction.followup.send("❌ Only MM team can claim.", ephemeral=True)
            return

        # ✅ CHECK DATABASE
        cursor.execute(
            "SELECT claimed_by FROM tickets WHERE channel_id = ?",
            (interaction.channel.id,)
        )
        data = cursor.fetchone()

        if data and data[0]:
            user = await interaction.guild.fetch_member(data[0])
            await interaction.followup.send(
                f"❌ Already claimed by {user.mention}",
                ephemeral=True
            )
            return

        # ✅ SAVE CLAIM
        cursor.execute(
            "UPDATE tickets SET claimed_by = ? WHERE channel_id = ?",
            (interaction.user.id, interaction.channel.id)
        )
        conn.commit()

        mm_role = interaction.guild.get_role(MM_ROLE_ID)

        # 🔒 lock role
        await interaction.channel.set_permissions(mm_role, send_messages=False)
        await interaction.channel.set_permissions(interaction.user, send_messages=True)

        # 🔥 CREATE CLEAN VIEW
        new_view = ControlView()
        new_view.opened_by = self.opened_by
        new_view.opened_at = self.opened_at

        # 🎨 update button
        for item in new_view.children:
            if item.label == "✅ Claim":
                item.label = f"🔒 Claimed by {interaction.user.name}"
                item.style = discord.ButtonStyle.gray

        await interaction.message.edit(view=new_view)

        await interaction.channel.send(f"🔒 Ticket claimed by {interaction.user.mention}")


    # ✅ UNCLAIM
    @discord.ui.button(label="🔓 Unclaim", style=discord.ButtonStyle.gray)
    async def unclaim(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer()

        # ✅ CHECK DATABASE
        
        cursor.execute(
            "SELECT claimed_by FROM tickets WHERE channel_id = ?",
            (interaction.channel.id,)
        )
        data = cursor.fetchone()

        if not data or data[0] != interaction.user.id:
            await interaction.followup.send("❌ Not your ticket", ephemeral=True)
            return

        # ✅ REMOVE CLAIM
        cursor.execute(
            "UPDATE tickets SET claimed_by = NULL WHERE channel_id = ?",
            (interaction.channel.id,)
        )
        conn.commit()

        mm_role = interaction.guild.get_role(MM_ROLE_ID)

        # 🔓 restore perms
        await interaction.channel.set_permissions(mm_role, send_messages=True)

        # 🔄 reset view
        new_view = ControlView()
        new_view.opened_by = self.opened_by
        new_view.opened_at = self.opened_at

        await interaction.message.edit(view=new_view)

        await interaction.channel.send("🔓 Ticket unclaimed")

    # ✅ CLOSE
    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        closed_by = interaction.user
        closed_at = interaction.created_at

        embed = discord.Embed(title="📜 Ticket Summary", color=0x2b2d31)

        embed.add_field(name="Opened by", value=self.opened_by.mention if self.opened_by else "Unknown", inline=False)
        embed.add_field(name="Claimed by", value=self.claimed_by.mention if self.claimed_by else "Not claimed", inline=False)
        embed.add_field(name="Closed by", value=closed_by.mention, inline=False)

        embed.add_field(name="Opened at", value=f"<t:{int(self.opened_at.timestamp())}:F>" if self.opened_at else "Unknown", inline=False)
        embed.add_field(name="Closed at", value=f"<t:{int(closed_at.timestamp())}:F>", inline=False)

        log_channel = interaction.guild.get_channel(TRANSCRIPT_CHANNEL_ID)

        await interaction.response.send_message("📜 Ticket closed")

        await log_channel.send(embed=embed)
        await interaction.channel.delete()

    # ✅ ADD USER
    @discord.ui.button(label="➕ Add User", style=discord.ButtonStyle.blurple)
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message("Send user ID", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", check=check, timeout=30)
            user = await interaction.guild.fetch_member(int(msg.content))

            await interaction.channel.set_permissions(user, view_channel=True, send_messages=True)
            await interaction.channel.send(f"✅ {user.mention} added")

        except:
            await interaction.channel.send("❌ Failed to add user")
# ---------- PANEL ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def panel(ctx):

    text = (
        "🎮 Verified Middleman Service\n"
        "```\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "   REQUEST A MIDDLEMAN  ·  TRADE SAFELY\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "```\n"
        "> Trade with complete confidence. Our verified Middlemen ensure every deal is completed safely.\n\n"

        "**✦ How It Works**\n"
        "**1.** Agree on trade\n"
        "**2.** Click button below\n"
        "**3.** Submit details\n"
        "**4.** MM handles trade\n"
        "**5.** Trade completed safely\n\n"


        "```\n"
        "⚠ ONLY USE VERIFIED MIDDLEMAN ⚠\n"
        "```"
    )

    embed = discord.Embed(description=text, color=0x2b2d31)

    embed.set_image(
        url="https://cdn.discordapp.com/attachments/1499704965021700116/1499705524885913670/file_00000000371871f4b1400c668285ac002.png?ex=69f5c51c&is=69f4739c&hm=4890800b4094b9f5bedb812326a33b304c9a796b43ed3f91dc0b1b27a2708fa2&"
    )
    await ctx.send(embed=embed, view=TicketView())

# ---------- transfer ----------
@bot.command()
async def transfer(ctx, new_mm: discord.Member):

    # ✅ must be MM
    if not any(role.id == MM_ROLE_ID for role in ctx.author.roles):
        await ctx.send("❌ Only MM team can transfer tickets.")
        return

    # ✅ check DB
    cursor.execute(
        "SELECT claimed_by FROM tickets WHERE channel_id = ?",
        (ctx.channel.id,)
    )
    data = cursor.fetchone()

    if not data or data[0] != ctx.author.id:
        await ctx.send("❌ You are not the current claimer.")
        return

    # ✅ target must be MM
    if not any(role.id == MM_ROLE_ID for role in new_mm.roles):
        await ctx.send("❌ Target user is not a MM.")
        return

    # ✅ update DB
    cursor.execute(
        "UPDATE tickets SET claimed_by = ? WHERE channel_id = ?",
        (new_mm.id, ctx.channel.id)
    )
    conn.commit()

    mm_role = ctx.guild.get_role(MM_ROLE_ID)

    # 🔒 lock all MMs
    await ctx.channel.set_permissions(mm_role, send_messages=False)

    # ✅ allow new MM
    await ctx.channel.set_permissions(new_mm, send_messages=True)

    # 🔄 update button UI
    view = ControlView()

    for item in view.children:
        if item.label == "✅ Claim":
            item.label = f"🔒 Claimed by {new_mm.name}"
            item.style = discord.ButtonStyle.gray

    await ctx.send(view=view)

    # ✅ message visible to everyone
    await ctx.send(f"🔄 Ticket transferred to {new_mm.mention} by {ctx.author.mention}")

# ---------- announce ---------
@bot.command()
@commands.has_permissions(administrator=True)
async def announce(ctx, channel: discord.TextChannel, *, message):

    embed = discord.Embed(
        description=message,
        color=0x2b2d31
    )

    embed.set_author(name="📢 Announcement", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

    await channel.send(embed=embed)

    await ctx.send("✅ Announcement sent")


@bot.command()
@commands.has_permissions(administrator=True)
async def dm(ctx, user: discord.Member, *, message):

    try:
        await user.send(message)
        await ctx.send(f"✅ Sent DM to {user}")
    except:
        await ctx.send("❌ Couldn't DM user")



@bot.command()
@commands.has_permissions(administrator=True)
async def dmrole(ctx, role: discord.Role, *, message):

    sent = 0
    failed = 0

    for member in role.members:
        try:
            await member.send(message)
            sent += 1
        except:
            failed += 1

    await ctx.send(f"✅ Sent: {sent} | ❌ Failed: {failed}")






# ---------- READY ----------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    
    bot.add_view(TicketView())
    bot.add_view(ControlView())


bot.run(TOKEN)
