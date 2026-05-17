import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
from dotenv import load_dotenv
from database import Database, Top10Database
from views import ReviewEditView, create_review_embed
import threading
from flask import Flask
import json
import asyncio
import aiohttp
import base64
import io

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
        await asyncio.sleep(840)
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

# Initialize Top 10 database
top10_db = Top10Database()

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

# === PERMISSION CHECK FUNCTIONS ===
def is_allowed_reviewer(user_id: int) -> bool:
    return user_id in ALLOWED_REVIEWERS

def is_bot_owner(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID

def can_edit_top10(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID or user_id in [553418145063239684]

# === BOT EVENTS ===
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'📊 Total reviews in database: {bot.db.get_review_count()}')
    print(f'👑 Bot Owner ID: {BOT_OWNER_ID}')
    print(f'📝 Allowed Reviewers: {ALLOWED_REVIEWERS}')
    print(f'🏆 Top 10 System: Active')
    reviewer_role = config.get_reviewer_role_id()
    if reviewer_role:
        print(f'🎭 Reviewer Role ID: {reviewer_role}')
    print(f'🔄 Self-ping system: Active (every 14 minutes)')
    print('------')
    
    bot.loop.create_task(self_ping())

# =============================================
# === OUTFIELD PLAYER REVIEW COMMAND ===
# =============================================
@bot.tree.command(name="review_outfield", description="Create a review for an outfield player (Restricted)")
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
    skill_points="Skill Points (e.g., 2X Attacking Midfielder, 2X Playmaker, 1X Dribbling)",
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
async def review_outfield(
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
    skill_points: str = "",
    image: discord.Attachment = None
):
    if not is_allowed_reviewer(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nYou are not authorized to create reviews.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    stats_display = f"**PAC:** {pace} | **SHO:** {shooting} | **PAS:** {passing}\n**DRI:** {dribbling} | **DEF:** {defending} | **PHY:** {physical}"
    image_url = image.url if image else None
    
    review_id = bot.db.add_review(
        player_name=player_name,
        rating=rating,
        image_url=image_url,
        base_stats=stats_display,
        reviewer_id=str(interaction.user.id),
        reviewer_name=interaction.user.display_name,
        event=event,
        skill_move=skill_move,
        weak_foot=weak_foot,
        strong_foot=strong_foot,
        skill_points=skill_points
    )
    
    review = bot.db.get_review(review_id)
    embed, file = create_review_embed(review)
    view = ReviewEditView(review_id, bot.db, config, interaction.user)
    
    if file:
        await interaction.followup.send(embed=embed, file=file, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view)

# =============================================
# === GOALKEEPER REVIEW COMMAND ===
# =============================================
@bot.tree.command(name="review_gk", description="Create a review for a goalkeeper (Restricted)")
@app_commands.describe(
    player_name="Name of the goalkeeper (e.g., Thibaut Courtois)",
    rating="Overall rating (e.g., 96 OVR)",
    event="Event/Promo name (e.g., TOTY, TOTS, UCL, Hero, Icon)",
    diving="DIVING stat (e.g., 95)",
    positioning="POSITIONING stat (e.g., 92)",
    handling="HANDLING stat (e.g., 90)",
    reflexes="REFLEXES stat (e.g., 93)",
    kicking="KICKING stat (e.g., 85)",
    physical="PHYSICAL stat (e.g., 88)",
    skill_move="Skill Move stars (1-5)",
    weak_foot="Weak Foot stars (1-5)",
    strong_foot="Strong Foot (Left or Right)",
    skill_points="Skill Points (e.g., 2X Diving, 2X Reflexes, 1X Handling)",
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
async def review_gk(
    interaction: discord.Interaction,
    player_name: str,
    rating: str,
    event: str,
    diving: str,
    positioning: str,
    handling: str,
    reflexes: str,
    kicking: str,
    physical: str,
    skill_move: int,
    weak_foot: int,
    strong_foot: str,
    skill_points: str = "",
    image: discord.Attachment = None
):
    if not is_allowed_reviewer(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nYou are not authorized to create reviews.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    stats_display = f"**DIV:** {diving} | **POS:** {positioning} | **HAN:** {handling}\n**REF:** {reflexes} | **KIC:** {kicking} | **PHY:** {physical}"
    image_url = image.url if image else None
    
    review_id = bot.db.add_review(
        player_name=player_name,
        rating=rating,
        image_url=image_url,
        base_stats=stats_display,
        reviewer_id=str(interaction.user.id),
        reviewer_name=interaction.user.display_name,
        event=event,
        skill_move=skill_move,
        weak_foot=weak_foot,
        strong_foot=strong_foot,
        skill_points=skill_points
    )
    
    review = bot.db.get_review(review_id)
    embed, file = create_review_embed(review)
    view = ReviewEditView(review_id, bot.db, config, interaction.user)
    
    if file:
        await interaction.followup.send(embed=embed, file=file, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view)

# =============================================
# === UPDATE IMAGE COMMAND ===
# =============================================
@bot.tree.command(name="update_image", description="Update the card image for an existing review (Owner Only)")
@app_commands.describe(
    review_id="The ID of the review to update",
    image="Upload the new player card image"
)
async def update_image(
    interaction: discord.Interaction,
    review_id: int,
    image: discord.Attachment
):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nOnly the bot owner can use this command.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer(ephemeral=True)
    
    review = bot.db.get_review(review_id)
    if not review:
        await interaction.followup.send(f"❌ Review `{review_id}` not found!", ephemeral=True)
        return
    
    success = bot.db.update_image(review_id, image.url)
    
    if success:
        embed = discord.Embed(
            title="✅ Image Updated!",
            description=f"Card image for review `{review_id}` (**{review['player_name']} {review['rating']}**) has been updated and stored permanently.",
            color=discord.Color.green()
        )
        embed.set_footer(text="The image will no longer expire!")
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send(f"❌ Failed to update image for review `{review_id}`. Check logs.", ephemeral=True)

# =============================================
# === TOP 10 COMMANDS ===
# =============================================

@bot.tree.command(name="top10", description="View the Top 10 players for any position with card images")
@app_commands.describe(position="Select the position")
@app_commands.choices(position=[
    app_commands.Choice(name="GK - Goalkeeper", value="GK"),
    app_commands.Choice(name="LB - Left Back", value="LB"),
    app_commands.Choice(name="RB - Right Back", value="RB"),
    app_commands.Choice(name="CB - Center Back", value="CB"),
    app_commands.Choice(name="CM - Center Midfielder", value="CM"),
    app_commands.Choice(name="CDM - Defensive Midfielder", value="CDM"),
    app_commands.Choice(name="CAM - Attacking Midfielder", value="CAM"),
    app_commands.Choice(name="LM - Left Midfielder", value="LM"),
    app_commands.Choice(name="RM - Right Midfielder", value="RM"),
    app_commands.Choice(name="LW - Left Winger", value="LW"),
    app_commands.Choice(name="RW - Right Winger", value="RW"),
    app_commands.Choice(name="ST - Striker", value="ST"),
])
async def top10_view(interaction: discord.Interaction, position: str):
    """View the gallery-style Top 10 for a position"""
    await interaction.response.defer()
    
    position_names = {
        "GK": "Goalkeeper", "LB": "Left Back", "RB": "Right Back", "CB": "Center Back",
        "CM": "Center Midfielder", "CDM": "Defensive Midfielder", "CAM": "Attacking Midfielder",
        "LM": "Left Midfielder", "RM": "Right Midfielder", "LW": "Left Winger",
        "RW": "Right Winger", "ST": "Striker"
    }
    
    entries = top10_db.get_top10(position)
    
    if not entries:
        embed = discord.Embed(
            title=f"🏆 Top 10 {position_names.get(position, position)}",
            description="No players added yet! Use `/top10_add` to add players.",
            color=0xF5A623
        )
        embed.set_footer(text="FELIX PR | Top 10 Leaderboard")
        await interaction.followup.send(embed=embed)
        return
    
    # Send header
    embed = discord.Embed(
        title=f"🏆 Top 10 {position_names.get(position, position)}",
        description=f"The best **{position}** players in FC Mobile\n━━━━━━━━━━━━━━━━━━",
        color=0xF5A623
    )
    embed.set_footer(text="FELIX PR | Top 10 Leaderboard")
    await interaction.followup.send(embed=embed)
    
    # Send each player with their card image
    for entry in entries:
        medal = "🥇" if entry['rank'] == 1 else "🥈" if entry['rank'] == 2 else "🥉" if entry['rank'] == 3 else f"#{entry['rank']}"
        
        if entry['rank'] == 1:
            color = 0xFFD700
        elif entry['rank'] == 2:
            color = 0xC0C0C0
        elif entry['rank'] == 3:
            color = 0xCD7F32
        else:
            color = 0x1E40AF
        
        player_embed = discord.Embed(
            title=f"{medal} {entry['player_name']}",
            description=f"**Card:** {entry['card_name']}\n**Rating:** {entry['rating']}",
            color=color
        )
        
        image_file = None
        if entry.get('image_data'):
            try:
                image_bytes = base64.b64decode(entry['image_data'])
                image_file = discord.File(io.BytesIO(image_bytes), filename=f"top10_{position}_{entry['rank']}.png")
                player_embed.set_image(url=f"attachment://top10_{position}_{entry['rank']}.png")
            except:
                pass
        
        if image_file:
            await interaction.channel.send(embed=player_embed, file=image_file)
        else:
            await interaction.channel.send(embed=player_embed)

@bot.tree.command(name="top10_add", description="Add/Update a player in the Top 10 (Owner/Admin Only)")
@app_commands.describe(
    position="Position to add to",
    rank="Rank number (1-10)",
    player_name="Player name",
    card_name="Card name (e.g., TOTY, UCL, Hero)",
    rating="Player rating (e.g., 117 OVR)",
    image="Upload the player card image"
)
@app_commands.choices(position=[
    app_commands.Choice(name="GK - Goalkeeper", value="GK"),
    app_commands.Choice(name="LB - Left Back", value="LB"),
    app_commands.Choice(name="RB - Right Back", value="RB"),
    app_commands.Choice(name="CB - Center Back", value="CB"),
    app_commands.Choice(name="CM - Center Midfielder", value="CM"),
    app_commands.Choice(name="CDM - Defensive Midfielder", value="CDM"),
    app_commands.Choice(name="CAM - Attacking Midfielder", value="CAM"),
    app_commands.Choice(name="LM - Left Midfielder", value="LM"),
    app_commands.Choice(name="RM - Right Midfielder", value="RM"),
    app_commands.Choice(name="LW - Left Winger", value="LW"),
    app_commands.Choice(name="RW - Right Winger", value="RW"),
    app_commands.Choice(name="ST - Striker", value="ST"),
])
async def top10_add(
    interaction: discord.Interaction,
    position: str,
    rank: int,
    player_name: str,
    card_name: str,
    rating: str,
    image: discord.Attachment
):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission to edit the Top 10!", ephemeral=True)
        return
    
    if rank < 1 or rank > 10:
        await interaction.response.send_message("❌ Rank must be between 1 and 10!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    success = top10_db.add_top10_entry(position, rank, player_name, card_name, rating, image.url, interaction.user.name)
    
    if success:
        embed = discord.Embed(
            title="✅ Top 10 Updated!",
            description=f"**{player_name}** added to **{position}** at rank **#{rank}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Card", value=card_name, inline=True)
        embed.add_field(name="Rating", value=rating, inline=True)
        embed.set_footer(text=f"Updated by {interaction.user.name}")
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed to add player!", ephemeral=True)

@bot.tree.command(name="top10_remove", description="Remove a player from the Top 10 (Owner/Admin Only)")
@app_commands.describe(
    position="Position to remove from",
    rank="Rank number to remove (1-10)"
)
@app_commands.choices(position=[
    app_commands.Choice(name="GK - Goalkeeper", value="GK"),
    app_commands.Choice(name="LB - Left Back", value="LB"),
    app_commands.Choice(name="RB - Right Back", value="RB"),
    app_commands.Choice(name="CB - Center Back", value="CB"),
    app_commands.Choice(name="CM - Center Midfielder", value="CM"),
    app_commands.Choice(name="CDM - Defensive Midfielder", value="CDM"),
    app_commands.Choice(name="CAM - Attacking Midfielder", value="CAM"),
    app_commands.Choice(name="LM - Left Midfielder", value="LM"),
    app_commands.Choice(name="RM - Right Midfielder", value="RM"),
    app_commands.Choice(name="LW - Left Winger", value="LW"),
    app_commands.Choice(name="RW - Right Winger", value="RW"),
    app_commands.Choice(name="ST - Striker", value="ST"),
])
async def top10_remove(interaction: discord.Interaction, position: str, rank: int):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    
    success = top10_db.remove_top10_entry(position, rank)
    
    if success:
        await interaction.response.send_message(f"✅ Removed rank **#{rank}** from **{position}** Top 10!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No player at rank **#{rank}** in **{position}**!", ephemeral=True)

@bot.tree.command(name="top10_swap", description="Swap two ranks in the Top 10 (Owner/Admin Only)")
@app_commands.describe(
    position="Position to swap in",
    rank1="First rank",
    rank2="Second rank"
)
@app_commands.choices(position=[
    app_commands.Choice(name="GK - Goalkeeper", value="GK"),
    app_commands.Choice(name="LB - Left Back", value="LB"),
    app_commands.Choice(name="RB - Right Back", value="RB"),
    app_commands.Choice(name="CB - Center Back", value="CB"),
    app_commands.Choice(name="CM - Center Midfielder", value="CM"),
    app_commands.Choice(name="CDM - Defensive Midfielder", value="CDM"),
    app_commands.Choice(name="CAM - Attacking Midfielder", value="CAM"),
    app_commands.Choice(name="LM - Left Midfielder", value="LM"),
    app_commands.Choice(name="RM - Right Midfielder", value="RM"),
    app_commands.Choice(name="LW - Left Winger", value="LW"),
    app_commands.Choice(name="RW - Right Winger", value="RW"),
    app_commands.Choice(name="ST - Striker", value="ST"),
])
async def top10_swap(interaction: discord.Interaction, position: str, rank1: int, rank2: int):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    
    if rank1 == rank2:
        await interaction.response.send_message("❌ Cannot swap the same rank!", ephemeral=True)
        return
    
    success = top10_db.swap_top10_entries(position, rank1, rank2)
    
    if success:
        await interaction.response.send_message(f"✅ Swapped rank **#{rank1}** and **#{rank2}** in **{position}**!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Failed to swap! Make sure both ranks have players.", ephemeral=True)

# =============================================
# === OTHER COMMANDS ===
# =============================================

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
    embed.set_footer(text=f"Role ID: {role.id}")
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
            embed = discord.Embed(
                title="🎭 Current Reviewer Role",
                description=f"**Role:** {role.mention}\n**Name:** {role.name}\n**ID:** `{role.id}`",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"⚠️ Reviewer role ID `{role_id}` is saved but the role no longer exists in this server!\n"
                "It may have been deleted. Use `/assign_reviewer_role` to set a new one.",
                ephemeral=True
            )
    else:
        await interaction.response.send_message(
            "❌ No reviewer role has been set yet.\nUse `/assign_reviewer_role @Role` to set one.",
            ephemeral=True
        )

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
    backup_path = None
    
    try:
        backup_path = bot.db.create_backup()
        if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
            files_to_send.append(discord.File(backup_path, filename="fcm_reviews.db"))
            print(f"✅ Backup file created: {backup_path} ({os.path.getsize(backup_path)} bytes)")
        else:
            print(f"⚠️ Backup file empty or missing")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        if os.path.exists('fcm_reviews.db'):
            db_size = os.path.getsize('fcm_reviews.db')
            if db_size > 0:
                files_to_send.append(discord.File('fcm_reviews.db'))
                print(f"⚠️ Using fallback direct file read: {db_size} bytes")
    
    if os.path.exists('top10.db'):
        files_to_send.append(discord.File('top10.db'))
    
    if os.path.exists('bot_config.json'):
        files_to_send.append(discord.File('bot_config.json'))
    
    if not files_to_send:
        await interaction.followup.send(
            "❌ **Backup Failed**\nNo files could be backed up.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="💾 Backup Complete",
        description=f"**Time:** <t:{int(datetime.now().timestamp())}:F>\n**Reviews:** {bot.db.get_review_count()}",
        color=discord.Color.green()
    )
    
    file_list = [f"• {f.filename}" for f in files_to_send]
    embed.add_field(name="Files", value="\n".join(file_list), inline=False)
    embed.add_field(name="💡 Restore", value="Use `/restore` and attach the files", inline=False)
    embed.set_footer(text="FCM Review Bot | Save these files!")
    
    await interaction.followup.send(embed=embed, files=files_to_send, ephemeral=True)
    
    if backup_path and os.path.exists(backup_path):
        try:
            os.remove(backup_path)
        except:
            pass

@bot.tree.command(name="restore", description="Restore database from backup files (Owner Only)")
@app_commands.describe(
    db_file="The fcm_reviews.db backup file",
    top10_file="The top10.db backup file (optional)",
    config_file="The bot_config.json backup file (optional)"
)
async def restore_command(
    interaction: discord.Interaction, 
    db_file: discord.Attachment,
    top10_file: discord.Attachment = None,
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
    
    if top10_file and top10_file.filename.endswith('.db'):
        try:
            file_data = await top10_file.read()
            with open('top10.db', 'wb') as f:
                f.write(file_data)
            restored.append("✅ top10.db")
        except Exception as e:
            failed.append(f"❌ top10.db: {str(e)}")
    
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

@bot.tree.command(name="dbcheck", description="Check database status (Owner Only)")
async def dbcheck_command(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(title="🔍 Database Status", color=discord.Color.blue())
    
    for db_name in ['fcm_reviews.db', 'top10.db']:
        exists = os.path.exists(db_name)
        size = os.path.getsize(db_name) if exists else 0
        embed.add_field(
            name=f"📁 {db_name}",
            value=f"Exists: {exists}\nSize: {size} bytes ({size/1024:.2f} KB)",
            inline=True
        )
    
    embed.add_field(name="Working Directory", value=f"`{os.getcwd()}`", inline=False)
    
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
    embed.add_field(name="Reviews DB Size", value=f"{db_size:.2f} KB", inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    top10_size = os.path.getsize('top10.db') / 1024 if os.path.exists('top10.db') else 0
    embed.add_field(name="Top 10 DB Size", value=f"{top10_size:.2f} KB", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show help for the review system")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 FCM Review Bot Help - FELIX PR",
        description="Complete guide to using the review system",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="⚽ `/review_outfield`",
        value="Create a review for outfield players\n**Stats:** PAC, SHO, PAS, DRI, DEF, PHY",
        inline=False
    )
    
    embed.add_field(
        name="🧤 `/review_gk`",
        value="Create a review for goalkeepers\n**Stats:** DIV, POS, HAN, REF, KIC, PHY",
        inline=False
    )
    
    embed.add_field(
        name="🏆 `/top10 <position>`",
        value="View gallery-style Top 10 leaderboard with card images",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Top 10 Management",
        value="`/top10_add` - Add player to Top 10\n`/top10_remove` - Remove player\n`/top10_swap` - Swap ranks",
        inline=False
    )
    
    embed.add_field(
        name="🖼️ `/update_image <id>`",
        value="Update card image for an existing review (Owner only)",
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
        value="Buttons: Edit Pros | Edit Cons | Edit Verdict | Edit Alternatives",
        inline=False
    )
    
    embed.add_field(
        name="🎭 Role Management",
        value="`/assign_reviewer_role @Role` | `/check_reviewer_role`",
        inline=False
    )
    
    embed.add_field(
        name="💾 `/backup` & `/restore`",
        value="Download/restore all data including Top 10 (Owner only)",
        inline=False
    )
    
    embed.add_field(
        name="📊 `/stats` & `/dbcheck`",
        value="View bot statistics and database status",
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
