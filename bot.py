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

# --- Flask Web Server (for Render health checks) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "FCM Review Bot is Online!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

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

async def has_reviewer_role(interaction: discord.Interaction) -> bool:
    role_id = config.get_reviewer_role_id()
    if not role_id:
        return False
    
    role = interaction.guild.get_role(role_id)
    if not role:
        return False
    
    return role in interaction.user.roles

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
    print('------')

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
    
    # Format stats for storage
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

@bot.tree.command(name="check_reviewer_role", description="Check the current reviewer role (Bot Owner Only)")
async def check_reviewer_role(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    role_id = config.get_reviewer_role_id()
    if role_id:
        role = interaction.guild.get_role(role_id)
        if role:
            await interaction.response.send_message(
                f"✅ Current reviewer role: **{role.name}** (ID: {role.id})",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "⚠️ Reviewer role is set but no longer exists in this server.",
                ephemeral=True
            )
    else:
        await interaction.response.send_message(
            "❌ No reviewer role has been set yet.\nUse `/assign_reviewer_role` to set one.",
            ephemeral=True
        )

@bot.tree.command(name="add_reviewer", description="Add a user ID to allowed reviewers (Bot Owner Only)")
@app_commands.describe(user_id="The Discord User ID to add")
async def add_reviewer(interaction: discord.Interaction, user_id: str):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    try:
        uid = int(user_id)
        if uid not in ALLOWED_REVIEWERS:
            ALLOWED_REVIEWERS.append(uid)
            await interaction.response.send_message(
                f"✅ Added user ID `{uid}` to allowed reviewers.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ User ID `{uid}` is already in the allowed list.",
                ephemeral=True
            )
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid user ID. Please provide a numeric ID.",
            ephemeral=True
        )

@bot.tree.command(name="remove_reviewer", description="Remove a user ID from allowed reviewers (Bot Owner Only)")
@app_commands.describe(user_id="The Discord User ID to remove")
async def remove_reviewer(interaction: discord.Interaction, user_id: str):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    try:
        uid = int(user_id)
        if uid == BOT_OWNER_ID:
            await interaction.response.send_message(
                "❌ Cannot remove the bot owner from the allowed list.",
                ephemeral=True
            )
        elif uid in ALLOWED_REVIEWERS:
            ALLOWED_REVIEWERS.remove(uid)
            await interaction.response.send_message(
                f"✅ Removed user ID `{uid}` from allowed reviewers.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ User ID `{uid}` is not in the allowed list.",
                ephemeral=True
            )
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid user ID. Please provide a numeric ID.",
            ephemeral=True
        )

@bot.tree.command(name="list_reviewers", description="List all allowed reviewers (Bot Owner Only)")
async def list_reviewers(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="📋 Allowed Reviewers",
        color=discord.Color.blue(),
        description=f"Total: {len(ALLOWED_REVIEWERS)} users"
    )
    
    for uid in ALLOWED_REVIEWERS:
        user = bot.get_user(uid)
        username = user.name if user else "Unknown User"
        crown = " 👑" if uid == BOT_OWNER_ID else ""
        embed.add_field(
            name=f"{username}{crown}",
            value=f"ID: `{uid}`",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

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

@bot.tree.command(name="backup", description="Create and download a backup of all reviews")
@app_commands.default_permissions(administrator=True)
async def backup_command(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    backup_path = bot.db.create_backup()
    file = discord.File(backup_path, filename=f"fcm_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    
    await interaction.followup.send(
        content=f"✅ **Backup Created**\nTotal Reviews: {bot.db.get_review_count()}",
        file=file,
        ephemeral=True
    )
    os.remove(backup_path)

@bot.tree.command(name="restore", description="Restore database from a backup file")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(backup_file="The .db backup file to restore from")
async def restore_command(interaction: discord.Interaction, backup_file: discord.Attachment):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    if not backup_file.filename.endswith('.db'):
        await interaction.response.send_message("Please upload a valid .db file!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    temp_path = f"temp_restore_{datetime.now().timestamp()}.db"
    await backup_file.save(temp_path)
    
    success = bot.db.restore_backup(temp_path)
    os.remove(temp_path)
    
    if success:
        bot.db = Database()
        await interaction.followup.send(
            f"✅ **Database Restored Successfully!**\nTotal Reviews: {bot.db.get_review_count()}",
            ephemeral=True
        )
    else:
        await interaction.followup.send("❌ Failed to restore database!", ephemeral=True)

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
        value="Create a new player review with:\n**Player Name, Rating, Event, Stats, Skill Move, Weak Foot, Strong Foot, Image**",
        inline=False
    )
    
    embed.add_field(
        name="🔍 `/search <player>`",
        value="Search for a player review by name and select from dropdown",
        inline=False
    )
    
    embed.add_field(
        name="📋 `/list_reviews`",
        value="Show all reviews in the database",
        inline=False
    )
    
    embed.add_field(
        name="✏️ Editing Reviews",
        value="Edit buttons are ONLY visible to: Bot Owner, users with Reviewer Role, and the original reviewer",
        inline=False
    )
    
    embed.add_field(
        name="💾 `/backup`",
        value="Download a backup of all reviews (Bot Owner only)",
        inline=False
    )
    
    embed.add_field(
        name="🔄 `/restore`",
        value="Restore database from a backup file (Bot Owner only)",
        inline=False
    )
    
    embed.add_field(
        name="📊 `/stats`",
        value="View bot statistics",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

# Run the bot with Flask in a separate thread
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ ERROR: No token found in .env file!")
        exit(1)
    
    bot.run(token)
