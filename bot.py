import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
from dotenv import load_dotenv
from database import Database, Top10Database, VoteDatabase
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
import urllib.request

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
ALLOWED_REVIEWERS = [1214456066687893506, 553418145063239684, 1202544947161468969,
    773492040339292190, 1284912012102598767, 1479410597387960371, 1417457966956810261,
    1075082413853642763, 933685309454057524]
CONFIG_FILE = "bot_config.json"

class BotConfig:
    def __init__(self):
        self.data = self.load()
    def load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        return {"reviewer_role_id": None}
    def save(self):
        with open(CONFIG_FILE, 'w') as f: json.dump(self.data, f)
    def get_reviewer_role_id(self):
        return self.data.get("reviewer_role_id")
    def set_reviewer_role_id(self, role_id: int):
        self.data["reviewer_role_id"] = role_id; self.save()

config = BotConfig()
top10_db = Top10Database()
poster_gen = Top10Poster()
vote_db = VoteDatabase()

# --- Review Search Dropdown ---
class ReviewSearchView(discord.ui.View):
    def __init__(self, matching_reviews: list, db: Database, config: BotConfig):
        super().__init__(timeout=60)
        self.db = db; self.config = config
        self.add_item(ReviewSelect(matching_reviews, db, config))

class ReviewSelect(discord.ui.Select):
    def __init__(self, matching_reviews: list, db: Database, config: BotConfig):
        self.db = db; self.config = config
        options = []
        for review in matching_reviews[:25]:
            status = "✅" if review.get('verdict') != 'Pending' else "⏳"
            event_text = f" [{review.get('event', '')}]" if review.get('event') else ""
            label = f"{review['player_name']} {review['rating']}{event_text}"
            if len(label) > 100: label = label[:97] + "..."
            description = f"By: {review['reviewer_name']}"
            if len(description) > 100: description = description[:97] + "..."
            options.append(discord.SelectOption(label=label, description=description, value=str(review['id']), emoji=status))
        super().__init__(placeholder="Select a review...", min_values=1, max_values=1, options=options)
    
    async def callback(self, interaction: discord.Interaction):
        review_id = int(self.values[0])
        review = self.db.get_review(review_id)
        if not review:
            await interaction.response.send_message("❌ Review not found!", ephemeral=True); return
        embed, file = create_review_embed(review)
        view = ReviewEditView(review_id, self.db, self.config, interaction.user)
        if file: await interaction.response.edit_message(embed=embed, attachments=[file], view=view)
        else: await interaction.response.edit_message(embed=embed, view=view)

class FCMReviewBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True; intents.members = True
        super().__init__(command_prefix='!', intents=intents)
        self.db = Database()
    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced commands for {self.user}")

bot = FCMReviewBot()

def is_allowed_reviewer(uid: int) -> bool: return uid in ALLOWED_REVIEWERS
def is_bot_owner(uid: int) -> bool: return uid == BOT_OWNER_ID
def can_edit_top10(uid: int) -> bool: return uid == BOT_OWNER_ID or uid in [553418145063239684]

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    print(f'📊 Reviews: {bot.db.get_review_count()}')
    print(f'🏆 Top 10: Active (4+4+4 DB Split)')
    print(f'🗳️ Voting System: Active')
    bot.loop.create_task(self_ping())

# =============================================
# === REVIEW COMMANDS ===
# =============================================

@bot.tree.command(name="review_outfield", description="Create outfield player review")
@app_commands.describe(
    player_name="Player name", rating="Rating (e.g., 97 OVR)", event="Event/Promo",
    pace="PACE", shooting="SHOOTING", passing="PASSING", dribbling="DRIBBLING",
    defending="DEFENDING", physical="PHYSICAL", skill_move="Skill Move (1-5)",
    weak_foot="Weak Foot (1-5)", strong_foot="Strong Foot", skill_points="Skill Points",
    image="Player card image")
