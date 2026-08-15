import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
from dotenv import load_dotenv
from database import Top10Database, ShardDatabase
from poster_generator import Top10Poster
from skill_guide import SKILL_GUIDE, get_skill_guide, get_position_options
import threading
from flask import Flask
import json
import asyncio
import aiohttp
import sqlite3
import base64
import io

# --- Flask Web Server (for Render health checks) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "FELIX PR is Online! 🏆"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- Self-Ping System ---
async def self_ping():
    await bot.wait_until_ready()
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not RENDER_URL:
        print("⚠️ RENDER_EXTERNAL_URL not set.")
        return
    while not bot.is_closed():
        await asyncio.sleep(840)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(RENDER_URL) as response:
                    if response.status == 200:
                        print(f"🔄 Self-ping OK at {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"⚠️ Self-ping failed: {e}")

# --- Discord Bot Setup ---
load_dotenv()

BOT_OWNER_ID = 1214456066687893506
CO_OWNER_ID = 553418145063239684
CONFIG_FILE = "bot_config.json"

maintenance_mode = False

class BotConfig:
    def __init__(self):
        self.data = self.load()
    def load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        return {}
    def save(self):
        with open(CONFIG_FILE, 'w') as f: json.dump(self.data, f)

config = BotConfig()
top10_db = Top10Database()
poster_gen = Top10Poster()
shard_db = ShardDatabase()

def maintenance_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if maintenance_mode and not is_bot_owner(interaction.user.id) and not is_co_owner(interaction.user.id):
            await interaction.response.send_message(
                "🔧 **Bot is under maintenance now, please wait.**\n\n"
                "The bot owner is currently making updates.\n"
                "Try again in a few minutes!",
                ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)

class ShardGuideView(discord.ui.View):
    def __init__(self, players: list, week: int, filters_text: str = "", page: int = 0):
        super().__init__(timeout=120)
        self.players = players
        self.week = week
        self.filters_text = filters_text
        self.page = page
        self.total_pages = len(players)
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        prev_btn = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.secondary, 
                                     disabled=(self.page == 0))
        prev_btn.callback = self.prev_callback
        self.add_item(prev_btn)
        
        page_btn = discord.ui.Button(label=f"{self.page + 1}/{self.total_pages}", 
                                     style=discord.ButtonStyle.primary, disabled=True)
        self.add_item(page_btn)
        
        next_btn = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.secondary,
                                     disabled=(self.page + 1 >= self.total_pages))
        next_btn.callback = self.next_callback
        self.add_item(next_btn)
    
    async def prev_callback(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_buttons()
        embed, file = self.get_player_embed()
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_callback(self, interaction: discord.Interaction):
        self.page += 1
        self.update_buttons()
        embed, file = self.get_player_embed()
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)
    
    def get_player_embed(self):
        p = self.players[self.page]
        color = TIER_COLOR.get(p['value_tier'], 0x3498db)
        emoji = TIER_EMOJI.get(p['value_tier'], "")
        
        embed = discord.Embed(
            title=f"{emoji} {p['player_name']}",
            description=f"**OVR:** {p['ovr']}\n**Cost:** `{p['shard_cost']}` shards\n"
                         f"**Tier:** {emoji} `{p['value_tier']}`\n"
                         f"**Week:** {self.week}\n\n"
                         f"Player {self.page + 1} of {self.total_pages}",
            color=color
        )
        embed.set_footer(text=f"FELIX PR | Player ID: {p['id']} • Use /shard_remove player_id:{p['id']} to remove")
        
        file = None
        if p.get('image_data'):
            try:
                img_bytes = base64.b64decode(p['image_data'])
                file = discord.File(io.BytesIO(img_bytes), filename=f"shard_{p['id']}.png")
                embed.set_image(url=f"attachment://shard_{p['id']}.png")
            except:
                pass
        
        return embed, file


class FCMReviewBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True; intents.members = True
        super().__init__(command_prefix='!', intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced commands for {self.user}")

bot = FCMReviewBot()

def is_bot_owner(uid: int) -> bool: return uid == BOT_OWNER_ID
def is_co_owner(uid: int) -> bool: return uid == CO_OWNER_ID
def is_admin(uid: int) -> bool: return is_bot_owner(uid) or is_co_owner(uid)
def can_edit_top10(uid: int) -> bool: return is_admin(uid)

TIER_EMOJI = {"S": "🌟", "A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴"}
TIER_COLOR = {"S": 0xFFD700, "A": 0x2ecc71, "B": 0xF1C40F, "C": 0xE67E22, "D": 0xE74C3C}

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'🏆 Top 10: Active (4+4+4 DB Split)')
    print(f'💎 Shard Guide: Active (Week + Multi-Filter)')
    print(f'🎯 Skill Point Guide: Active')
    print(f'🔧 Maintenance Mode: {"🟢 ON" if maintenance_mode else "🟢 OFF"}')
    print(f'👑 Admins: {BOT_OWNER_ID}, {CO_OWNER_ID}')
    bot.loop.create_task(self_ping())

# =============================================
# === MAINTENANCE COMMAND ===
# =============================================

@bot.tree.command(name="maintenance", description="Toggle maintenance mode (Admin Only)")
@app_commands.describe(status="ON or OFF")
@app_commands.choices(status=[
    app_commands.Choice(name="ON - Lock bot for everyone else", value="on"),
    app_commands.Choice(name="OFF - Unlock bot", value="off"),
])
async def maintenance_cmd(interaction: discord.Interaction, status: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    
    global maintenance_mode
    maintenance_mode = (status == "on")
    
    embed = discord.Embed(
        title=f"🔧 Maintenance Mode: {'🟢 ON' if maintenance_mode else '🟢 OFF'}",
        description="Only admins can use commands when maintenance is ON." if maintenance_mode else "All users can use commands now.",
        color=0xF59E0B if maintenance_mode else 0x2ecc71
    )
    embed.set_footer(text="FELIX PR")
    await interaction.response.send_message(embed=embed)

# =============================================
# === SKILL POINT GUIDE COMMAND ===
# =============================================

@bot.tree.command(name="skill_guide", description="Get skill point recommendations for your player")
@maintenance_check()
@app_commands.describe(
    position="Position of your player",
    playstyle="Your player's current skill point or workrate"
)
@app_commands.choices(position=[
    app_commands.Choice(name="LW - Left Winger", value="LW"),
    app_commands.Choice(name="RW - Right Winger", value="RW"),
    app_commands.Choice(name="ST - Striker", value="ST"),
    app_commands.Choice(name="LM - Left Midfielder", value="LM"),
    app_commands.Choice(name="RM - Right Midfielder", value="RM"),
    app_commands.Choice(name="CAM - Attacking Midfielder", value="CAM"),
    app_commands.Choice(name="CDM - Defensive Midfielder", value="CDM"),
    app_commands.Choice(name="CM - Central Midfielder", value="CM"),
    app_commands.Choice(name="CB - Centre Back", value="CB"),
    app_commands.Choice(name="LB - Left Back", value="LB"),
    app_commands.Choice(name="RB - Right Back", value="RB"),
    app_commands.Choice(name="GK - Goalkeeper", value="GK"),
])
async def skill_guide_cmd(interaction: discord.Interaction, position: str, playstyle: str):
    await interaction.response.defer()
    
    guide = get_skill_guide(position, playstyle)
    
    if not guide:
        await interaction.followup.send(embed=discord.Embed(
            title="❌ No Skill Guide Found",
            description=f"No recommendations available for **{position}** with playstyle **{playstyle}**.\n\n"
                         "Try different playstyle or position!",
            color=0xE74C3C).set_footer(text="FELIX PR"))
        return
    
    embed = discord.Embed(
        title=f"🎯 Skill Point Guide - {position}",
        description=f"**Your Playstyle:** {guide['skill_name']}",
        color=0x8B5CF6
    )
    
    for i, skill in enumerate(guide["recommendations"], 1):
        embed.add_field(
            name=f"{i}. {skill}",
            value="✅ Recommended",
            inline=False
        )
    
    embed.add_field(
        name="📝 Note",
        value=guide.get("note", "Recommended skill point combination"),
        inline=False
    )
    
    embed.set_footer(text="FELIX PR | Skill Point Guide")
    
    await interaction.followup.send(embed=embed)

# =============================================
# === ANNOUNCE TOP 10 COMMAND ===
# =============================================

@bot.tree.command(name="announce_top10", description="Announce Top 10 update in a channel (Admin Only)")
@app_commands.describe(channel="Channel to send the announcement to")
async def announce_top10(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(
        title="🏆 **Top 10 List Updated!**",
        description=(
            "Hey <@&1391671055902572625>! The **Top 10 Players** list has been refreshed! 📊\n\n"
            "## 📋 **Updated Positions:**\n"
            "✅ All 12 positions have been updated:\n"
            "`GK` `LB` `RB` `CB` `CM` `CDM` `CAM` `LM` `RM` `LW` `RW` `ST`\n\n"
            "## 🔍 **Check it out:**\n"
            "```\n/top10 [position]\n```\n"
            "New Update on Top 10 lists: All P2W cards removed i.e, no more box cards in any lists.\n\n"
            "## 📅 **Next Update:**\n"
            "Next Saturday or Sunday or Monday, before 10 PM IST\n\n"
            "Thanks to the <@&1484603567057666219> for their work on the lists! 👏\n\n"
            "Stay updated on the meta! ⚽"
        ),
        color=0xF5A623
    )
    embed.set_footer(text="FELIX PR | Top 10 Announcement")
    
    try:
        await channel.send(embed=embed)
        await interaction.followup.send(f"✅ Announcement sent to {channel.mention}!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to send: {e}", ephemeral=True)

# =============================================
# === SHARD GUIDE COMMANDS ===
# =============================================

@bot.tree.command(name="shard_add", description="Add player to Shard Value Guide (Admin Only)")
@maintenance_check()
@app_commands.describe(
    player_name="Player name",
    ovr="Player OVR (e.g., 117)",
    shard_cost="Shard cost",
    value_tier="Value rating tier",
    week="Week number (e.g., 1, 2, 3...)",
    image="Player card image"
)
@app_commands.choices(value_tier=[
    app_commands.Choice(name="🌟 S Tier - MUST BUY", value="S"),
    app_commands.Choice(name="🟢 A Tier - Great Value", value="A"),
    app_commands.Choice(name="🟡 B Tier - Good", value="B"),
    app_commands.Choice(name="🟠 C Tier - Decent", value="C"),
    app_commands.Choice(name="🔴 D Tier - Skip", value="D"),
])
async def shard_add(interaction: discord.Interaction, player_name: str, ovr: str,
    shard_cost: int, value_tier: str, week: int, image: discord.Attachment):
    
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    
    await interaction.response.defer(ephemeral=True)
    
    if shard_db.add_player(player_name, ovr, shard_cost, value_tier, week, image.url, interaction.user.name):
        emoji = TIER_EMOJI.get(value_tier, "")
        await interaction.followup.send(
            f"✅ **{player_name}** ({ovr} OVR) added to Shard Guide Week {week}!\n"
            f"Cost: `{shard_cost}` shards | Tier: {emoji} `{value_tier}`",
            ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed to add player!", ephemeral=True)

@bot.tree.command(name="shard_guide", description="View Shard Guide with multiple optional filters")
@maintenance_check()
@app_commands.describe(
    week="Week number to view",
    max_shards="Optional: Max shard cost",
    value_tier="Optional: Filter by tier",
    player_name="Optional: Search by player name"
)
@app_commands.choices(value_tier=[
    app_commands.Choice(name="🌟 S Tier", value="S"),
    app_commands.Choice(name="🟢 A Tier", value="A"),
    app_commands.Choice(name="🟡 B Tier", value="B"),
    app_commands.Choice(name="🟠 C Tier", value="C"),
    app_commands.Choice(name="🔴 D Tier", value="D"),
])
async def shard_guide(interaction: discord.Interaction, week: int, 
    max_shards: int = None, value_tier: str = None, player_name: str = None):
    await interaction.response.defer()
    
    players = shard_db.get_players_by_week(week)
    if not players:
        weeks = shard_db.get_all_weeks()
        week_list = ", ".join([f"`{w}`" for w in weeks]) if weeks else "None"
        await interaction.followup.send(embed=discord.Embed(
            title=f"💎 Shard Value Guide - Week {week}",
            description=f"No players for Week {week}.\n\nAvailable weeks: {week_list}",
            color=0x3498db).set_footer(text="FELIX PR"))
        return
    
    total_in_week = len(players)
    active_filters = []
    
    if value_tier:
        players = [p for p in players if p['value_tier'] == value_tier]
        active_filters.append(f"Tier: {TIER_EMOJI.get(value_tier, '')} `{value_tier}`")
        if not players:
            await interaction.followup.send(embed=discord.Embed(
                title=f"💎 Shard Value Guide - Week {week}",
                description=f"❌ No `{value_tier}`-Tier players in Week {week}.\nTry a different tier!",
                color=0xE74C3C).set_footer(text="FELIX PR"))
            return
    
    if player_name:
        players = [p for p in players if player_name.lower() in p['player_name'].lower()]
        active_filters.append(f"Name: `{player_name}`")
        if not players:
            await interaction.followup.send(embed=discord.Embed(
                title=f"💎 Shard Value Guide - Week {week}",
                description=f"❌ No players matching **{player_name}** in Week {week}.\nTry a different name!",
                color=0xE74C3C).set_footer(text="FELIX PR"))
            return
    
    if max_shards is not None:
        players = [p for p in players if p['shard_cost'] <= max_shards]
        active_filters.append(f"≤{max_shards} shards")
        if not players:
            min_cost = min(p['shard_cost'] for p in shard_db.get_players_by_week(week))
            await interaction.followup.send(embed=discord.Embed(
                title=f"💎 Shard Value Guide - Week {week}",
                description=f"❌ No players within `{max_shards}` shards.\n\n"
                             f"The cheapest player this week costs `{min_cost}` shards.",
                color=0xE74C3C).set_footer(text="FELIX PR | Try a higher limit"))
            return
    
    title = f"💎 Shard Value Guide - Week {week}"
    if active_filters:
        title += f" ({', '.join(active_filters)})"
    
    header_desc = f"**{len(players)}/{total_in_week} players** shown\n"
    if active_filters:
        header_desc += f"Filters: {', '.join(active_filters)}\n"
    header_desc += "🌟 S | 🟢 A | 🟡 B | 🟠 C | 🔴 D\n"
    header_desc += "━━━━━━━━━━━━━━━━━━━━━━━━"
    
    header = discord.Embed(title=title, description=header_desc, color=0x3498db)
    header.set_footer(text="FELIX PR | Shard Guide • Player IDs shown on each card")
    await interaction.followup.send(embed=header)
    
    filters_text = ", ".join(active_filters) if active_filters else ""
    view = ShardGuideView(players, week, filters_text)
    embed, file = view.get_player_embed()
    
    if file:
        await interaction.channel.send(embed=embed, file=file, view=view)
    else:
        await interaction.channel.send(embed=embed, view=view)

@bot.tree.command(name="shard_weeks", description="List all available Shard Guide weeks")
@maintenance_check()
async def shard_weeks(interaction: discord.Interaction):
    weeks = shard_db.get_all_weeks()
    if not weeks:
        await interaction.response.send_message("No shard guide weeks found!", ephemeral=True)
        return
    
    text = "**📅 Available Shard Guide Weeks:**\n"
    for w in weeks:
        count = shard_db.get_count(w)
        min_cost = min(p['shard_cost'] for p in shard_db.get_players_by_week(w)) if count > 0 else 0
        text += f"• Week `{w}` - {count} players (from `{min_cost}` shards)\n"
    text += "\nUse `/shard_guide week:<number>` to view!\n"
    text += "Add filters: `max_shards:` `value_tier:` `player_name:`"
    
    await interaction.response.send_message(text, ephemeral=True)

@bot.tree.command(name="shard_remove", description="Remove player from Shard Guide (Admin Only)")
@maintenance_check()
@app_commands.describe(player_id="ID of player to remove (shown on each card)")
async def shard_remove(interaction: discord.Interaction, player_id: int):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    
    if shard_db.remove_player(player_id):
        await interaction.response.send_message(f"✅ Removed player `{player_id}` from Shard Guide!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No player with ID `{player_id}`!", ephemeral=True)

@bot.tree.command(name="shard_reset_week", description="Delete all players from a specific week (Admin Only)")
@maintenance_check()
@app_commands.describe(week="Week number to reset")
async def shard_reset_week(interaction: discord.Interaction, week: int):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    
    await interaction.response.defer(ephemeral=True)
    
    count = shard_db.remove_week(week)
    await interaction.followup.send(
        f"🔄 **Week {week} Reset!**\n"
        f"Removed `{count}` players from Week {week}.",
        ephemeral=True)

# =============================================
# === TOP 10 COMMANDS ===
# =============================================

ALL_POSITIONS = [app_commands.Choice(name=f"{p[0]} - {p[1]}", value=p[0]) for p in [
    ("GK","Goalkeeper"),("LB","Left Back"),("RB","Right Back"),("CB","Center Back"),
    ("CM","Center Midfielder"),("CDM","Defensive Midfielder"),("CAM","Attacking Midfielder"),
    ("LM","Left Midfielder"),("RM","Right Midfielder"),("LW","Left Winger"),
    ("RW","Right Winger"),("ST","Striker")]]

PN = {"GK":"Goalkeeper","LB":"Left Back","RB":"Right Back","CB":"Center Back",
      "CM":"Center Midfielder","CDM":"Defensive Midfielder","CAM":"Attacking Midfielder",
      "LM":"Left Midfielder","RM":"Right Midfielder","LW":"Left Winger",
      "RW":"Right Winger","ST":"Striker"}

@bot.tree.command(name="top10", description="View Top 10 poster")
@maintenance_check()
@app_commands.describe(position="Select position")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_view(interaction: discord.Interaction, position: str):
    await interaction.response.defer()
    entries = top10_db.get_top10(position)
    if not entries:
        await interaction.followup.send(embed=discord.Embed(
            title=f"🏆 Top 10 {PN.get(position, position)}",
            description="No players yet! Use `/top10_add`.", color=0xF5A623).set_footer(text="FELIX PR"))
        return
    try:
        poster_bytes = poster_gen.generate(entries, position, PN.get(position, position))
        poster_file = discord.File(poster_bytes, filename=f"top10_{position}.png")
        embed = discord.Embed(title=f"🏆 Top 10 {PN.get(position, position)}", color=0xF5A623)
        embed.set_image(url=f"attachment://top10_{position}.png")
        embed.set_footer(text="FELIX PR | Updated weekly")
        await interaction.followup.send(embed=embed, file=poster_file)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="top10_add", description="Add player to Top 10 (Admin Only)")
@maintenance_check()
@app_commands.describe(position="Position", rank="Rank (1-10)", player_name="Player name",
    rating="Rating (e.g., 117 OVR)", image="Card image", 
    badge1="Optional: First playstyle badge", badge2="Optional: Second playstyle badge")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_add(interaction: discord.Interaction, position: str, rank: int,
    player_name: str, rating: str, image: discord.Attachment,
    badge1: discord.Attachment = None, badge2: discord.Attachment = None):
    
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    if rank < 1 or rank > 10:
        await interaction.response.send_message("❌ Rank 1-10!", ephemeral=True); return
    
    await interaction.response.defer(ephemeral=True)
    
    badge1_url = badge1.url if badge1 else None
    badge2_url = badge2.url if badge2 else None
    
    if top10_db.add_top10_entry(position, rank, player_name, "", rating, image.url, interaction.user.name, badge1_url, badge2_url):
        await interaction.followup.send(f"✅ **{player_name}** added to {position} #{rank}!", ephemeral=True)
    else: 
        await interaction.followup.send("❌ Failed!", ephemeral=True)

@bot.tree.command(name="top10_add_badges", description="Add badges to existing Top 10 player (Admin Only)")
@maintenance_check()
@app_commands.describe(position="Position", rank="Rank to update", 
    badge1="First playstyle badge", badge2="Second playstyle badge")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_add_badges(interaction: discord.Interaction, position: str, rank: int,
    badge1: discord.Attachment = None, badge2: discord.Attachment = None):
    
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    
    if not badge1 and not badge2:
        await interaction.response.send_message("❌ You must provide at least one badge!", ephemeral=True); return
        
    await interaction.response.defer(ephemeral=True)
    
    badge1_url = badge1.url if badge1 else None
    badge2_url = badge2.url if badge2 else None
    
    if top10_db.update_top10_badges(position, rank, badge1_url, badge2_url):
        await interaction.followup.send(f"✅ Badges updated for {position} #{rank}!", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ Failed! Is there a player at {position} #{rank}?", ephemeral=True)

@bot.tree.command(name="top10_remove", description="Remove player (Admin Only)")
@maintenance_check()
@app_commands.describe(position="Position", rank="Rank to remove")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_remove(interaction: discord.Interaction, position: str, rank: int):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    if top10_db.remove_top10_entry(position, rank):
        await interaction.response.send_message(f"✅ Removed #{rank} from {position}!", ephemeral=True)
    else: await interaction.response.send_message(f"❌ No player at #{rank}!", ephemeral=True)

@bot.tree.command(name="top10_swap", description="Swap two ranks (Admin Only)")
@maintenance_check()
@app_commands.describe(position="Position", rank1="First rank", rank2="Second rank")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_swap(interaction: discord.Interaction, position: str, rank1: int, rank2: int):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    if rank1 == rank2:
        await interaction.response.send_message("❌ Same rank!", ephemeral=True); return
    if top10_db.swap_top10_entries(position, rank1, rank2):
        await interaction.response.send_message(f"✅ Swapped #{rank1} & #{rank2}!", ephemeral=True)
    else: await interaction.response.send_message("❌ Failed!", ephemeral=True)

@bot.tree.command(name="top10_debug", description="Show raw entries (Admin Only)")
@maintenance_check()
@app_commands.describe(position="Position")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_debug(interaction: discord.Interaction, position: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    entries = top10_db.get_top10(position)
    if not entries:
        await interaction.response.send_message(f"❌ No entries in {position}", ephemeral=True); return
    text = f"**{position} - {len(entries)} entries:**\n"
    for e in entries: text += f"Rank `{e['rank']}`: **{e['player_name']}** ({e['rating']})\n"
    await interaction.response.send_message(text, ephemeral=True)

@bot.tree.command(name="top10_clear", description="Clear all entries for a position (Admin Only)")
@maintenance_check()
@app_commands.describe(position="Position")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_clear(interaction: discord.Interaction, position: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    for rank in range(1, 11): top10_db.remove_top10_entry(position, rank)
    await interaction.response.send_message(f"✅ Cleared {position}!", ephemeral=True)

@bot.tree.command(name="top10_import", description="Import old top10.db into new 4+4+4 databases (Admin Only)")
@maintenance_check()
@app_commands.describe(old_db="Upload your old top10.db file")
async def top10_import(interaction: discord.Interaction, old_db: discord.Attachment):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    if not old_db.filename.endswith('.db'):
        await interaction.response.send_message("❌ Must be a .db file!", ephemeral=True); return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        file_data = await old_db.read()
        with open('_temp_import.db', 'wb') as f: f.write(file_data)
        old_conn = sqlite3.connect('_temp_import.db')
        old_conn.row_factory = sqlite3.Row
        positions = ['GK','LB','RB','CB','CM','CDM','CAM','LM','RM','LW','RW','ST']
        total = 0; details = []
        for pos in positions:
            try:
                cursor = old_conn.cursor()
                cursor.execute(f"SELECT * FROM top10_{pos} ORDER BY CAST(rank AS INTEGER)")
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        top10_db.add_top10_entry(position=pos, rank=row['rank'], player_name=row['player_name'],
                            card_name=row['card_name'] or "", rating=row['rating'],
                            image_url=row['image_url'] or "", updated_by=row['updated_by'] or "import")
                        total += 1
                    details.append(f"✅ {pos}: {len(rows)} entries")
                else: details.append(f"⚪ {pos}: empty")
            except Exception as e: details.append(f"⚠️ {pos}: skipped ({e})")
        old_conn.close(); os.remove('_temp_import.db')
        embed = discord.Embed(title="✅ Import Complete!", description=f"**{total}** entries imported.", color=0x2ecc71)
        embed.add_field(name="Details", value="\n".join(details[:12]), inline=False)
        embed.set_footer(text="FELIX PR")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Import failed: {e}", ephemeral=True)
        try: os.remove('_temp_import.db')
        except: pass

# =============================================
# === UTILITY COMMANDS ===
# =============================================

@bot.tree.command(name="backup", description="Download all data (Admin Only)")
@maintenance_check()
async def backup_command(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    files = []
    for f in ['top10_1.db','top10_2.db','top10_3.db','shards.db','bot_config.json']:
        if os.path.exists(f) and os.path.getsize(f) > 0: files.append(discord.File(f))
    if not files:
        await interaction.followup.send("❌ No files!", ephemeral=True); return
    embed = discord.Embed(title="💾 Backup Complete", color=0x2ecc71)
    embed.add_field(name="Files", value="\n".join([f"• {f.filename}" for f in files]), inline=False)
    embed.set_footer(text="FELIX PR | Use /restore to restore")
    await interaction.followup.send(embed=embed, files=files, ephemeral=True)

@bot.tree.command(name="restore", description="Restore from backup (Admin Only)")
@maintenance_check()
@app_commands.describe(
    top10_1_file="top10_1.db (opt)", top10_2_file="top10_2.db (opt)",
    top10_3_file="top10_3.db (opt)", shards_file="shards.db (opt)",
    config_file="bot_config.json (opt)")
async def restore_command(interaction: discord.Interaction,
    top10_1_file: discord.Attachment = None, top10_2_file: discord.Attachment = None,
    top10_3_file: discord.Attachment = None, shards_file: discord.Attachment = None,
    config_file: discord.Attachment = None):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return    await interaction.response.defer(ephemeral=True)
    restored, failed = [], []
    for file_obj, name in [(top10_1_file,'top10_1.db'),(top10_2_file,'top10_2.db'),
                           (top10_3_file,'top10_3.db'),(shards_file,'shards.db')]:
        if file_obj and file_obj.filename.endswith('.db'):
            try:
                data = await file_obj.read()
                with open(name,'wb') as f: f.write(data)
                restored.append(f"✅ {name}")
            except Exception as e: failed.append(f"❌ {name}: {e}")
    if config_file and config_file.filename.endswith('.json'):
        try:
            data = await config_file.read()
            with open('bot_config.json','wb') as f: f.write(data)
            restored.append("✅ bot_config.json")
        except Exception as e: failed.append(f"❌ bot_config.json: {e}")
    embed = discord.Embed(title="🔄 Restore Results", color=0x2ecc71 if restored else 0xe74c3c)
    if restored: embed.add_field(name="✅ Restored", value="\n".join(restored), inline=False)
    if failed: embed.add_field(name="❌ Failed", value="\n".join(failed), inline=False)
    if restored: embed.add_field(name="⚠️ Note", value="Restart for full effect", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="dbcheck", description="Check database status (Admin Only)")
@maintenance_check()
async def dbcheck_command(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("❌ Admin only!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🔍 Database Status", color=0x3498db)
    for db in ['top10_1.db','top10_2.db','top10_3.db','shards.db']:
        e = os.path.exists(db); s = os.path.getsize(db) if e else 0
        embed.add_field(name=f"📁 {db}", value=f"Exists: {e}\nSize: {s:,} bytes ({s/1024:.1f} KB)", inline=True)
    embed.add_field(name="📂 Working Dir", value=f"`{os.getcwd()}`", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="stats", description="Bot statistics")
@maintenance_check()
async def stats_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📊 FELIX PR Stats", color=0x2ecc71, timestamp=datetime.now())
    embed.add_field(name="Latency", value=f"{round(bot.latency*1000)}ms", inline=True)
    embed.add_field(name="💎 Total Shard Players", value=str(shard_db.get_count()), inline=True)
    for db in ['top10_1.db','top10_2.db','top10_3.db','shards.db']:
        s = os.path.getsize(db)/1024 if os.path.exists(db) else 0
        embed.add_field(name=db, value=f"{s:.1f} KB", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show all commands")
@maintenance_check()
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 FELIX PR - Help", color=0x8B5CF6, description="FC Mobile Top 10, Shard & Skill Guide Bot")
    embed.add_field(name="🏆 `/top10 <pos>`", value="View Top 10 poster", inline=False)
    embed.add_field(name="🔧 Top 10 Mgmt", value="`/top10_add` `/top10_add_badges` `/top10_remove` `/top10_swap`\n`/top10_debug` `/top10_clear` `/top10_import`", inline=False)
    embed.add_field(name="💎 Shard Guide", value="`/shard_add` `/shard_guide week: max_shards: value_tier: player_name:`\n`/shard_weeks` `/shard_remove player_id:` `/shard_reset_week`", inline=False)
    embed.add_field(name="🎯 Skill Guide", value="`/skill_guide position: playstyle:`", inline=False)
    embed.add_field(name="📢 `/announce_top10`", value="Announce Top 10 update in a channel", inline=False)
    embed.add_field(name="💾 `/backup` & `/restore`", value="Backup/restore all data (incl. shards)", inline=False)
    embed.add_field(name="📊 `/stats` & `/dbcheck`", value="Statistics & diagnostics", inline=False)
    embed.add_field(name="🔧 `/maintenance on/off`", value="Toggle maintenance mode (Admin)", inline=False)
    embed.set_footer(text="FELIX PR | 4+4+4 DB Split | Full Guide System")
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True; flask_thread.start()
    token = os.getenv('DISCORD_TOKEN')
    if not token: print("❌ DISCORD_TOKEN not set!"); exit(1)
    bot.run(token)
