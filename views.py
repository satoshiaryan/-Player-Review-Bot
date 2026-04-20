import discord
from typing import Optional
from datetime import datetime

def get_star_display(rating: int) -> str:
    """Convert number to star display"""
    if rating <= 0:
        return "N/A"
    stars = "★" * rating
    empty = "☆" * (5 - rating)
    return f"{stars}{empty} ({rating}/5)"

class ReviewEditView(discord.ui.View):
    def __init__(self, review_id: int, database, config):
        super().__init__(timeout=None)
        self.review_id = review_id
        self.db = database
        self.config = config
    
    async def check_permission(self, interaction: discord.Interaction) -> bool:
        """Check if user has permission to edit"""
        if interaction.user.id == 1214456066687893506:
            return True
        
        role_id = self.config.get_reviewer_role_id()
        if role_id:
            role = interaction.guild.get_role(role_id)
            if role and role in interaction.user.roles:
                return True
        
        review = self.db.get_review(self.review_id)
        if review and str(interaction.user.id) == review.get('reviewer_id'):
            return True
        
        return False
    
    async def handle_no_permission(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "❌ **Permission Denied**\nYou don't have permission to edit this review.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Edit Pros", style=discord.ButtonStyle.green, custom_id="edit_pros", row=1)
    async def edit_pros(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permission(interaction):
            return await self.handle_no_permission(interaction)
        modal = EditModal("pros", self.review_id, self.db, self.config, "Enter the pros (one per line)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Edit Cons", style=discord.ButtonStyle.red, custom_id="edit_cons", row=1)
    async def edit_cons(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permission(interaction):
            return await self.handle_no_permission(interaction)
        modal = EditModal("cons", self.review_id, self.db, self.config, "Enter the cons (one per line)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Edit Verdict", style=discord.ButtonStyle.blurple, custom_id="edit_verdict", row=1)
    async def edit_verdict(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permission(interaction):
            return await self.handle_no_permission(interaction)
        modal = EditModal("verdict", self.review_id, self.db, self.config, "Enter your final verdict")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Edit Alternatives", style=discord.ButtonStyle.grey, custom_id="edit_alternatives", row=1)
    async def edit_alternatives(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permission(interaction):
            return await self.handle_no_permission(interaction)
        modal = EditModal("alternatives", self.review_id, self.db, self.config, "Enter alternative players")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary, custom_id="refresh_review", row=2)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        review = self.db.get_review(self.review_id)
        if not review:
            await interaction.response.send_message("Review not found!", ephemeral=True)
            return
        
        embed = create_review_embed(review)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, custom_id="delete_review", row=2)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permission(interaction):
            return await self.handle_no_permission(interaction)
        
        self.db.delete_review(self.review_id)
        await interaction.response.edit_message(content="🗑️ **Review Deleted**", embed=None, view=None)

class EditModal(discord.ui.Modal):
    def __init__(self, field: str, review_id: int, database, config, placeholder: str):
        super().__init__(title=f"Edit {field.title()}")
        self.field = field
        self.review_id = review_id
        self.db = database
        self.config = config
        
        self.text_input = discord.ui.TextInput(
            label=placeholder,
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
            placeholder=placeholder
        )
        self.add_item(self.text_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        value = self.text_input.value if self.text_input.value else f"No {self.field} provided"
        self.db.update_review_field(self.review_id, self.field, value)
        
        review = self.db.get_review(self.review_id)
        if review:
            embed = create_review_embed(review)
            view = ReviewEditView(self.review_id, self.db, self.config)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("Error: Review not found!", ephemeral=True)

def create_review_embed(review: dict) -> discord.Embed:
    """Create a formatted embed for a review"""
    # Build title
    title = f"📋 {review['player_name']} {review['rating']}"
    if review.get('event'):
        title += f" - {review['event']}"
    
    embed = discord.Embed(
        title=title,
        color=discord.Color.gold(),
        timestamp=datetime.fromisoformat(review['updated_at']) if review.get('updated_at') else discord.utils.utcnow()
    )
    
    # Player Info Section (Skill Move, Weak Foot, Strong Foot)
    skill_move = review.get('skill_move', 0)
    weak_foot = review.get('weak_foot', 0)
    strong_foot = review.get('strong_foot', 'N/A')
    
    player_info = f"**Skill Move:** {get_star_display(skill_move)}\n"
    player_info += f"**Weak Foot:** {get_star_display(weak_foot)}\n"
    player_info += f"**Strong Foot:** {strong_foot}"
    
    embed.add_field(name="⚽ Player Info", value=player_info, inline=False)
    
    # Base Stats
    if review.get('base_stats'):
        embed.add_field(name="📊 Base Stats", value=review['base_stats'], inline=False)
    
    # Review Content
    embed.add_field(name="✅ Pros", value=review.get('pros') or "Not filled", inline=True)
    embed.add_field(name="❌ Cons", value=review.get('cons') or "Not filled", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    
    embed.add_field(name="⭐ Verdict", value=review.get('verdict') or "Pending", inline=True)
    embed.add_field(name="🔄 Alternatives", value=review.get('alternatives') or "None", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    
    # Footer
    embed.set_footer(
        text=f"Reviewed by {review.get('reviewer_name', 'Unknown')} • ID: {review.get('id', 'N/A')}",
        icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
    )
    
    # Set image
    if review.get('image_url'):
        embed.set_image(url=review['image_url'])
    
    return embed
