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

def format_with_bullets(text: str) -> str:
    """Convert multi-line text to bullet points"""
    if not text or text in ["Not filled", "Pending", "None"]:
        return text
    lines = text.strip().split('\n')
    return '\n'.join([f"• {line}" if not line.startswith('•') and not line.startswith('-') else line for line in lines])

class ReviewEditView(discord.ui.View):
    def __init__(self, review_id: int, database, config, interaction_user: discord.User = None):
        super().__init__(timeout=None)
        self.review_id = review_id
        self.db = database
        self.config = config
        self.interaction_user = interaction_user
        
        # Show/hide buttons based on permission
        self.update_button_visibility()
    
    def has_permission(self, user_id: int) -> bool:
        """Check if user has permission to edit"""
        # Bot owner always has permission
        if user_id == 1214456066687893506:
            return True
        
        # Check if user is the original reviewer
        review = self.db.get_review(self.review_id)
        if review and str(user_id) == review.get('reviewer_id'):
            return True
        
        return False
    
    def update_button_visibility(self):
        """Update which buttons are visible based on user"""
        if not self.interaction_user:
            return
        
        has_perm = self.has_permission(self.interaction_user.id)
        
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id in ["edit_pros", "edit_cons", "edit_verdict", "edit_alternatives", "delete_review"]:
                    # Hide edit/delete buttons for non-reviewers
                    if not has_perm:
                        self.remove_item(child)
    
    async def check_permission(self, interaction: discord.Interaction) -> bool:
        """Full permission check with guild context"""
        # Bot owner always has permission
        if interaction.user.id == 1214456066687893506:
            return True
        
        # Check if user has reviewer role
        role_id = self.config.get_reviewer_role_id()
        if role_id and interaction.guild:
            role = interaction.guild.get_role(role_id)
            if role and role in interaction.user.roles:
                return True
        
        # Check if user is the original reviewer
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
        modal = EditModal("alternatives", self.review_id, self.db, self.config, "Enter alternative players (one per line)")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary, custom_id="refresh_review", row=2)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        review = self.db.get_review(self.review_id)
        if not review:
            await interaction.response.send_message("Review not found!", ephemeral=True)
            return
        
        embed = create_review_embed(review)
        view = ReviewEditView(self.review_id, self.db, self.config, interaction.user)
        await interaction.response.edit_message(embed=embed, view=view)
    
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
        
        # Get current value for pre-filling
        review = self.db.get_review(self.review_id)
        current_value = review.get(field, '') if review else ''
        if current_value in ['Not filled', 'Pending', 'None']:
            current_value = ''
        
        self.text_input = discord.ui.TextInput(
            label=placeholder,
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
            placeholder=placeholder,
            default=current_value
        )
        self.add_item(self.text_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        value = self.text_input.value if self.text_input.value else f"No {self.field} provided"
        self.db.update_review_field(self.review_id, self.field, value)
        
        review = self.db.get_review(self.review_id)
        if review:
            embed = create_review_embed(review)
            view = ReviewEditView(self.review_id, self.db, self.config, interaction.user)
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
    
    # Review Content with bullets
    pros = format_with_bullets(review.get('pros') or "Not filled")
    cons = format_with_bullets(review.get('cons') or "Not filled")
    verdict = format_with_bullets(review.get('verdict') or "Pending")
    alternatives = format_with_bullets(review.get('alternatives') or "None")
    
    embed.add_field(name="✅ Pros", value=pros, inline=True)
    embed.add_field(name="❌ Cons", value=cons, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # Spacer
    
    embed.add_field(name="⭐ Verdict", value=verdict, inline=True)
    embed.add_field(name="🔄 Alternatives", value=alternatives, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)  # Spacer
    
    # Footer
    embed.set_footer(
        text=f"Reviewed by {review.get('reviewer_name', 'Unknown')} • ID: {review.get('id', 'N/A')}",
        icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
    )
    
    # Set image
    if review.get('image_url'):
        embed.set_image(url=review['image_url'])
    
    return embed
