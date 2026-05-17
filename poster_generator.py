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
        # Background
        bg_path = "assets/background.jpg"
        logo_path = "assets/logo.png"
        
        if os.path.exists(bg_path):
            self.background = Image.open(bg_path).resize((self.width, self.height))
        else:
            # Create gradient background if file missing
            self.background = self.create_gradient_bg()
        
        if os.path.exists(logo_path):
            self.logo = Image.open(logo_path).convert("RGBA")
        else:
            self.logo = None
        
        # Try to load fonts
        self.font_title = self.get_font(60, bold=True)
        self.font_name = self.get_font(36, bold=True)
        self.font_rating = self.get_font(28)
        self.font_rank = self.get_font(24)
        self.font_bottom = self.get_font(22)
    
    def get_font(self, size, bold=False):
        """Get font with fallback"""
        try:
            if bold:
                return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except:
            return ImageFont.load_default()
    
    def create_gradient_bg(self):
        """Create a dark gradient background"""
        from PIL import ImageDraw
        img = Image.new('RGB', (self.width, self.height), '#1a1a2e')
        draw = ImageDraw.Draw(img)
        for i in range(self.height):
            ratio = i / self.height
            r = int(26 + (15 - 26) * ratio)
            g = int(26 + (15 - 26) * ratio)
            b = int(46 + (25 - 46) * ratio)
            draw.line([(0, i), (self.width, i)], fill=(r, g, b))
        return img
    
    def generate(self, entries: list, position: str, position_name: str) -> io.BytesIO:
        """Generate the Top 10 poster"""
        self.canvas = self.background.copy()
        self.draw = ImageDraw.Draw(self.canvas)
        
        # Add logo (top right)
        if self.logo:
            logo_size = (100, 100)
            self.logo = self.logo.resize(logo_size)
            self.canvas.paste(self.logo, (self.width - 130, 30), self.logo)
        
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
        # Layout:
        #      [  #1  ]  (center, big)
        #   [ #2 ]  [ #3 ]  (smaller, side by side)
        
        # #1 - Large center card
        if len(entries) >= 1:
            card = self.load_card_image(entries[0])
            if card:
                card = card.resize((400, 400))
                x = self.width//2 - 200
                y = 260
                self.draw_card_border(x, y, 400, 400, '#FFD700', 8)
                self.canvas.paste(card, (x + 6, y + 6))
                # Name & rating
                name = entries[0].get('player_name', 'Unknown')
                rating = entries[0].get('rating', 'N/A')
                self.draw.text((self.width//2, 680), name, fill='#FFD700', font=self.font_name, anchor='mt')
                self.draw.text((self.width//2, 730), f"🥇 #{1}  •  {rating}", fill='#FFFFFF', font=self.font_rating, anchor='mt')
        
        # #2 & #3 - Side by side
        positions = [(200, 800), (self.width - 650, 800)]
        for i in range(1, min(3, len(entries))):
            card = self.load_card_image(entries[i])
            if card:
                card = card.resize((350, 350))
                x, y = positions[i-1]
                color = '#C0C0C0' if i == 1 else '#CD7F32'
                self.draw_card_border(x, y, 350, 350, color, 6)
                self.canvas.paste(card, (x + 5, y + 5))
                medal = "🥈" if i == 1 else "🥉"
                name = entries[i].get('player_name', 'Unknown')
                rating = entries[i].get('rating', 'N/A')
                self.draw.text((x + 175, 1165), name, fill=color, font=self.font_name, anchor='mt')
                self.draw.text((x + 175, 1210), f"{medal} #{i+1}  •  {rating}", fill='#FFFFFF', font=self.font_rating, anchor='mt')
    
    def draw_remaining(self, entries, position):
        """Draw #4-#10 in a 3-column grid"""
        start_y = 1280
        card_size = 180
        gap = 20
        
        for i, entry in enumerate(entries):
            rank = i + 4
            col = i % 3
            row = i // 3
            
            x = 120 + col * (card_size + gap + 100)
            y = start_y + row * (card_size + 80)
            
            card = self.load_card_image(entry)
            if card:
                card = card.resize((card_size, card_size))
                self.draw_card_border(x, y, card_size, card_size, '#444444', 4)
                self.canvas.paste(card, (x + 3, y + 3))
                name = entry.get('player_name', 'Unknown')
                rating = entry.get('rating', 'N/A')
                self.draw.text((x + card_size//2, y + card_size + 5), name[:15], fill='#FFFFFF', font=self.font_rank, anchor='mt')
                self.draw.text((x + card_size//2, y + card_size + 35), f"#{rank} • {rating}", fill='#AAAAAA', font=self.font_bottom, anchor='mt')
    
    def load_card_image(self, entry):
        """Load card image from base64 data"""
        try:
            image_data = entry.get('image_data')
            if image_data:
                image_bytes = base64.b64decode(image_data)
                return Image.open(io.BytesIO(image_bytes)).convert("RGBA")
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
