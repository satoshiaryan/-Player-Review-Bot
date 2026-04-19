import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
from dotenv import load_dotenv
from database import Database
from views import ReviewEditView, create_review_embed
from utils import parse_stats_input

load_dotenv()

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
        
        # Register persistent views
        self.add_view(ReviewEditView(0, self.db))

bot = FCMReviewBot()

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'📊 Total reviews in database: {bot.db.get_review_count()}')
    print('------')

# Slash Commands
@bot.tree.command(name="review", description="Start a new player review")
@app_commands.describe(
    player_name="Name of the player",
    rating="Overall rating (e.g., 97 OVR)",
    stats="Base stats (e.g., PAC: 95, SHO: 88, PAS: 82)",
    image="Upload the player card image"
)
async def review_command(
    interaction: discord.Interaction,
    player_name: str,
    rating: str,
    stats: str,
    image: discord.Attachment
):
    await interaction.response.defer()
    
    # Create review in database
    review_id = bot.db.add_review(
        player_name=player_name,
        rating=rating,
        image_url=image.url,
        base_stats=stats,
        reviewer_id=str(interaction.user.id),
        reviewer_name=interaction.user.display_name
    )
    
    # Get the created review
    review = bot.db.get_review(review_id)
    
    # Create embed and view
    embed = create_review_embed(review)
    view = ReviewEditView(review_id, bot.db)
    
    await interaction.followup.send(embed=embed, view=view)

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
    
    for review in reviews[:25]:  # Discord limit of 25 fields
        status = "✅" if review['verdict'] != 'Pending' else "⏳"
        embed.add_field(
            name=f"{status} {review['player_name']} {review['rating']}",
            value=f"ID: `{review['id']}` | By: {review['reviewer_name']}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="get_review", description="Get a specific review by ID")
@app_commands.describe(review_id="The ID of the review to fetch")
async def get_review(interaction: discord.Interaction, review_id: int):
    review = bot.db.get_review(review_id)
    
    if not review:
        await interaction.response.send_message(f"Review #{review_id} not found!", ephemeral=True)
        return
    
    embed = create_review_embed(review)
    view = ReviewEditView(review_id, bot.db)
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="backup", description="Create and download a backup of all reviews")
@app_commands.default_permissions(administrator=True)
async def backup_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    backup_path = bot.db.create_backup()
    
    file = discord.File(backup_path, filename=f"fcm_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    
    await interaction.followup.send(
        content=f"✅ **Backup Created**\nTotal Reviews: {bot.db.get_review_count()}",
        file=file,
        ephemeral=True
    )
    
    # Clean up the temporary backup file
    os.remove(backup_path)

@bot.tree.command(name="restore", description="Restore database from a backup file")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(backup_file="The .db backup file to restore from")
async def restore_command(interaction: discord.Interaction, backup_file: discord.Attachment):
    if not backup_file.filename.endswith('.db'):
        await interaction.response.send_message("Please upload a valid .db file!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Save uploaded file temporarily
    temp_path = f"temp_restore_{datetime.now().timestamp()}.db"
    await backup_file.save(temp_path)
    
    # Attempt restore
    success = bot.db.restore_backup(temp_path)
    
    # Clean up temp file
    os.remove(temp_path)
    
    if success:
        # Reinitialize database connection
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
    embed.add_field(name="Database Size", value=f"{os.path.getsize('fcm_reviews.db') / 1024:.2f} KB", inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help_review", description="Show help for the review system")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 FCM Review Bot Help",
        description="Complete guide to using the review system",
        color=discord.Color.blurple()
    )
    
    embed.add_field(
        name="Creating a Review",
        value="Use `/review` command with player name, rating, stats, and card image",
        inline=False
    )
    
    embed.add_field(
        name="Editing Reviews",
        value="Click the buttons below any review to edit pros, cons, verdict, or alternatives",
        inline=False
    )
    
    embed.add_field(
        name="Backup System",
        value="Admins can use `/backup` to download database\nUse `/restore` with a backup file to restore",
        inline=False
    )
    
    embed.add_field(
        name="Stats Format",
        value="Use format: `PAC: 95, SHO: 88, PAS: 82, DRI: 91, DEF: 45, PHY: 78`",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ ERROR: No token found in .env file!")
        print("Create a .env file with DISCORD_TOKEN=your_token_here")
        exit(1)
    
    bot.run(token)
