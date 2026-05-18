import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
from dotenv import load_dotenv
from database import Database, Top10Database
from views import ReviewEditView, create_review_embed
from poster_generator import Top10Poster
import threading
from flask import Flask
import json
import asyncio
import aiohttp
import base64
import io
import sqlite3

# --- Flask Web Server (for Render health checks) ---
app = Flask(__name__)

@app.route('/')
def home():
    try:
        return f"FCM Review Bot is Online! | Reviews: {bot.db.get_review_count()}"
    except:
        return "FCM Review Bot is Online!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- Self-Ping System (keeps bot alive on Render) ---
async def self_ping():
    await bot.wait_until_ready()
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not RENDER_URL:
        print("⚠️ RENDER_EXTERNAL_URL not set. Self-ping disabled.")
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

# === CONFIGURATION ===
BOT_OWNER_ID = 1214456066687893506

ALLOWED_REVIEWERS = [
    1214456066687893506,
    553418145063239684,
    1202544947161468969,
    773492040339292190,
    1284912012102598767,
    1479410597387960371,
    1417457966956810261,
]

CONFIG_FILE = "bot_config.json"

class BotConfig:
    def __init__(self):
        self.data = self.load()
    def load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {"reviewer_role_id": None}
    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.data, f)
    def get_reviewer_role_id(self):
        return self.data.get("reviewer_role_id")
    def set_reviewer_role_id(self, role_id):
        self.data["reviewer_role_id"] = role_id
        self.save()

config = BotConfig()
top10_db = Top10Database()
poster_gen = Top10Poster()

# --- Review Search Dropdown View ---
class ReviewSearchView(discord.ui.View):
    def __init__(self, matching_reviews: list, db: Database, config):
        super().__init__(timeout=60)
        self.db = db
        self.config = config
        self.add_item(ReviewSelect(matching_reviews, db, config))

class ReviewSelect(discord.ui.Select):
    def __init__(self, matching_reviews: list, db: Database, config):
        self.db = db
        self.config = config
        options = []
        for review in matching_reviews[:25]:
            status = "✅" if review.get('verdict') != 'Pending' else "⏳"
            event_text = f" [{review.get('event', '')}]" if review.get('event') else ""
            label = f"{review['player_name']} {review['rating']}{event_text}"
            if len(label) > 100: label = label[:97] + "..."
            description = f"By: {review['reviewer_name']}"
            if len(description) > 100: description = description[:97] + "..."
            options.append(discord.SelectOption(label=label, description=description, value=str(review['id']), emoji=status))
        super().__init__(placeholder="Select a review to view...", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        review_id = int(self.values[0])
        review = self.db.get_review(review_id)
        if not review:
            await interaction.response.send_message("❌ Review not found!", ephemeral=True)
            return
        embed, file = create_review_embed(review)
        view = ReviewEditView(review_id, self.db, self.config, interaction.user)
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)

class FCMReviewBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)
        self.db = Database()
    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced commands for {self.user}")

bot = FCMReviewBot()

def is_allowed_reviewer(user_id: int) -> bool:
    return user_id in ALLOWED_REVIEWERS

def is_bot_owner(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID

def can_edit_top10(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID or user_id in [553418145063239684]

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'📊 Reviews: {bot.db.get_review_count()}')
    print(f'🏆 Top 10: Active (4+4+4 DB Split)')
    bot.loop.create_task(self_ping())

# =============================================
# === REVIEW COMMANDS ===
# =============================================

@bot.tree.command(name="review_outfield", description="Create a review for an outfield player (Restricted)")
@app_commands.describe(
    player_name="Player name", rating="Overall rating (e.g., 97 OVR)",
    event="Event/Promo name", pace="PACE", shooting="SHOOTING",
    passing="PASSING", dribbling="DRIBBLING", defending="DEFENDING",
    physical="PHYSICAL", skill_move="Skill Move (1-5)", weak_foot="Weak Foot (1-5)",
    strong_foot="Strong Foot", skill_points="Skill Points", image="Player card image"
)
@app_commands.choices(
    skill_move=[app_commands.Choice(name=f"{i} ★", value=i) for i in range(1,6)],
    weak_foot=[app_commands.Choice(name=f"{i} ★", value=i) for i in range(1,6)],
    strong_foot=[app_commands.Choice(name="Left", value="Left"), app_commands.Choice(name="Right", value="Right")]
)
async def review_outfield(interaction: discord.Interaction, player_name: str, rating: str, event: str,
    pace: str, shooting: str, passing: str, dribbling: str, defending: str, physical: str,
    skill_move: int, weak_foot: int, strong_foot: str, skill_points: str = "", image: discord.Attachment = None):
    if not is_allowed_reviewer(interaction.user.id):
        await interaction.response.send_message("❌ Not authorized!", ephemeral=True); return
    await interaction.response.defer()
    stats_display = f"**PAC:** {pace} | **SHO:** {shooting} | **PAS:** {passing}\n**DRI:** {dribbling} | **DEF:** {defending} | **PHY:** {physical}"
    image_url = image.url if image else None
    review_id = bot.db.add_review(player_name, rating, image_url, stats_display, str(interaction.user.id), interaction.user.display_name, event, skill_move, weak_foot, strong_foot, skill_points)
    review = bot.db.get_review(review_id)
    embed, file = create_review_embed(review)
    view = ReviewEditView(review_id, bot.db, config, interaction.user)
    if file: await interaction.followup.send(embed=embed, file=file, view=view)
    else: await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="review_gk", description="Create a review for a goalkeeper (Restricted)")
