import discord
from typing import Optional

class ReviewEditView(discord.ui.View):
    def __init__(self, review_id: int, database):
        super().__init__(timeout=None)  # No timeout for persistent view
        self.review_id = review_id
        self.db = database
    
    @discord.ui.button(label="Edit Pros", style=discord.ButtonStyle.green, custom_id="edit_pros", row=1)
    async def edit_pros(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditModal("pros", self.review_id, self.db, "Enter the pros (one per line)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Edit Cons", style=discord.ButtonStyle.red, custom_id="edit_cons", row=1)
    async def edit_cons(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditModal("cons", self.review_id, self.db, "Enter the cons (one per line)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Edit Verdict", style=discord.ButtonStyle.blurple, custom_id="edit_verdict", row=1)
    async def edit_verdict(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditModal("verdict", self.review_id, self.db, "Enter your final verdict")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Edit Alternatives", style=discord.ButtonStyle.grey, custom_id="edit_alternatives", row=1)
    async def edit_alternatives(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditModal("alternatives", self.review_id, self.db, "Enter alternative players")
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
        # Check if user is the original reviewer or has admin perms
        review = self.db.get_review(self.review_id)
        if str(interaction.user.id) != review.get('reviewer_id') and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You can only delete your own reviews!", ephemeral=True)
            return
        
        self.db.delete_review(self.review_id)
        await interaction.response.edit_message(content="🗑️ **Review Deleted**", embed=None, view=None)

class EditModal(discord.ui.Modal):
    def __init__(self, field: str, review_id: int, database, placeholder: str):
        super().__init__(title=f"Edit {field.title()}")
        self.field = field
        self.review_id = review_id
        self.db = database
        
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
        
        # Update the original message
        review = self.db.get_review(self.review_id)
        if review:
            embed = create_review_embed(review)
            view = ReviewEditView(self.review_id, self.db)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("Error: Review not found!", ephemeral=True)

def create_review_embed(review: dict) -> discord.Embed:
    """Create a formatted embed for a review"""
    embed = discord.Embed(
        title=f"📋 {review['player_name']} {review['rating']}",
        color=discord.Color.gold(),
        timestamp=datetime.fromisoformat(review['updated_at']) if review['updated_at'] else discord.utils.utcnow()
    )
    
    # Base Stats
    if review['base_stats']:
        embed.add_field(name="📊 Base Stats", value=review['base_stats'], inline=False)
    
    # Review Content
    embed.add_field(name="✅ Pros", value=review['pros'] or "Not filled", inline=True)
    embed.add_field(name="❌ Cons", value=review['cons'] or "Not filled", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # Spacer
    
    embed.add_field(name="⭐ Verdict", value=review['verdict'] or "Pending", inline=True)
    embed.add_field(name="🔄 Alternatives", value=review['alternatives'] or "None", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # Spacer
    
    # Footer with reviewer info
    embed.set_footer(
        text=f"Reviewed by {review['reviewer_name']} • ID: {review['id']}",
        icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
    )
    
    # Set image if exists
    if review['image_url']:
        embed.set_image(url=review['image_url'])
    
    return embed

# Import datetime here to avoid circular import
from datetime import datetime
