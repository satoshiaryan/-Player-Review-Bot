import discord
import json
import io
import os
from datetime import datetime

def format_stats(stats_dict: dict) -> str:
    """Format stats dictionary into readable string"""
    if not stats_dict:
        return "No stats provided"
    
    formatted = []
    for key, value in stats_dict.items():
        formatted.append(f"**{key}:** {value}")
    
    return "\n".join(formatted)

async def send_backup_to_discord(channel: discord.TextChannel, db):
    """Send database backup to a Discord channel"""
    backup_path = db.create_backup()
    
    file = discord.File(backup_path, filename=f"fcm_backup_{datetime.now().strftime('%Y%m%d')}.db")
    
    embed = discord.Embed(
        title="💾 Database Backup Created",
        description=f"**Total Reviews:** {db.get_review_count()}",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    
    await channel.send(embed=embed, file=file)
    
    # Clean up backup file after sending (optional)
    # os.remove(backup_path)

def parse_stats_input(stats_text: str) -> dict:
    """Parse stats from text input like 'PAC: 95, SHO: 88, PAS: 82'"""
    stats = {}
    for part in stats_text.split(','):
        if ':' in part:
            key, value = part.split(':', 1)
            stats[key.strip()] = value.strip()
    return stats