@app_commands.describe(
    player_name="Player name", rating="Overall rating (e.g., 96 OVR)",
    event="Event/Promo name", diving="DIVING", positioning="POSITIONING",
    handling="HANDLING", reflexes="REFLEXES", kicking="KICKING",
    physical="PHYSICAL", skill_move="Skill Move (1-5)", weak_foot="Weak Foot (1-5)",
    strong_foot="Strong Foot", skill_points="Skill Points", image="Player card image"
)
@app_commands.choices(
    skill_move=[app_commands.Choice(name=f"{i} ★", value=i) for i in range(1,6)],
    weak_foot=[app_commands.Choice(name=f"{i} ★", value=i) for i in range(1,6)],
    strong_foot=[app_commands.Choice(name="Left", value="Left"), app_commands.Choice(name="Right", value="Right")]
)
async def review_gk(interaction: discord.Interaction, player_name: str, rating: str, event: str,
    diving: str, positioning: str, handling: str, reflexes: str, kicking: str, physical: str,
    skill_move: int, weak_foot: int, strong_foot: str, skill_points: str = "", image: discord.Attachment = None):
    if not is_allowed_reviewer(interaction.user.id):
        await interaction.response.send_message("❌ Not authorized!", ephemeral=True); return
    await interaction.response.defer()
    stats_display = f"**DIV:** {diving} | **POS:** {positioning} | **HAN:** {handling}\n**REF:** {reflexes} | **KIC:** {kicking} | **PHY:** {physical}"
    image_url = image.url if image else None
    review_id = bot.db.add_review(player_name, rating, image_url, stats_display, str(interaction.user.id), interaction.user.display_name, event, skill_move, weak_foot, strong_foot, skill_points)
    review = bot.db.get_review(review_id)
    embed, file = create_review_embed(review)
    view = ReviewEditView(review_id, bot.db, config, interaction.user)
    if file: await interaction.followup.send(embed=embed, file=file, view=view)
    else: await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="update_image", description="Update card image for a review (Owner Only)")
