from PIL import Image, ImageDraw, ImageFont
import io
import base64
import os
import urllib.request
from datetime import datetime

class Top10Poster:
    def __init__(self):
        self.width = 1200
        self.height = 1800
        self.canvas = None
        self.draw = None
        
        self.load_assets()
    
    def load_assets(self):
        """Load background and logo"""
        bg_path = "assets/background.jpg"
        logo_path = "assets/logo.png"
        
        if os.path.exists(bg_path):
            self.background = Image.open(bg_path).resize((self.width, self.height)).convert("RGBA")
        else:
            self.background = self.create_gradient_bg()
        
        if os.path.exists(logo_path):
            self.logo = Image.open(logo_path).convert("RGBA")
        else:
            self.logo = None
        
        self.font_title = self.get_font(60, bold=True)
        self.font_name_big = self.get_font(36, bold=True)
        self.font_name_med = self.get_font(24, bold=True)
        self.font_name_small = self.get_font(18, bold=True)
        self.font_name_tiny = self.get_font(14, bold=True)
        self.font_rating = self.get_font(28)
        self.font_rating_small = self.get_font(20)
        self.font_rank = self.get_font(20)
        self.font_bottom = self.get_font(22)
    
    def get_font(self, size, bold=False):
        """Get font with fallback"""
        try:
            if bold:
                return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except:
            try:
                if bold:
                    return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
                return ImageFont.truetype("DejaVuSans.ttf", size)
            except:
                return ImageFont.load_default()
    
    def get_medal_text(self, rank):
        if rank == 1: return "1st"
        elif rank == 2: return "2nd"
        elif rank == 3: return "3rd"
        else: return f"#{rank}"
    
    def get_font_for_name(self, name, max_width, base_font):
        bbox = self.draw.textbbox((0, 0), name, font=base_font)
        if bbox[2] - bbox[0] <= max_width:
            return base_font
        for font in [self.font_name_med, self.font_name_small, self.font_name_tiny]:
            bbox = self.draw.textbbox((0, 0), name, font=font)
            if bbox[2] - bbox[0] <= max_width:
                return font
        return self.font_name_tiny
    
    def create_gradient_bg(self):
        img = Image.new('RGBA', (self.width, self.height), (26, 26, 46, 255))
        draw = ImageDraw.Draw(img)
        for i in range(self.height):
            ratio = i / self.height
            r = int(26 + (15 - 26) * ratio)
            g = int(26 + (15 - 26) * ratio)
            b = int(46 + (25 - 46) * ratio)
            draw.line([(0, i), (self.width, i)], fill=(r, g, b, 255))
        return img
    
    def generate(self, entries: list, position: str, position_name: str) -> io.BytesIO:
        """Generate the Top 10 poster"""
        self.canvas = self.background.copy()
        self.draw = ImageDraw.Draw(self.canvas)
        
        # Sort entries by actual rank number
        entries = sorted(entries, key=lambda e: int(e.get('rank', 0)))
        
        # Logo
        if self.logo:
            logo_resized = self.logo.resize((100, 100))
            self.canvas.paste(logo_resized, (self.width - 130, 30), logo_resized)
        
        # Title
        title = f"TOP 10 {position_name.upper()}"
        bbox = self.draw.textbbox((0, 0), title, font=self.font_title)
        title_width = bbox[2] - bbox[0]
        self.draw.text((self.width//2 - title_width//2, 50), title, fill='#FFD700', font=self.font_title)
        
        # Divider
        self.draw.line([(100, 140), (self.width - 100, 140)], fill='#FFD700', width=3)
        
        # Position badge
        badge_w, badge_h = 200, 50
        self.draw.rounded_rectangle(
            [(self.width//2 - badge_w//2, 160), (self.width//2 + badge_w//2, 210)],
            radius=25, fill='#FFD700'
        )
        bbox = self.draw.textbbox((0, 0), position, font=self.font_rank)
        pos_w = bbox[2] - bbox[0]
        self.draw.text((self.width//2 - pos_w//2, 172), position, fill='#1a1a2e', font=self.font_rank)
        
        # Split by actual rank
        top3 = [e for e in entries if int(e.get('rank', 0)) <= 3]
        remaining = [e for e in entries if int(e.get('rank', 0)) > 3]
        
        if top3:
            self.draw_top3(top3, position)
        if remaining:
            self.draw_remaining(remaining, position)
        
        # Bottom text
        bottom_text = f"FELIX PR | Generated {datetime.now().strftime('%B %d, %Y')}"
        bbox = self.draw.textbbox((0, 0), bottom_text, font=self.font_bottom)
        bw = bbox[2] - bbox[0]
        self.draw.text((self.width//2 - bw//2, self.height - 60), bottom_text, fill='#888888', font=self.font_bottom)
        
        output = io.BytesIO()
        self.canvas.save(output, format='PNG')
        output.seek(0)
        return output
    
    def draw_top3(self, entries, position):
        """Draw top 3 by actual rank numbers"""
        entries = sorted(entries, key=lambda e: int(e.get('rank', 0)))
        
        # Find by actual rank
        rank1 = next((e for e in entries if int(e.get('rank', 0)) == 1), None)
        rank2 = next((e for e in entries if int(e.get('rank', 0)) == 2), None)
        rank3 = next((e for e in entries if int(e.get('rank', 0)) == 3), None)
        
        # #1 - Center
        if rank1:
            card = self.load_card_image(rank1)
            if card:
                card = card.resize((400, 400))
                x = self.width//2 - 200
                y = 240
                self.draw_card_border(x, y, 400, 400, '#FFD700', 8)
                self.canvas.paste(card, (x + 6, y + 6), card)
                name = rank1.get('player_name', 'Unknown')
                rating = rank1.get('rating', 'N/A')
                font = self.get_font_for_name(name, 380, self.font_name_big)
                self.draw.text((self.width//2, 660), name, fill='#FFD700', font=font, anchor='mt')
                self.draw.text((self.width//2, 710), f"⭐ 1st  •  {rating}", fill='#FFFFFF', font=self.font_rating, anchor='mt')
        
        # #2 & #3 - Side by side
        positions = [(200, 760), (self.width - 650, 760)]
        colors = ['#C0C0C0', '#CD7F32']
        for i, entry in enumerate([rank2, rank3]):
            if entry:
                card = self.load_card_image(entry)
                if card:
                    card = card.resize((350, 350))
                    x, y = positions[i]
                    self.draw_card_border(x, y, 350, 350, colors[i], 6)
                    self.canvas.paste(card, (x + 5, y + 5), card)
                    rank_text = self.get_medal_text(int(entry.get('rank', 0)))
                    name = entry.get('player_name', 'Unknown')
                    rating = entry.get('rating', 'N/A')
                    font = self.get_font_for_name(name, 330, self.font_name_med)
                    self.draw.text((x + 175, 1125), name, fill=colors[i], font=font, anchor='mt')
                    self.draw.text((x + 175, 1165), f"⭐ {rank_text}  •  {rating}", fill='#FFFFFF', font=self.font_rating_small, anchor='mt')
    
    def draw_remaining(self, entries, position):
        """Draw #4-#10 sorted by actual rank"""
        entries = sorted(entries, key=lambda e: int(e.get('rank', 0)))
        
        start_y = 1220
        card_size = 160
        gap_x = 30
        gap_y = 20
        
        num = len(entries)
        row1_count = min(5, num)
        row2_count = num - row1_count
        
        # Row 1
        total_w1 = row1_count * card_size + (row1_count - 1) * gap_x
        start_x1 = (self.width - total_w1) // 2
        for i in range(row1_count):
            entry = entries[i]
            rank = int(entry.get('rank', 0))
            x = start_x1 + i * (card_size + gap_x)
            y = start_y
            self.draw_small_card(entry, x, y, card_size, rank)
        
        # Row 2
        if row2_count > 0:
            total_w2 = row2_count * card_size + (row2_count - 1) * gap_x
            start_x2 = (self.width - total_w2) // 2
            for i in range(row2_count):
                entry = entries[row1_count + i]
                rank = int(entry.get('rank', 0))
                x = start_x2 + i * (card_size + gap_x)
                y = start_y + card_size + gap_y + 50
                self.draw_small_card(entry, x, y, card_size, rank)
    
    def draw_small_card(self, entry, x, y, card_size, rank):
        card = self.load_card_image(entry)
        if card:
            card = card.resize((card_size, card_size))
            self.draw_card_border(x, y, card_size, card_size, '#555555', 3)
            self.canvas.paste(card, (x + 3, y + 3), card)
            name = entry.get('player_name', 'Unknown')
            rating = entry.get('rating', 'N/A')
            font = self.get_font_for_name(name, 150, self.font_name_small)
            self.draw.text((x + card_size//2, y + card_size + 5), name, fill='#FFFFFF', font=font, anchor='mt')
            self.draw.text((x + card_size//2, y + card_size + 30), f"#{rank} • {rating}", fill='#AAAAAA', font=self.font_bottom, anchor='mt')
    
    def load_card_image(self, entry):
        try:
            image_data = entry.get('image_data')
            if image_data:
                image_bytes = base64.b64decode(image_data)
                img = Image.open(io.BytesIO(image_bytes))
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                return img
        except:
            pass
        return None
    
    def draw_card_border(self, x, y, w, h, color, width):
        self.draw.rounded_rectangle(
            [(x, y), (x + w, y + h)],
            radius=15,
            outline=color,
            width=width
        )