@app_commands.choices(
    skill_move=[app_commands.Choice(name=f"{i} ★", value=i) for i in range(1,6)],
    weak_foot=[app_commands.Choice(name=f"{i} ★", value=i) for i in range(1,6)],
    strong_foot=[app_commands.Choice(name="Left", value="Left"), app_commands.Choice(name="Right", value="Right")])
async def review_outfield(
    interaction: discord.Interaction,
    player_name: str, rating: str, event: str,
    pace: str, shooting: str, passing: str, dribbling: str, defending: str, physical: str,
    skill_move: int, weak_foot: int, strong_foot: str,
    skill_points: str = "", image: discord.Attachment = None):
    
    if not is_allowed_reviewer(interaction.user.id):
        await interaction.response.send_message("❌ Not authorized!", ephemeral=True); return
    await interaction.response.defer()
    stats = f"**PAC:** {pace} | **SHO:** {shooting} | **PAS:** {passing}\n**DRI:** {dribbling} | **DEF:** {defending} | **PHY:** {physical}"
    img_url = image.url if image else None
    rid = bot.db.add_review(player_name, rating, img_url, stats, str(interaction.user.id),
        interaction.user.display_name, event, skill_move, weak_foot, strong_foot, skill_points)
    review = bot.db.get_review(rid)
    embed, file = create_review_embed(review)
    view = ReviewEditView(rid, bot.db, config, interaction.user)
    if file: await interaction.followup.send(embed=embed, file=file, view=view)
    else: await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="review_gk", description="Create goalkeeper review")
@app_commands.describe(
    player_name="Player name", rating="Rating (e.g., 96 OVR)", event="Event/Promo",
    diving="DIVING", positioning="POSITIONING", handling="HANDLING", reflexes="REFLEXES",
    kicking="KICKING", physical="PHYSICAL", skill_move="Skill Move (1-5)",
    weak_foot="Weak Foot (1-5)", strong_foot="Strong Foot", skill_points="Skill Points",
    image="Player card image")
@app_commands.choices(
    skill_move=[app_commands.Choice(name=f"{i} ★", value=i) for i in range(1,6)],
    weak_foot=[app_commands.Choice(name=f"{i} ★", value=i) for i in range(1,6)],
    strong_foot=[app_commands.Choice(name="Left", value="Left"), app_commands.Choice(name="Right", value="Right")])
async def review_gk(
    interaction: discord.Interaction,
    player_name: str, rating: str, event: str,
    diving: str, positioning: str, handling: str, reflexes: str, kicking: str, physical: str,
    skill_move: int, weak_foot: int, strong_foot: str,
    skill_points: str = "", image: discord.Attachment = None):
    
    if not is_allowed_reviewer(interaction.user.id):
        await interaction.response.send_message("❌ Not authorized!", ephemeral=True); return
    await interaction.response.defer()
    stats = f"**DIV:** {diving} | **POS:** {positioning} | **HAN:** {handling}\n**REF:** {reflexes} | **KIC:** {kicking} | **PHY:** {physical}"
    img_url = image.url if image else None
    rid = bot.db.add_review(player_name, rating, img_url, stats, str(interaction.user.id),
        interaction.user.display_name, event, skill_move, weak_foot, strong_foot, skill_points)
    review = bot.db.get_review(rid)
    embed, file = create_review_embed(review)
    view = ReviewEditView(rid, bot.db, config, interaction.user)
    if file: await interaction.followup.send(embed=embed, file=file, view=view)
    else: await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="update_image", description="Update card image (Owner Only)")
@app_commands.describe(review_id="Review ID", image="New card image")
async def update_image(interaction: discord.Interaction, review_id: int, image: discord.Attachment):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    review = bot.db.get_review(review_id)
    if not review:
        await interaction.followup.send(f"❌ Review `{review_id}` not found!", ephemeral=True); return
    if bot.db.update_image(review_id, image.url):
        await interaction.followup.send(f"✅ Image updated for `{review_id}`!", ephemeral=True)
    else: await interaction.followup.send("❌ Failed!", ephemeral=True)

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

