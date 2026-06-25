from PIL import Image, ImageDraw, ImageFont
import io
import base64
import os
from datetime import datetime

class Top10Poster:
    def __init__(self):
        self.width = 1080
        self.height = 1920
        self.content_width = int(self.width * 0.93)  # 93% for content
        self.brand_width = int(self.width * 0.07)    # 7% for branding
        self.canvas = None
        self.draw = None
        self.load_assets()
    
    def load_assets(self):
        """Load logo and fonts"""
        logo_path = "assets/logo.png"
        
        if os.path.exists(logo_path):
            self.logo = Image.open(logo_path).convert("RGBA")
        else:
            self.logo = None
        
        # Try DIN/Barlow Condensed, fallback to DejaVu
        self.font_title = self.get_font(52, bold=True)
        self.font_name_big = self.get_font(30, bold=True)
        self.font_name_med = self.get_font(20, bold=True)
        self.font_name_small = self.get_font(15, bold=True)
        self.font_name_tiny = self.get_font(11, bold=True)
        self.font_rating = self.get_font(22)
        self.font_rating_small = self.get_font(16)
        self.font_rank = self.get_font(18)
        self.font_bottom = self.get_font(18)
        self.font_brand_top = self.get_font(14, bold=True)
        self.font_brand_mid = self.get_font(18, bold=True)
        self.font_brand_bot = self.get_font(14, bold=True)
    
    def get_font(self, size, bold=False):
        """Get font with fallback - try DIN/Barlow first, then DejaVu"""
        font_names = [
            "DINCondensed-Bold.ttf", "BarlowCondensed-Bold.ttf",
            "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"
        ]
        
        for font_name in font_names:
            try:
                if bold and "Bold" not in font_name:
                    continue
                return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{font_name}", size)
            except:
                try:
                    return ImageFont.truetype(font_name, size)
                except:
                    continue
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
    
    def create_background(self):
        """Create EA SPORTS FC Mobile style gradient background"""
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Horizontal gradient: Cyan → Sky Blue → Royal Blue
        for x in range(self.width):
            ratio = x / self.width
            if ratio < 0.5:
                # Left to middle: #22D8E6 → #2E92F5
                r = int(0x22 + (0x2E - 0x22) * ratio * 2)
                g = int(0xD8 + (0x92 - 0xD8) * ratio * 2)
                b = int(0xE6 + (0xF5 - 0xE6) * ratio * 2)
            else:
                # Middle to right: #2E92F5 → #2C67E8
                r2 = (ratio - 0.5) * 2
                r = int(0x2E + (0x2C - 0x2E) * r2)
                g = int(0x92 + (0x67 - 0x92) * r2)
                b = int(0xF5 + (0xE8 - 0xF5) * r2)
            draw.line([(x, 0), (x, self.height)], fill=(r, g, b, 255))
        
        return img
    
    def draw_branding(self):
        """Draw the right-side branding column with rotated text"""
        brand_x = self.content_width + int(self.width * 0.02)  # 2% padding from right
        brand_color = '#FFFFFF'
        
        # Top Branding: EA SPORTS / FC MOBILE
        top_text = "EA SPORTS\nFC MOBILE"
        self.draw_rotated_text(top_text, brand_x, int(self.height * 0.10), 
                              self.font_brand_top, brand_color)
        
        # Middle Branding: TOP 10 PLAYER / SERIES
        mid_text = "TOP 10 PLAYER\nSERIES"
        self.draw_rotated_text(mid_text, brand_x, int(self.height * 0.50),
                              self.font_brand_mid, brand_color)
        
        # Bottom Branding: FCOmega / EAFC
        bot_text = "FCOmega\nEAFC"
        self.draw_rotated_text(bot_text, brand_x, int(self.height * 0.90),
                              self.font_brand_bot, brand_color)
    
    def draw_rotated_text(self, text, x, y, font, color):
        """Draw text rotated 90° clockwise at position"""
        # Create a temporary image for the text
        lines = text.split('\n')
        line_height = font.size + 4
        total_height = line_height * len(lines)
        
        # Measure max width
        max_width = 0
        for line in lines:
            bbox = self.draw.textbbox((0, 0), line, font=font)
            max_width = max(max_width, bbox[2] - bbox[0])
        
        # Create temp image
        temp_img = Image.new('RGBA', (max_width + 4, total_height + 4), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        
        for i, line in enumerate(lines):
            temp_draw.text((2, i * line_height + 2), line, fill=color, font=font)
        
        # Rotate 90° clockwise
        rotated = temp_img.rotate(270, expand=True)
        
        # Paste onto canvas
        paste_x = x - rotated.width // 2
        paste_y = y - rotated.height // 2
        self.canvas.paste(rotated, (paste_x, paste_y), rotated)
    
    def generate(self, entries: list, position: str, position_name: str) -> io.BytesIO:
        """Generate the Top 10 poster"""
        # Create gradient background
        self.canvas = self.create_background()
        self.draw = ImageDraw.Draw(self.canvas)
        
        # Sort entries by rank
        entries = sorted(entries, key=lambda e: int(e.get('rank', 0)))
        
        # Draw right-side branding
        self.draw_branding()
        
        # FELIX PR Logo (top-left in content area)
        if self.logo:
            logo_size = (70, 70)
            logo_resized = self.logo.resize(logo_size)
            self.canvas.paste(logo_resized, (30, 30), logo_resized)
        
        # Title (centered in content area)
        title = f"TOP 10 {position_name.upper()}"
        bbox = self.draw.textbbox((0, 0), title, font=self.font_title)
        title_x = self.content_width // 2 - (bbox[2] - bbox[0]) // 2
        self.draw.text((title_x, 35), title, fill='#FFFFFF', font=self.font_title)
        
        # Divider
        divider_y = 100
        self.draw.line([(40, divider_y), (self.content_width - 40, divider_y)], fill='#FFFFFF', width=2)
        
        # Position badge
        badge_w, badge_h = 160, 40
        badge_x = self.content_width // 2 - badge_w // 2
        self.draw.rounded_rectangle(
            [(badge_x, 110), (badge_x + badge_w, 150)],
            radius=20, fill='#FFFFFF')
        bbox = self.draw.textbbox((0, 0), position, font=self.font_rank)
        pos_w = bbox[2] - bbox[0]
        self.draw.text((self.content_width // 2 - pos_w // 2, 120), position, 
                      fill='#2C67E8', font=self.font_rank)
        
        # =============================================
        # === 1-2-3-4 PYRAMID LAYOUT (in content area) ===
        # =============================================
        
        center_x = self.content_width // 2
        
        # Row 1: Rank 1 - 1 card
        rank1 = next((e for e in entries if int(e.get('rank', 0)) == 1), None)
        if rank1:
            self.draw_rank_card(rank1, 1, center_x, 230, 280, 280, '#FFD700', 6, True)
        
        # Row 2: Ranks 2-3 - 2 cards
        row2_y = 600
        row2_card_size = 210
        row2_gap = 40
        row2_total_w = 2 * row2_card_size + row2_gap
        row2_start_x = center_x - row2_total_w // 2
        for i, r in enumerate([2, 3]):
            entry = next((e for e in entries if int(e.get('rank', 0)) == r), None)
            if entry:
                color = '#C0C0C0' if r == 2 else '#CD7F32'
                x = row2_start_x + i * (row2_card_size + row2_gap)
                self.draw_rank_card(entry, r, x + row2_card_size // 2, row2_y, 
                                  row2_card_size, row2_card_size, color, 4, True)
        
        # Row 3: Ranks 4-6 - 3 cards
        row3_y = 900
        row3_card_size = 170
        row3_gap = 30
        row3_total_w = 3 * row3_card_size + 2 * row3_gap
        row3_start_x = center_x - row3_total_w // 2
        for i, r in enumerate([4, 5, 6]):
            entry = next((e for e in entries if int(e.get('rank', 0)) == r), None)
            if entry:
                x = row3_start_x + i * (row3_card_size + row3_gap)
                self.draw_rank_card(entry, r, x + row3_card_size // 2, row3_y,
                                  row3_card_size, row3_card_size, '#FFFFFF', 3, False)
        
        # Row 4: Ranks 7-10 - 4 cards
        row4_y = 1160
        row4_card_size = 145
        row4_gap = 20
        row4_total_w = 4 * row4_card_size + 3 * row4_gap
        row4_start_x = center_x - row4_total_w // 2
        for i, r in enumerate([7, 8, 9, 10]):
            entry = next((e for e in entries if int(e.get('rank', 0)) == r), None)
            if entry:
                x = row4_start_x + i * (row4_card_size + row4_gap)
                self.draw_rank_card(entry, r, x + row4_card_size // 2, row4_y,
                                  row4_card_size, row4_card_size, '#FFFFFF', 3, False)
        
        # Bottom text
        bottom_text = f"FELIX PR | Generated {datetime.now().strftime('%B %d, %Y')}"
        bbox = self.draw.textbbox((0, 0), bottom_text, font=self.font_bottom)
        self.draw.text((center_x - (bbox[2] - bbox[0]) // 2, self.height - 45),
                      bottom_text, fill='#FFFFFF', font=self.font_bottom)
        
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
        name_y = y + card_h + 6
        max_name_w = card_w + 20
        font = self.get_font_for_name(name, max_name_w, 
                                     self.font_name_small if not is_top3 else self.font_name_med)
        name_color = '#FFFFFF' if not is_top3 else border_color
        self.draw.text((center_x, name_y), name, fill=name_color, font=font, anchor='mt')
        
        # Rating
        rating_y = name_y + font.size + 4
        medal = "⭐ " if is_top3 else ""
        rank_text = f"{medal}{self.get_medal_text(rank)}  •  {rating}"
        rating_font = self.font_rating_small if not is_top3 else self.font_rating
        rating_color = '#CCCCCC' if not is_top3 else '#FFFFFF'
        self.draw.text((center_x, rating_y), rank_text, fill=rating_color, font=rating_font, anchor='mt')
    
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
            radius=10,
            outline=color,
            width=width
        )
