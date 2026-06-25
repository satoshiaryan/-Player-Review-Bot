from PIL import Image, ImageDraw, ImageFont
import io
import base64
import os
from datetime import datetime

class Top10Poster:
    def __init__(self):
        self.width = 1200
        self.height = 1800
        self.canvas = None
        self.draw = None
        self.load_assets()
    
    def load_assets(self):
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
        
        self.font_title = self.get_font(56, bold=True)
        self.font_name_big = self.get_font(32, bold=True)
        self.font_name_med = self.get_font(22, bold=True)
        self.font_name_small = self.get_font(16, bold=True)
        self.font_name_tiny = self.get_font(12, bold=True)
        self.font_rating = self.get_font(24)
        self.font_rating_small = self.get_font(18)
        self.font_rank = self.get_font(20)
        self.font_bottom = self.get_font(20)
    
    def get_font(self, size, bold=False):
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
        self.canvas = self.background.copy()
        self.draw = ImageDraw.Draw(self.canvas)
        
        entries = sorted(entries, key=lambda e: int(e.get('rank', 0)))
        
        # Logo (top right)
        if self.logo:
            logo_resized = self.logo.resize((90, 90))
            self.canvas.paste(logo_resized, (self.width - 120, 25), logo_resized)
        
        # Title (WHITE)
        title = f"TOP 10 {position_name.upper()}"
        bbox = self.draw.textbbox((0, 0), title, font=self.font_title)
        self.draw.text((self.width//2 - (bbox[2]-bbox[0])//2, 40), title, fill='#FFFFFF', font=self.font_title)
        
        # Divider (WHITE)
        self.draw.line([(100, 110), (self.width - 100, 110)], fill='#FFFFFF', width=2)
        
        # Position badge
        badge_w, badge_h = 180, 45
        self.draw.rounded_rectangle(
            [(self.width//2 - badge_w//2, 125), (self.width//2 + badge_w//2, 170)],
            radius=22, fill='#FFFFFF')
        bbox = self.draw.textbbox((0, 0), position, font=self.font_rank)
        self.draw.text((self.width//2 - (bbox[2]-bbox[0])//2, 137), position, fill='#1a1a2e', font=self.font_rank)
        
        # =============================================
        # === 1-2-3-4 PYRAMID LAYOUT ===
        # =============================================
        
        # Row 1: Rank 1 (center, large) - 1 card
        rank1 = next((e for e in entries if int(e.get('rank', 0)) == 1), None)
        if rank1:
            self.draw_rank_card(rank1, 1, self.width//2, 260, 320, 320, '#FFD700', 7, True)
        
        # Row 2: Ranks 2-3 - 2 cards
        row2_y = 700
        row2_card_size = 240
        row2_gap = 40
        row2_total_w = 2 * row2_card_size + row2_gap
        row2_start_x = (self.width - row2_total_w) // 2
        for i, r in enumerate([2, 3]):
            entry = next((e for e in entries if int(e.get('rank', 0)) == r), None)
            if entry:
                color = '#C0C0C0' if r == 2 else '#CD7F32'
                x = row2_start_x + i * (row2_card_size + row2_gap)
                self.draw_rank_card(entry, r, x + row2_card_size//2, row2_y, row2_card_size, row2_card_size, color, 5, True)
        
        # Row 3: Ranks 4-6 - 3 cards
        row3_y = 1020
        row3_card_size = 190
        row3_gap = 35
        row3_total_w = 3 * row3_card_size + 2 * row3_gap
        row3_start_x = (self.width - row3_total_w) // 2
        for i, r in enumerate([4, 5, 6]):
            entry = next((e for e in entries if int(e.get('rank', 0)) == r), None)
            if entry:
                x = row3_start_x + i * (row3_card_size + row3_gap)
                self.draw_rank_card(entry, r, x + row3_card_size//2, row3_y, row3_card_size, row3_card_size, '#777777', 4, False)
        
        # Row 4: Ranks 7-10 - 4 cards
        row4_y = 1300
        row4_card_size = 160
        row4_gap = 25
        row4_total_w = 4 * row4_card_size + 3 * row4_gap
        row4_start_x = (self.width - row4_total_w) // 2
        for i, r in enumerate([7, 8, 9, 10]):
            entry = next((e for e in entries if int(e.get('rank', 0)) == r), None)
            if entry:
                x = row4_start_x + i * (row4_card_size + row4_gap)
                self.draw_rank_card(entry, r, x + row4_card_size//2, row4_y, row4_card_size, row4_card_size, '#555555', 3, False)
        
        # Bottom text
        bottom_text = f"FELIX PR | Generated {datetime.now().strftime('%B %d, %Y')}"
        bbox = self.draw.textbbox((0, 0), bottom_text, font=self.font_bottom)
        self.draw.text((self.width//2 - (bbox[2]-bbox[0])//2, self.height - 50), bottom_text, fill='#888888', font=self.font_bottom)
        
        output = io.BytesIO()
        self.canvas.save(output, format='PNG')
        output.seek(0)
        return output
    
    def draw_rank_card(self, entry, rank, center_x, y, card_w, card_h, border_color, border_width, is_top3):
        """Draw a single card centered at (center_x, y)"""
        card = self.load_card_image(entry)
        if not card:
            print(f"⚠️ No image for rank {rank}: {entry.get('player_name', 'Unknown')}")
            return
        
        name = entry.get('player_name', 'Unknown')
        rating = entry.get('rating', 'N/A')
        
        card = card.resize((card_w, card_h))
        x = center_x - card_w // 2
        
        # Card border
        self.draw_card_border(x, y, card_w, card_h, border_color, border_width)
        self.canvas.paste(card, (x + border_width - 1, y + border_width - 1), card)
        
        # Name & rating below card
        name_y = y + card_h + 8
        max_name_w = card_w + 20
        font = self.get_font_for_name(name, max_name_w, self.font_name_small if not is_top3 else self.font_name_med)
        self.draw.text((center_x, name_y), name, fill='#FFFFFF' if not is_top3 else border_color, font=font, anchor='mt')
        
        # Rating
        rating_y = name_y + font.size + 5
        medal = "⭐ " if is_top3 else ""
        rank_text = f"{medal}{self.get_medal_text(rank)}  •  {rating}"
        rating_font = self.font_rating_small if not is_top3 else self.font_rating
        self.draw.text((center_x, rating_y), rank_text, fill='#CCCCCC' if not is_top3 else '#FFFFFF', font=rating_font, anchor='mt')
    
    def load_card_image(self, entry):
        try:
            image_data = entry.get('image_data')
            if image_data:
                image_bytes = base64.b64decode(image_data)
                img = Image.open(io.BytesIO(image_bytes))
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                return img
            else:
                print(f"⚠️ No image_data for rank {entry.get('rank')}: {entry.get('player_name')}")
        except Exception as e:
            print(f"❌ Load failed for rank {entry.get('rank')}: {e}")
        return None
    
    def draw_card_border(self, x, y, w, h, color, width):
        self.draw.rounded_rectangle(
            [(x, y), (x + w, y + h)],
            radius=12,
            outline=color,
            width=width
        )