@app_commands.describe(review_id="Review ID", image="New card image")
async def update_image(interaction: discord.Interaction, review_id: int, image: discord.Attachment):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    review = bot.db.get_review(review_id)
    if not review:
        await interaction.followup.send(f"❌ Review `{review_id}` not found!", ephemeral=True); return
    if bot.db.update_image(review_id, image.url):
        await interaction.followup.send(f"✅ Image updated for review `{review_id}`!", ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed to update image!", ephemeral=True)

# =============================================
# === TOP 10 COMMANDS ===
# =============================================

ALL_POSITIONS = [app_commands.Choice(name=f"{p[0]} - {p[1]}", value=p[0]) for p in [
    ("GK","Goalkeeper"),("LB","Left Back"),("RB","Right Back"),("CB","Center Back"),
    ("CM","Center Midfielder"),("CDM","Defensive Midfielder"),("CAM","Attacking Midfielder"),
    ("LM","Left Midfielder"),("RM","Right Midfielder"),("LW","Left Winger"),
    ("RW","Right Winger"),("ST","Striker")
]]

@bot.tree.command(name="top10", description="View Top 10 poster with card images")
@app_commands.describe(position="Select position")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_view(interaction: discord.Interaction, position: str):
    await interaction.response.defer()
    pn = {"GK":"Goalkeeper","LB":"Left Back","RB":"Right Back","CB":"Center Back",
          "CM":"Center Midfielder","CDM":"Defensive Midfielder","CAM":"Attacking Midfielder",
          "LM":"Left Midfielder","RM":"Right Midfielder","LW":"Left Winger",
          "RW":"Right Winger","ST":"Striker"}
    entries = top10_db.get_top10(position)
    if not entries:
        await interaction.followup.send(embed=discord.Embed(title=f"🏆 Top 10 {pn.get(position, position)}", description="No players yet! Use `/top10_add`.", color=0xF5A623).set_footer(text="FELIX PR"))
        return
    try:
        poster_bytes = poster_gen.generate(entries, position, pn.get(position, position))
        poster_file = discord.File(poster_bytes, filename=f"top10_{position}.png")
        embed = discord.Embed(title=f"🏆 Top 10 {pn.get(position, position)}", color=0xF5A623)
        embed.set_image(url=f"attachment://top10_{position}.png")
        embed.set_footer(text="FELIX PR | Updated weekly")
        await interaction.followup.send(embed=embed, file=poster_file)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

@bot.tree.command(name="top10_add", description="Add player to Top 10 (Owner/Admin)")
@app_commands.describe(position="Position", rank="Rank (1-10)", player_name="Player name", rating="Rating (e.g., 117 OVR)", image="Card image")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_add(interaction: discord.Interaction, position: str, rank: int, player_name: str, rating: str, image: discord.Attachment):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ No permission!", ephemeral=True); return
    if rank < 1 or rank > 10:
        await interaction.response.send_message("❌ Rank 1-10!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    if top10_db.add_top10_entry(position, rank, player_name, "", rating, image.url, interaction.user.name):
        await interaction.followup.send(f"✅ **{player_name}** added to {position} #{rank}!", ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed!", ephemeral=True)

@bot.tree.command(name="top10_remove", description="Remove player from Top 10 (Owner/Admin)")
@app_commands.describe(position="Position", rank="Rank to remove")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_remove(interaction: discord.Interaction, position: str, rank: int):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ No permission!", ephemeral=True); return
    if top10_db.remove_top10_entry(position, rank):
        await interaction.response.send_message(f"✅ Removed #{rank} from {position}!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No player at #{rank}!", ephemeral=True)

@bot.tree.command(name="top10_swap", description="Swap two ranks (Owner/Admin)")
@app_commands.describe(position="Position", rank1="First rank", rank2="Second rank")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_swap(interaction: discord.Interaction, position: str, rank1: int, rank2: int):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ No permission!", ephemeral=True); return
    if rank1 == rank2:
        await interaction.response.send_message("❌ Same rank!", ephemeral=True); return
    if top10_db.swap_top10_entries(position, rank1, rank2):
        await interaction.response.send_message(f"✅ Swapped #{rank1} & #{rank2}!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Failed!", ephemeral=True)

@bot.tree.command(name="top10_debug", description="Show raw entries (Owner)")
@app_commands.describe(position="Position")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_debug(interaction: discord.Interaction, position: str):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    entries = top10_db.get_top10(position)
    if not entries:
        await interaction.response.send_message(f"❌ No entries in {position}", ephemeral=True); return
    text = f"**{position} - {len(entries)} entries:**\n"
    for e in entries: text += f"Rank `{e['rank']}`: **{e['player_name']}** ({e['rating']})\n"
    await interaction.response.send_message(text, ephemeral=True)

@bot.tree.command(name="top10_clear", description="Clear all entries for a position (Owner)")
@app_commands.describe(position="Position")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_clear(interaction: discord.Interaction, position: str):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    for rank in range(1, 11): top10_db.remove_top10_entry(position, rank)
    await interaction.response.send_message(f"✅ Cleared {position}!", ephemeral=True)

@bot.tree.command(name="top10_migrate", description="Migrate old top10.db to new 4+4+4 split databases (Owner Only)")
async def top10_migrate(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True)
        return
    
    if not os.path.exists('top10.db'):
        await interaction.response.send_message("❌ No old `top10.db` found! Nothing to migrate.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    positions = ['GK', 'LB', 'RB', 'CB', 'CM', 'CDM', 'CAM', 'LM', 'RM', 'LW', 'RW', 'ST']
    migrated = 0
    
    try:
        old_conn = sqlite3.connect('top10.db')
        old_conn.row_factory = sqlite3.Row
        
        for position in positions:
            try:
                cursor = old_conn.cursor()
                cursor.execute(f"SELECT * FROM top10_{position} ORDER BY CAST(rank AS INTEGER)")
                rows = cursor.fetchall()
                
                for row in rows:
                    top10_db.add_top10_entry(
                        position=position,
                        rank=row['rank'],
                        player_name=row['player_name'],
                        card_name=row['card_name'] if row['card_name'] else "",
                        rating=row['rating'],
                        image_url=row['image_url'] if row['image_url'] else "",
                        updated_by=row['updated_by'] if row['updated_by'] else "migration"
                    )
                    migrated += 1
            except Exception as e:
                print(f"⚠️ Skipped {position}: {e}")
        
        old_conn.close()
        
        # Rename old database as backup
        os.rename('top10.db', 'top10_old_backup.db')
        
        embed = discord.Embed(
            title="✅ Migration Complete!",
            description=f"**{migrated}** entries migrated from old database.\nOld file renamed to `top10_old_backup.db`",
            color=discord.Color.green()
        )
        embed.add_field(name="New Structure", value="• `top10_1.db` - GK, LB, RB, CB\n• `top10_2.db` - CM, CDM, CAM, LM\n• `top10_3.db` - RM, LW, RW, ST", inline=False)
        embed.set_footer(text="Old backup kept as top10_old_backup.db - delete when ready")
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Migration failed: {e}", ephemeral=True)

# =============================================
# === OTHER COMMANDS ===
# =============================================

@bot.tree.command(name="search", description="Search reviews by player name")
@app_commands.describe(player_name="Player name")
async def search_command(interaction: discord.Interaction, player_name: str):
    reviews = bot.db.get_all_reviews()
    matching = [r for r in reviews if player_name.lower() in r['player_name'].lower()]
    if not matching:
        await interaction.response.send_message(f"❌ No reviews for **{player_name}**", ephemeral=True); return
    embed = discord.Embed(title=f"🔍 Search: '{player_name}'", description=f"Found **{len(matching)}** review(s). Select below:", color=0x3498db)
    await interaction.response.send_message(embed=embed, view=ReviewSearchView(matching, bot.db, config), ephemeral=False)

@bot.tree.command(name="assign_reviewer_role", description="Set reviewer role (Owner)")
@app_commands.describe(role="Role for editing reviews")
async def assign_reviewer_role(interaction: discord.Interaction, role: discord.Role):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    config.set_reviewer_role_id(role.id)
    await interaction.response.send_message(f"✅ **{role.name}** can now edit reviews!")

@bot.tree.command(name="check_reviewer_role", description="Check current reviewer role (Owner)")
async def check_reviewer_role(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    role_id = config.get_reviewer_role_id()
    if role_id:
        role = interaction.guild.get_role(role_id)
        if role: await interaction.response.send_message(f"🎭 Reviewer role: **{role.name}** (`{role.id}`)", ephemeral=True)
        else: await interaction.response.send_message("⚠️ Role deleted! Set new one.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ No role set!", ephemeral=True)

@bot.tree.command(name="list_reviews", description="List all reviews")
async def list_reviews(interaction: discord.Interaction):
    reviews = bot.db.get_all_reviews()
    if not reviews:
        await interaction.response.send_message("No reviews!", ephemeral=True); return
    embed = discord.Embed(title="📋 All Reviews", color=0x3498db, description=f"Total: {len(reviews)}")
    for r in reviews[:25]:
        s = "✅" if r.get('verdict') != 'Pending' else "⏳"
        ev = f" [{r.get('event','')}]" if r.get('event') else ""
        embed.add_field(name=f"{s} {r['player_name']} {r['rating']}{ev}", value=f"ID: `{r['id']}` | By: {r['reviewer_name']}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="backup", description="Download all data (Owner)")
async def backup_command(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    try:
        conn = sqlite3.connect('fcm_reviews.db'); conn.commit(); conn.close()
    except: pass
    files_to_send = []
    for f in ['fcm_reviews.db', 'top10_1.db', 'top10_2.db', 'top10_3.db', 'bot_config.json']:
        if os.path.exists(f) and os.path.getsize(f) > 0:
            files_to_send.append(discord.File(f))
    if not files_to_send:
        await interaction.followup.send("❌ No files!", ephemeral=True); return
    embed = discord.Embed(title="💾 Backup Complete", description=f"Reviews: {bot.db.get_review_count()}", color=0x2ecc71)
    embed.add_field(name="Files", value="\n".join([f"• {f.filename}" for f in files_to_send]), inline=False)
    embed.set_footer(text="FELIX PR | Use /restore to restore")
    await interaction.followup.send(embed=embed, files=files_to_send, ephemeral=True)

@bot.tree.command(name="restore", description="Restore from backup (Owner)")
@app_commands.describe(
    reviews_file="fcm_reviews.db",
    top10_1_file="top10_1.db (optional)",
    top10_2_file="top10_2.db (optional)",
    top10_3_file="top10_3.db (optional)",
    config_file="bot_config.json (optional)"
)
async def restore_command(interaction: discord.Interaction, reviews_file: discord.Attachment,
    top10_1_file: discord.Attachment = None, top10_2_file: discord.Attachment = None,
    top10_3_file: discord.Attachment = None, config_file: discord.Attachment = None):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    restored, failed = [], []
    if reviews_file.filename.endswith('.db'):
        try:
            data = await reviews_file.read()
            with open('fcm_reviews.db', 'wb') as f: f.write(data)
            bot.db = Database()
            restored.append(f"✅ fcm_reviews.db ({bot.db.get_review_count()} reviews)")
        except Exception as e: failed.append(f"❌ fcm_reviews.db: {e}")
    else: failed.append("❌ reviews_file must be .db")
    for file_obj, name in [(top10_1_file,'top10_1.db'),(top10_2_file,'top10_2.db'),(top10_3_file,'top10_3.db')]:
        if file_obj and file_obj.filename.endswith('.db'):
            try:
                data = await file_obj.read()
                with open(name, 'wb') as f: f.write(data)
                restored.append(f"✅ {name}")
            except Exception as e: failed.append(f"❌ {name}: {e}")
    if config_file and config_file.filename.endswith('.json'):
        try:
            data = await config_file.read()
            with open('bot_config.json', 'wb') as f: f.write(data)
            restored.append("✅ bot_config.json")
        except Exception as e: failed.append(f"❌ bot_config.json: {e}")
    embed = discord.Embed(title="🔄 Restore Results", color=0x2ecc71 if restored else 0xe74c3c)
    if restored: embed.add_field(name="✅ Restored", value="\n".join(restored), inline=False)
    if failed: embed.add_field(name="❌ Failed", value="\n".join(failed), inline=False)
    if restored: embed.add_field(name="⚠️ Note", value="Restart for full effect", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="dbcheck", description="Check database status (Owner)")
async def dbcheck_command(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🔍 Database Status", color=0x3498db)
    for db in ['fcm_reviews.db','top10_1.db','top10_2.db','top10_3.db']:
        e = os.path.exists(db); s = os.path.getsize(db) if e else 0
        embed.add_field(name=f"📁 {db}", value=f"Exists: {e}\nSize: {s:,} bytes ({s/1024:.1f} KB)", inline=True)
    if os.path.exists('top10.db'):
        s = os.path.getsize('top10.db')
        embed.add_field(name="⚠️ top10.db (old)", value=f"Size: {s:,} bytes\nUse `/top10_migrate`", inline=True)
    embed.add_field(name="📂 Working Dir", value=f"`{os.getcwd()}`", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="stats", description="Bot statistics")
async def stats_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📊 FELIX PR Stats", color=0x2ecc71, timestamp=datetime.now())
    embed.add_field(name="Reviews", value=str(bot.db.get_review_count()), inline=True)
    rs = os.path.getsize('fcm_reviews.db')/1024 if os.path.exists('fcm_reviews.db') else 0
    embed.add_field(name="Reviews DB", value=f"{rs:.1f} KB", inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency*1000)}ms", inline=True)
    for db in ['top10_1.db','top10_2.db','top10_3.db']:
        s = os.path.getsize(db)/1024 if os.path.exists(db) else 0
        embed.add_field(name=db, value=f"{s:.1f} KB", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show all commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 FELIX PR - Help", color=0x8B5CF6, description="FC Mobile Player Review Bot")
    embed.add_field(name="⚽ `/review_outfield`", value="Create outfield review", inline=False)
    embed.add_field(name="🧤 `/review_gk`", value="Create GK review", inline=False)
    embed.add_field(name="🏆 `/top10 <pos>`", value="View Top 10 poster", inline=False)
    embed.add_field(name="🔧 Top 10 Mgmt", value="`/top10_add` `/top10_remove` `/top10_swap`\n`/top10_debug` `/top10_clear` `/top10_migrate`", inline=False)
    embed.add_field(name="🖼️ `/update_image`", value="Update card image", inline=False)
    embed.add_field(name="🔍 `/search`", value="Search reviews", inline=False)
    embed.add_field(name="📋 `/list_reviews`", value="List all reviews", inline=False)
    embed.add_field(name="💾 `/backup` & `/restore`", value="Backup/restore all data", inline=False)
    embed.add_field(name="📊 `/stats` & `/dbcheck`", value="Statistics & diagnostics", inline=False)
    embed.set_footer(text="FELIX PR | 4+4+4 DB Split")
    await interaction.response.send_message(embed=embed)

# Run
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN not set!")
        exit(1)
    bot.run(token)