@bot.tree.command(name="top10_add", description="Add player to Top 10 (Owner/Admin)")
@app_commands.describe(position="Position", rank="Rank (1-10)", player_name="Player name",
    rating="Rating (e.g., 117 OVR)", image="Card image")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_add(interaction: discord.Interaction, position: str, rank: int,
    player_name: str, rating: str, image: discord.Attachment):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ No permission!", ephemeral=True); return
    if rank < 1 or rank > 10:
        await interaction.response.send_message("❌ Rank 1-10!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    if top10_db.add_top10_entry(position, rank, player_name, "", rating, image.url, interaction.user.name):
        await interaction.followup.send(f"✅ **{player_name}** added to {position} #{rank}!", ephemeral=True)
    else: await interaction.followup.send("❌ Failed!", ephemeral=True)

@bot.tree.command(name="top10_remove", description="Remove player (Owner/Admin)")
@app_commands.describe(position="Position", rank="Rank to remove")
@app_commands.choices(position=ALL_POSITIONS)
async def top10_remove(interaction: discord.Interaction, position: str, rank: int):
    if not can_edit_top10(interaction.user.id):
        await interaction.response.send_message("❌ No permission!", ephemeral=True); return
    if top10_db.remove_top10_entry(position, rank):
        await interaction.response.send_message(f"✅ Removed #{rank} from {position}!", ephemeral=True)
    else: await interaction.response.send_message(f"❌ No player at #{rank}!", ephemeral=True)

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
    else: await interaction.response.send_message("❌ Failed!", ephemeral=True)

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

@bot.tree.command(name="top10_import", description="Import old top10.db into new 4+4+4 databases (Owner Only)")
@app_commands.describe(old_db="Upload your old top10.db file")
async def top10_import(interaction: discord.Interaction, old_db: discord.Attachment):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
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
# === VOTING COMMANDS ===
# =============================================

@bot.tree.command(name="vote_start", description="Start a Top 10 vote with player cards (Owner Only)")
@app_commands.describe(
    position="Position to vote for",
    player1_name="Player 1", player1_image="Card 1",
    player2_name="Player 2", player2_image="Card 2",
    player3_name="Player 3", player3_image="Card 3",
    player4_name="Player 4", player4_image="Card 4",
    player5_name="Player 5", player5_image="Card 5",
    player6_name="Player 6", player6_image="Card 6",
    player7_name="Player 7", player7_image="Card 7",
    player8_name="Player 8", player8_image="Card 8",
    player9_name="Player 9", player9_image="Card 9",
    player10_name="Player 10", player10_image="Card 10",
    player11_name="Player 11 (opt)", player11_image="Card 11 (opt)",
    player12_name="Player 12 (opt)", player12_image="Card 12 (opt)",
    player13_name="Player 13 (opt)", player13_image="Card 13 (opt)",
    player14_name="Player 14 (opt)", player14_image="Card 14 (opt)",
    player15_name="Player 15 (opt)", player15_image="Card 15 (opt)",
)
@app_commands.choices(position=ALL_POSITIONS)
async def vote_start(
    interaction: discord.Interaction, position: str,
    player1_name: str, player1_image: discord.Attachment,
    player2_name: str, player2_image: discord.Attachment,
    player3_name: str, player3_image: discord.Attachment,
    player4_name: str, player4_image: discord.Attachment,
    player5_name: str, player5_image: discord.Attachment,
    player6_name: str, player6_image: discord.Attachment,
    player7_name: str, player7_image: discord.Attachment,
    player8_name: str, player8_image: discord.Attachment,
    player9_name: str, player9_image: discord.Attachment,
    player10_name: str, player10_image: discord.Attachment,
    player11_name: str = "", player11_image: discord.Attachment = None,
    player12_name: str = "", player12_image: discord.Attachment = None,
    player13_name: str = "", player13_image: discord.Attachment = None,
    player14_name: str = "", player14_image: discord.Attachment = None,
    player15_name: str = "", player15_image: discord.Attachment = None,
):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    await interaction.response.defer()
    
    candidates = []
    for i in range(1, 16):
        name = locals().get(f"player{i}_name", "")
        image = locals().get(f"player{i}_image")
        if name and image:
            try:
                req = urllib.request.Request(image.url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    img_data = base64.b64encode(resp.read()).decode('utf-8')
                candidates.append((name, img_data))
            except:
                candidates.append((name, None))
    
    if len(candidates) < 10:
        await interaction.followup.send("❌ Need at least 10 players!", ephemeral=True); return
    
    vote_id = vote_db.start_vote(position, candidates, str(interaction.user.id))
    
    embed = discord.Embed(
        title=f"🗳️ Top 10 {PN.get(position, position)} - VOTE NOW!",
        description=f"**Vote ID:** `{vote_id}`\n\n"
                     "Use `/vote_cast` to rank each player.\n"
                     "Use `/vote_view` to see candidates.\n"
                     "Use `/vote_end` when done.",
        color=0xF5A623)
    embed.add_field(name="Candidates", value="\n".join([f"• {c[0]}" for c in candidates[:15]]), inline=False)
    embed.set_footer(text="FELIX PR | Voting System")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="vote_view", description="View vote candidates")
@app_commands.describe(vote_id="Vote session ID")
async def vote_view(interaction: discord.Interaction, vote_id: int):
    candidates = vote_db.get_vote_candidates(vote_id)
    if not candidates:
        await interaction.response.send_message("❌ Vote not found!", ephemeral=True); return
    embed = discord.Embed(title=f"🗳️ Vote #{vote_id} Candidates", color=0xF5A623)
    for i, c in enumerate(candidates, 1):
        embed.add_field(name=f"#{i}", value=c['candidate_name'], inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vote_cast", description="Cast your vote for a rank")
@app_commands.describe(vote_id="Vote session ID", rank="Rank (1-10)", candidate_name="Player name (exact)")
async def vote_cast(interaction: discord.Interaction, vote_id: int, rank: int, candidate_name: str):
    if rank < 1 or rank > 10:
        await interaction.response.send_message("❌ Rank must be 1-10!", ephemeral=True); return
    candidates = vote_db.get_vote_candidates(vote_id)
    candidate = next((c for c in candidates if c['candidate_name'].lower() == candidate_name.lower()), None)
    if not candidate:
        await interaction.response.send_message(f"❌ **{candidate_name}** not found!", ephemeral=True); return
    vote_db.cast_vote(vote_id, candidate['id'], rank, str(interaction.user.id), interaction.user.display_name)
    await interaction.response.send_message(f"✅ Voted **{candidate_name}** for **#{rank}**!", ephemeral=True)

@bot.tree.command(name="vote_end", description="End voting and generate Top 10 (Owner Only)")
@app_commands.describe(vote_id="Vote session ID")
async def vote_end(interaction: discord.Interaction, vote_id: int):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    await interaction.response.defer()
    
    results = vote_db.get_vote_results(vote_id)
    if not results['candidates']:
        await interaction.followup.send("❌ Vote not found!", ephemeral=True); return
    
    candidates = {c['id']: c for c in results['candidates']}
    winners = {}
    for rank in range(1, 11):
        tally = results['results'].get(rank, {})
        if tally:
            winner_id = max(tally, key=tally.get)
            winners[rank] = candidates[winner_id]
    
    if len(winners) < 10:
        await interaction.followup.send(f"❌ Not enough votes! Only {len(winners)} ranks voted.", ephemeral=True); return
    
    conn = sqlite3.connect('votes.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT position FROM active_votes WHERE id = ?", (vote_id,))
    row = cursor.fetchone()
    conn.close()
    position = row['position'] if row else "ST"
    
    for rank, candidate in winners.items():
        top10_db.add_top10_entry(position, rank, candidate['candidate_name'], "", "Voted", "", "Community Vote")
        db_name = top10_db.get_db_for_position(position)
        with sqlite3.connect(db_name) as conn2:
            conn2.cursor().execute(f"UPDATE top10_{position} SET image_data = ? WHERE rank = ?", (candidate['image_data'], rank))
            conn2.commit()
    
    vote_db.end_vote(vote_id)
    
    embed = discord.Embed(
        title=f"✅ Vote #{vote_id} Ended!", description=f"**Position:** {PN.get(position, position)}\n**Voters:** {results['total_voters']}\n\nSaved to Top 10!",
        color=0x2ecc71)
    for rank in range(1, 11):
        if rank in winners: embed.add_field(name=f"#{rank}", value=winners[rank]['candidate_name'], inline=True)
    embed.set_footer(text="Use /top10 to view the new poster!")
    await interaction.followup.send(embed=embed)

# =============================================
# === OTHER COMMANDS ===
# =============================================

@bot.tree.command(name="search", description="Search reviews")
@app_commands.describe(player_name="Player name")
async def search_command(interaction: discord.Interaction, player_name: str):
    reviews = bot.db.get_all_reviews()
    matching = [r for r in reviews if player_name.lower() in r['player_name'].lower()]
    if not matching:
        await interaction.response.send_message(f"❌ No reviews for **{player_name}**", ephemeral=True); return
    embed = discord.Embed(title=f"🔍 Search: '{player_name}'", description=f"Found **{len(matching)}** review(s).", color=0x3498db)
    await interaction.response.send_message(embed=embed, view=ReviewSearchView(matching, bot.db, config), ephemeral=False)

@bot.tree.command(name="assign_reviewer_role", description="Set reviewer role (Owner)")
@app_commands.describe(role="Role for editing")
async def assign_reviewer_role(interaction: discord.Interaction, role: discord.Role):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    config.set_reviewer_role_id(role.id)
    await interaction.response.send_message(f"✅ **{role.name}** can now edit reviews!")

@bot.tree.command(name="check_reviewer_role", description="Check reviewer role (Owner)")
async def check_reviewer_role(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    role_id = config.get_reviewer_role_id()
    if role_id:
        role = interaction.guild.get_role(role_id)
        if role: await interaction.response.send_message(f"🎭 **{role.name}** (`{role.id}`)", ephemeral=True)
        else: await interaction.response.send_message("⚠️ Role deleted!", ephemeral=True)
    else: await interaction.response.send_message("❌ No role set!", ephemeral=True)

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
    files = []
    for f in ['fcm_reviews.db','top10_1.db','top10_2.db','top10_3.db','votes.db','bot_config.json']:
        if os.path.exists(f) and os.path.getsize(f) > 0: files.append(discord.File(f))
    if not files:
        await interaction.followup.send("❌ No files!", ephemeral=True); return
    embed = discord.Embed(title="💾 Backup Complete", description=f"Reviews: {bot.db.get_review_count()}", color=0x2ecc71)
    embed.add_field(name="Files", value="\n".join([f"• {f.filename}" for f in files]), inline=False)
    embed.set_footer(text="FELIX PR | Use /restore to restore")
    await interaction.followup.send(embed=embed, files=files, ephemeral=True)

@bot.tree.command(name="restore", description="Restore from backup (Owner)")
@app_commands.describe(reviews_file="fcm_reviews.db", top10_1_file="top10_1.db (opt)",
    top10_2_file="top10_2.db (opt)", top10_3_file="top10_3.db (opt)",
    votes_file="votes.db (opt)", config_file="bot_config.json (opt)")
async def restore_command(interaction: discord.Interaction, reviews_file: discord.Attachment,
    top10_1_file: discord.Attachment = None, top10_2_file: discord.Attachment = None,
    top10_3_file: discord.Attachment = None, votes_file: discord.Attachment = None,
    config_file: discord.Attachment = None):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    restored, failed = [], []
    if reviews_file.filename.endswith('.db'):
        try:
            data = await reviews_file.read()
            with open('fcm_reviews.db','wb') as f: f.write(data)
            bot.db = Database()
            restored.append(f"✅ fcm_reviews.db ({bot.db.get_review_count()} reviews)")
        except Exception as e: failed.append(f"❌ fcm_reviews.db: {e}")
    else: failed.append("❌ reviews_file must be .db")
    for file_obj, name in [(top10_1_file,'top10_1.db'),(top10_2_file,'top10_2.db'),(top10_3_file,'top10_3.db'),(votes_file,'votes.db')]:
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

@bot.tree.command(name="dbcheck", description="Check database status (Owner)")
async def dbcheck_command(interaction: discord.Interaction):
    if not is_bot_owner(interaction.user.id):
        await interaction.response.send_message("❌ Owner only!", ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    embed = discord.Embed(title="🔍 Database Status", color=0x3498db)
    for db in ['fcm_reviews.db','top10_1.db','top10_2.db','top10_3.db','votes.db']:
        e = os.path.exists(db); s = os.path.getsize(db) if e else 0
        embed.add_field(name=f"📁 {db}", value=f"Exists: {e}\nSize: {s:,} bytes ({s/1024:.1f} KB)", inline=True)
    embed.add_field(name="📂 Working Dir", value=f"`{os.getcwd()}`", inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="stats", description="Bot statistics")
async def stats_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📊 FELIX PR Stats", color=0x2ecc71, timestamp=datetime.now())
    embed.add_field(name="Reviews", value=str(bot.db.get_review_count()), inline=True)
    rs = os.path.getsize('fcm_reviews.db')/1024 if os.path.exists('fcm_reviews.db') else 0
    embed.add_field(name="Reviews DB", value=f"{rs:.1f} KB", inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency*1000)}ms", inline=True)
    for db in ['top10_1.db','top10_2.db','top10_3.db','votes.db']:
        s = os.path.getsize(db)/1024 if os.path.exists(db) else 0
        embed.add_field(name=db, value=f"{s:.1f} KB", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show all commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 FELIX PR - Help", color=0x8B5CF6, description="FC Mobile Player Review Bot")
    embed.add_field(name="⚽ `/review_outfield`", value="Create outfield review", inline=False)
    embed.add_field(name="🧤 `/review_gk`", value="Create GK review", inline=False)
    embed.add_field(name="🏆 `/top10 <pos>`", value="View Top 10 poster", inline=False)
    embed.add_field(name="🔧 Top 10 Mgmt", value="`/top10_add` `/top10_remove` `/top10_swap`\n`/top10_debug` `/top10_clear` `/top10_import`", inline=False)
    embed.add_field(name="🗳️ Voting System", value="`/vote_start` `/vote_view` `/vote_cast` `/vote_end`", inline=False)
    embed.add_field(name="🖼️ `/update_image`", value="Update card image", inline=False)
    embed.add_field(name="🔍 `/search`", value="Search reviews", inline=False)
    embed.add_field(name="📋 `/list_reviews`", value="List all reviews", inline=False)
    embed.add_field(name="💾 `/backup` & `/restore`", value="Backup/restore all data", inline=False)
    embed.add_field(name="📊 `/stats` & `/dbcheck`", value="Statistics & diagnostics", inline=False)
    embed.set_footer(text="FELIX PR | 4+4+4 DB Split | Voting System")
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True; flask_thread.start()
    token = os.getenv('DISCORD_TOKEN')
    if not token: print("❌ DISCORD_TOKEN not set!"); exit(1)
    bot.run(token)
