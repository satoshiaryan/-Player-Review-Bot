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
        
        # Load assets
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
        
        # Try to load fonts
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
        """Get text medal for rank"""
        if rank == 1:
            return "1st"
        elif rank == 2:
            return "2nd"
        elif rank == 3:
            return "3rd"
        else:
            return f"#{rank}"
    
    def get_font_for_name(self, name, max_width, base_font):
        """Get appropriate font size to fit name within max_width"""
        # Try base font first
        bbox = self.draw.textbbox((0, 0), name, font=base_font)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            return base_font
        
        # Try smaller fonts
        for font in [self.font_name_med, self.font_name_small, self.font_name_tiny]:
            bbox = self.draw.textbbox((0, 0), name, font=font)
            text_width = bbox[2] - bbox[0]
            if text_width <= max_width:
                return font
        
        return self.font_name_tiny
    
    def create_gradient_bg(self):
        """Create a dark gradient background"""
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
        
        # Add logo (top right)
        if self.logo:
            logo_size = (100, 100)
            logo_resized = self.logo.resize(logo_size)
            self.canvas.paste(logo_resized, (self.width - 130, 30), logo_resized)
        
        # Title
        title = f"TOP 10 {position_name.upper()}"
        bbox = self.draw.textbbox((0, 0), title, font=self.font_title)
        title_width = bbox[2] - bbox[0]
        self.draw.text((self.width//2 - title_width//2, 50), title, fill='#FFD700', font=self.font_title)
        
        # Divider line
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
        
        # Arrange cards based on rank
        if len(entries) > 0:
            self.draw_top3(entries, position)
        if len(entries) > 3:
            self.draw_remaining(entries[3:], position)
        
        # Bottom branding
        bottom_text = f"FELIX PR | Generated {datetime.now().strftime('%B %d, %Y')}"
        bbox = self.draw.textbbox((0, 0), bottom_text, font=self.font_bottom)
        bw = bbox[2] - bbox[0]
        self.draw.text((self.width//2 - bw//2, self.height - 60), bottom_text, fill='#888888', font=self.font_bottom)
        
        # Save to bytes
        output = io.BytesIO()
        self.canvas.save(output, format='PNG')
        output.seek(0)
        return output
    
    def draw_top3(self, entries, position):
        """Draw top 3 players (large cards)"""
        # #1 - Large center card
        if len(entries) >= 1:
            card = self.load_card_image(entries[0])
            if card:
                card = card.resize((400, 400))
                x = self.width//2 - 200
                y = 240
                self.draw_card_border(x, y, 400, 400, '#FFD700', 8)
                self.canvas.paste(card, (x + 6, y + 6), card)
                
                name = entries[0].get('player_name', 'Unknown')
                rating = entries[0].get('rating', 'N/A')
                # #1 has plenty of space - use big font, fallback to medium
                font = self.get_font_for_name(name, 380, self.font_name_big)
                self.draw.text((self.width//2, 660), name, fill='#FFD700', font=font, anchor='mt')
                self.draw.text((self.width//2, 710), f"⭐ 1st  •  {rating}", fill='#FFFFFF', font=self.font_rating, anchor='mt')
        
        # #2 & #3 - Side by side
        positions = [(200, 760), (self.width - 650, 760)]
        for i in range(1, min(3, len(entries))):
            card = self.load_card_image(entries[i])
            if card:
                card = card.resize((350, 350))
                x, y = positions[i-1]
                color = '#C0C0C0' if i == 1 else '#CD7F32'
                self.draw_card_border(x, y, 350, 350, color, 6)
                self.canvas.paste(card, (x + 5, y + 5), card)
                
                rank_text = self.get_medal_text(i + 1)
                name = entries[i].get('player_name', 'Unknown')
                rating = entries[i].get('rating', 'N/A')
                # #2/#3 have 330px width for name
                font = self.get_font_for_name(name, 330, self.font_name_med)
                self.draw.text((x + 175, 1125), name, fill=color, font=font, anchor='mt')
                self.draw.text((x + 175, 1165), f"⭐ {rank_text}  •  {rating}", fill='#FFFFFF', font=self.font_rating_small, anchor='mt')
    
    def draw_remaining(self, entries, position):
        """Draw #4-#10 in a flexible grid"""
        start_y = 1220
        card_size = 160
        gap_x = 30
        gap_y = 20
        
        num_remaining = len(entries)
        
        if num_remaining <= 7:
            cols_row1 = min(5, num_remaining)
            cols_row2 = num_remaining - cols_row1
            
            # Row 1
            for i in range(cols_row1):
                entry = entries[i]
                rank = i + 4
                total_w = cols_row1 * card_size + (cols_row1 - 1) * gap_x
                start_x = (self.width - total_w) // 2
                x = start_x + i * (card_size + gap_x)
                y = start_y
                self.draw_small_card(entry, x, y, card_size, rank)
            
            # Row 2 (centered)
            if cols_row2 > 0:
                total_w2 = cols_row2 * card_size + (cols_row2 - 1) * gap_x
                start_x2 = (self.width - total_w2) // 2
                for i in range(cols_row2):
                    entry = entries[cols_row1 + i]
                    rank = cols_row1 + i + 4
                    x = start_x2 + i * (card_size + gap_x)
                    y = start_y + card_size + gap_y + 50
                    self.draw_small_card(entry, x, y, card_size, rank)
        else:
            for i, entry in enumerate(entries):
                rank = i + 4
                col = i % 5
                row = i // 5
                total_w = min(num_remaining, 5) * card_size + (min(num_remaining, 5) - 1) * gap_x
                start_x = (self.width - total_w) // 2
                x = start_x + col * (card_size + gap_x)
                y = start_y + row * (card_size + gap_y + 50)
                self.draw_small_card(entry, x, y, card_size, rank)
    
    def draw_small_card(self, entry, x, y, card_size, rank):
        """Draw a single small card for ranks 4-10"""
        card = self.load_card_image(entry)
        if card:
            card = card.resize((card_size, card_size))
            self.draw_card_border(x, y, card_size, card_size, '#555555', 3)
            self.canvas.paste(card, (x + 3, y + 3), card)
            
            name = entry.get('player_name', 'Unknown')
            rating = entry.get('rating', 'N/A')
            
            # Use smaller font for long names (cards are only 160px wide)
            font = self.get_font_for_name(name, 150, self.font_name_small)
            
            self.draw.text((x + card_size//2, y + card_size + 5), name, fill='#FFFFFF', font=font, anchor='mt')
            self.draw.text((x + card_size//2, y + card_size + 30), f"#{rank} • {rating}", fill='#AAAAAA', font=self.font_bottom, anchor='mt')
    
    def load_card_image(self, entry):
        """Load card image from base64 data, preserving transparency"""
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
        """Draw a rounded rectangle border around a card"""
        self.draw.rounded_rectangle(
            [(x, y), (x + w, y + h)],
            radius=15,
            outline=color,
            width=width
        )
