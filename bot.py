import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
from dotenv import load_dotenv
from database import Database
from views import ReviewEditView, create_review_embed
import threading
from flask import Flask
import json
import asyncio
import aiohttp

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
    """Ping the external URL every 14 minutes to prevent Render sleep"""
    await bot.wait_until_ready()
    
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not RENDER_URL:
        print("⚠️ RENDER_EXTERNAL_URL not set. Self-ping disabled.")
        return
    
    while not bot.is_closed():
        await asyncio.sleep(840)  # 14 minutes
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(RENDER_URL) as response:
                    if response.status == 200:
                        print(f"🔄 Self-ping OK at {datetime.now().strftime('%H:%M:%S')}")
                    else:
                        print(f"⚠️ Self-ping status: {response.status}")
        except Exception as e:
            print(f"⚠️ Self-ping failed: {e}")

# --- Discord Bot Setup ---
load_dotenv()

# === CONFIGURATION ===
BOT_OWNER_ID = 1214456066687893506

ALLOWED_REVIEWERS = [
    1214456066687893506,  # Bot Owner
    553418145063239684,   # Other reviewer
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
            if len(label) > 100:
                label = label[:97] + "..."
            
            description = f"By: {review['reviewer_name']}"
            if len(description) > 100:
                description = description[:97] + "..."
            
            options.append(
                discord.SelectOption(
                    label=label,
                    description=description,
                    value=str(review['id']),
                    emoji=status
                )
            )
        
        super().__init__(
            placeholder="Select a review to view...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        review_id = int(self.values[0])
        review = self.db.get_review(review_id)
        
        if not review:
            await interaction.response.send_message(
                "❌ Review not found! It may have been deleted.",
                ephemeral=True
            )
            return
        
        embed = create_review_embed(review)
        view = ReviewEditView(review_id, self.db, self.config, interaction.user)
        
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
        self.add_view(ReviewEditView(0, self.db, config, None))

bot = FCMReviewBot()

# === PERMISSION CHECK FUNCTIONS ===
def is_allowed_reviewer(user_id: int) -> bool:
    return user_id in ALLOWED_REVIEWERS

def is_bot_owner(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID

def format_stats(pace: str, shooting: str, passing: str, dribbling: str, defending: str, physical: str) -> str:
    """Format the stats into a clean display string"""
    return f"**PAC:** {pace} | **SHO:** {shooting} | **PAS:** {passing}\n**DRI:** {dribbling} | **DEF:** {defending} | **PHY:** {physical}"

# === BOT EVENTS ===
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'📊 Total reviews in database: {bot.db.get_review_count()}')
    print(f'👑 Bot Owner ID: {BOT_OWNER_ID}')
    print(f'📝 Allowed Reviewers: {ALLOWED_REVIEWERS}')
    reviewer_role = config.get_reviewer_role_id()
    if reviewer_role:
        print(f'🎭 Reviewer Role ID: {reviewer_role}')
    print(f'🔄 Self-ping system: Active (every 14 minutes)')
    print('------')
    
    # Start self-ping task
    bot.loop.create_task(self_ping())

# === SLASH COMMANDS ===

@bot.tree.command(name="review", description="Start a new player review (Restricted)")
@app_commands.describe(
    player_name="Name of the player (e.g., Kylian Mbappé)",
    rating="Overall rating (e.g., 97 OVR)",
    event="Event/Promo name (e.g., TOTY, TOTS, UCL, Hero, Icon)",
    pace="PACE stat (e.g., 97)",
    shooting="SHOOTING stat (e.g., 94)",
    passing="PASSING stat (e.g., 88)",
    dribbling="DRIBBLING stat (e.g., 95)",
    defending="DEFENDING stat (e.g., 40)",
    physical="PHYSICAL stat (e.g., 78)",
    skill_move="Skill Move stars (1-5)",
    weak_foot="Weak Foot stars (1-5)",
    strong_foot="Strong Foot (Left or Right)",
    image="Upload the player card image"
)
@app_commands.choices(
    skill_move=[
        app_commands.Choice(name="1 ★", value=1),
        app_commands.Choice(name="2 ★★", value=2),
        app_commands.Choice(name="3 ★★★", value=3),
        app_commands.Choice(name="4 ★★★★", value=4),
        app_commands.Choice(name="5 ★★★★★", value=5),
    ],
    weak_foot=[
        app_commands.Choice(name="1 ★", value=1),
        app_commands.Choice(name="2 ★★", value=2),
        app_commands.Choice(name="3 ★★★", value=3),
        app_commands.Choice(name="4 ★★★★", value=4),
        app_commands.Choice(name="5 ★★★★★", value=5),
    ],
    strong_foot=[
        app_commands.Choice(name="Left", value="Left"),
        app_commands.Choice(name="Right", value="Right"),
    ]
)
async def review_command(
    interaction: discord.Interaction,
    player_name: str,
    rating: str,
    event: str,
    pace: str,
    shooting: str,
    passing: str,
    dribbling: str,
    defending: str,
    physical: str,
    skill_move: int,
    weak_foot: int,
    strong_foot: str,
    image: discord.Attachment
):
    if not is_allowed_reviewer(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nYou are not authorized to create reviews.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    stats_display = format_stats(pace, shooting, passing, dribbling, defending, physical)
    
    review_id = bot.db.add_review(
        player_name=player_name,
        rating=rating,
        image_url=image.url,
        base_stats=stats_display,
        reviewer_id=str(interaction.user.id),
        reviewer_name=interaction.user.display_name,
        event=event,
        skill_move=skill_move,
        weak_foot=weak_foot,
        strong_foot=strong_foot
    )
    
    review = bot.db.get_review(review_id)
    embed = create_review_embed(review)
    view = ReviewEditView(review_id, bot.db, config, interaction.user)
    
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="search", description="Search for a player review by name")
@app_commands.describe(player_name="Name of the player to search for")
async def search_command(interaction: discord.Interaction, player_name: str):
    reviews = bot.db.get_all_reviews()
    
    matching_reviews = [
        r for r in reviews 
        if player_name.lower() in r['player_name'].lower()
    ]
    
    if not matching_reviews:
        await interaction.response.send_message(
            f"❌ No reviews found for **{player_name}**",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title=f"🔍 Search Results for '{player_name}'",
        description=f"Found **{len(matching_reviews)}** matching review(s).\nSelect one from the dropdown below:",
        color=discord.Color.blue()
    )
    
    view = ReviewSearchView(matching_reviews, bot.db, config)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

@bot.tree.command(name="assign_reviewer_role", description="Set the role that can edit reviews (Bot Owner Only)")
@app_commands.describe(role="The role to assign for editing reviews")
async def assign_reviewer_role(interaction: discord.Interaction, role: discord.Role):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    config.set_reviewer_role_id(role.id)
    
    embed = discord.Embed(
        title="✅ Reviewer Role Set",
        description=f"Users with the **{role.name}** role can now edit reviews.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="list_reviews", description="List all reviews in the database")
async def list_reviews(interaction: discord.Interaction):
    reviews = bot.db.get_all_reviews()
    
    if not reviews:
        await interaction.response.send_message("No reviews found!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📋 All Player Reviews",
        color=discord.Color.blue(),
        description=f"Total: {len(reviews)} reviews"
    )
    
    for review in reviews[:25]:
        status = "✅" if review.get('verdict') != 'Pending' else "⏳"
        event_text = f" [{review.get('event', '')}]" if review.get('event') else ""
        embed.add_field(
            name=f"{status} {review['player_name']} {review['rating']}{event_text}",
            value=f"ID: `{review['id']}` | By: {review['reviewer_name']}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="backup", description="Download all bot data for backup (Owner Only)")
async def backup_command(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    files_to_send = []
    
    if os.path.exists('fcm_reviews.db'):
        files_to_send.append(discord.File('fcm_reviews.db'))
    if os.path.exists('bot_config.json'):
        files_to_send.append(discord.File('bot_config.json'))
    
    if not files_to_send:
        await interaction.followup.send("❌ No database files found!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="💾 Backup Complete",
        description=f"**Time:** <t:{int(datetime.now().timestamp())}:F>\n**Reviews:** {bot.db.get_review_count()}",
        color=discord.Color.green()
    )
    embed.add_field(name="Files", value="• fcm_reviews.db\n• bot_config.json", inline=False)
    embed.add_field(name="💡 Restore", value="Use `/restore` and attach these files", inline=False)
    embed.set_footer(text="FCM Review Bot | Save these files!")
    
    await interaction.followup.send(embed=embed, files=files_to_send, ephemeral=True)

@bot.tree.command(name="restore", description="Restore database from backup files (Owner Only)")
@app_commands.describe(
    db_file="The fcm_reviews.db backup file",
    config_file="The bot_config.json backup file (optional)"
)
async def restore_command(
    interaction: discord.Interaction, 
    db_file: discord.Attachment,
    config_file: discord.Attachment = None
):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    restored = []
    failed = []
    
    if db_file.filename.endswith('.db'):
        try:
            file_data = await db_file.read()
            with open('fcm_reviews.db', 'wb') as f:
                f.write(file_data)
            
            bot.db = Database()
            count = bot.db.get_review_count()
            restored.append(f"✅ fcm_reviews.db ({count} reviews)")
        except Exception as e:
            failed.append(f"❌ fcm_reviews.db: {str(e)}")
    else:
        failed.append("❌ db_file must be a .db file")
    
    if config_file and config_file.filename.endswith('.json'):
        try:
            file_data = await config_file.read()
            with open('bot_config.json', 'wb') as f:
                f.write(file_data)
            restored.append("✅ bot_config.json")
        except Exception as e:
            failed.append(f"❌ bot_config.json: {str(e)}")
    
    embed = discord.Embed(
        title="🔄 Restore Results",
        color=discord.Color.green() if restored else discord.Color.red(),
        timestamp=datetime.now()
    )
    
    if restored:
        embed.add_field(name="✅ Restored", value="\n".join(restored), inline=False)
    if failed:
        embed.add_field(name="❌ Failed", value="\n".join(failed), inline=False)
    
    if restored:
        embed.add_field(name="⚠️ Note", value="Restart recommended for full effect", inline=False)
    
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="stats", description="Show bot statistics")
async def stats_command(interaction: discord.Interaction):
    review_count = bot.db.get_review_count()
    
    embed = discord.Embed(
        title="📊 FCM Review Bot Statistics",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Total Reviews", value=str(review_count), inline=True)
    
    db_size = os.path.getsize('fcm_reviews.db') / 1024 if os.path.exists('fcm_reviews.db') else 0
    embed.add_field(name="Database Size", value=f"{db_size:.2f} KB", inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show help for the review system")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 FCM Review Bot Help",
        description="Complete guide to using the review system",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="📝 `/review`",
        value="Create a new player review with all stats",
        inline=False
    )
    
    embed.add_field(
        name="🔍 `/search <player>`",
        value="Search for a player review by name",
        inline=False
    )
    
    embed.add_field(
        name="📋 `/list_reviews`",
        value="Show all reviews in the database",
        inline=False
    )
    
    embed.add_field(
        name="✏️ Editing Reviews",
        value="Edit buttons visible to: Owner, Reviewer Role, Original Reviewer",
        inline=False
    )
    
    embed.add_field(
        name="💾 `/backup`",
        value="Download all data for backup (Owner only)",
        inline=False
    )
    
    embed.add_field(
        name="🔄 `/restore`",
        value="Restore from backup files (Owner only)",
        inline=False
    )
    
    embed.add_field(
        name="📊 `/stats`",
        value="View bot statistics",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

# Run the bot
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ ERROR: No token found in .env file!")
        exit(1)
    
    bot.run(token)
