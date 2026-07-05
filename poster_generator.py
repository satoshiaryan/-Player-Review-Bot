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
        
        self.font_title = self.get_font(52, bold=True)
        self.font_name_big = self.get_font(26, bold=True)
        self.font_name_small = self.get_font(20, bold=True)
        self.font_rating = self.get_font(22)
        self.font_rating_small = self.get_font(18)
        self.font_rank = self.get_font(18)
        self.font_bottom = self.get_font(18)
    
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
        return self.font_name_small
    
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
        
        if self.logo:
            logo_resized = self.logo.resize((80, 80))
            self.canvas.paste(logo_resized, (self.width - 110, 20), logo_resized)
        
        title = f"TOP 10 {position_name.upper()}"
        bbox = self.draw.textbbox((0, 0), title, font=self.font_title)
        self.draw.text((self.width//2 - (bbox[2]-bbox[0])//2, 28), title, fill='#FFFFFF', font=self.font_title)
        
        self.draw.line([(80, 90), (self.width - 80, 90)], fill='#FFFFFF', width=2)
        
        badge_w, badge_h = 160, 38
        self.draw.rounded_rectangle(
            [(self.width//2 - badge_w//2, 102), (self.width//2 + badge_w//2, 140)],
            radius=19, fill='#FFFFFF')
        bbox = self.draw.textbbox((0, 0), position, font=self.font_rank)
        self.draw.text((self.width//2 - (bbox[2]-bbox[0])//2, 111), position, fill='#1a1a2e', font=self.font_rank)
        
        CARD_SIZE = 260
        GAP_X = 30
        GAP_Y = 15
        START_Y = 175
        ROW_SPACING = CARD_SIZE + GAP_Y + 40
        center_x = self.width // 2
        
        rank1 = next((e for e in entries if int(e.get('rank', 0)) == 1), None)
        if rank1:
            self.draw_uniform_card(rank1, 1, center_x, START_Y, CARD_SIZE, '#FFD700', 6, True)
        
        row2_y = START_Y + ROW_SPACING
        row2_total_w = 2 * CARD_SIZE + GAP_X
        row2_start_x = center_x - row2_total_w // 2
        for i, r in enumerate([2, 3]):
            entry = next((e for e in entries if int(e.get('rank', 0)) == r), None)
            if entry:
                color = '#C0C0C0' if r == 2 else '#CD7F32'
                x = row2_start_x + i * (CARD_SIZE + GAP_X)
                self.draw_uniform_card(entry, r, x + CARD_SIZE // 2, row2_y, CARD_SIZE, color, 5, True)
        
        row3_y = row2_y + ROW_SPACING
        row3_total_w = 3 * CARD_SIZE + 2 * GAP_X
        row3_start_x = center_x - row3_total_w // 2
        for i, r in enumerate([4, 5, 6]):
            entry = next((e for e in entries if int(e.get('rank', 0)) == r), None)
            if entry:
                x = row3_start_x + i * (CARD_SIZE + GAP_X)
                self.draw_uniform_card(entry, r, x + CARD_SIZE // 2, row3_y, CARD_SIZE, '#FFFFFF', 4, False)
        
        row4_y = row3_y + ROW_SPACING
        row4_total_w = 4 * CARD_SIZE + 3 * GAP_X
        row4_start_x = center_x - row4_total_w // 2
        for i, r in enumerate([7, 8, 9, 10]):
            entry = next((e for e in entries if int(e.get('rank', 0)) == r), None)
            if entry:
                x = row4_start_x + i * (CARD_SIZE + GAP_X)
                self.draw_uniform_card(entry, r, x + CARD_SIZE // 2, row4_y, CARD_SIZE, '#FFFFFF', 3, False)
        
        bottom_text = f"FELIX PR | Generated {datetime.now().strftime('%B %d, %Y')}"
        bbox = self.draw.textbbox((0, 0), bottom_text, font=self.font_bottom)
        self.draw.text((self.width//2 - (bbox[2]-bbox[0])//2, self.height - 40), bottom_text, fill='#888888', font=self.font_bottom)
        
        output = io.BytesIO()
        self.canvas.save(output, format='PNG')
        output.seek(0)
        return output
    
    def draw_uniform_card(self, entry, rank, center_x, y, card_size, border_color, border_width, is_top3):
        card = self.load_card_image(entry)
        if not card: return
        
        card = card.resize((card_size, card_size))
        x = center_x - card_size // 2
        self.draw_card_border(x, y, card_size, card_size, border_color, border_width)
        self.canvas.paste(card, (x + border_width - 1, y + border_width - 1), card)
        
        # --- ENLARGED BADGE LOGIC (50x50) ---
        badges = []
        badge_target_size = (50, 50) 
        
        if entry.get('badge1_data'):
            b1 = self.load_badge_image(entry['badge1_data'], badge_target_size)
            if b1: badges.append(b1)
        if entry.get('badge2_data'):
            b2 = self.load_badge_image(entry['badge2_data'], badge_target_size)
            if b2: badges.append(b2)

        if badges:
            badge_x = x - (badge_target_size[0] // 2)
            center_y = y + (card_size // 2)
            if len(badges) == 1:
                badge_y = center_y - (badge_target_size[1] // 2)
                self.canvas.paste(badges[0], (badge_x, badge_y), badges[0])
            elif len(badges) == 2:
                spacing = 12 
                total_height = (badge_target_size[1] * 2) + spacing
                start_y = center_y - (total_height // 2)
                self.canvas.paste(badges[0], (badge_x, start_y), badges[0])
                self.canvas.paste(badges[1], (badge_x, start_y + badge_target_size[1] + spacing), badges[1])
        
        name = entry.get('player_name', 'Unknown')
        name_y = y + card_size + 6
        font = self.get_font_for_name(name, card_size + 40, self.font_name_big if is_top3 else self.font_name_small)
        self.draw.text((center_x, name_y), name, fill=(border_color if is_top3 else '#FFFFFF'), font=font, anchor='mt')
        
        rating_y = name_y + font.size + 4
        rank_text = f"{'⭐ ' if is_top3 else ''}{self.get_medal_text(rank)}  •  {entry.get('rating', 'N/A')}"
        self.draw.text((center_x, rating_y), rank_text, fill=('#FFFFFF' if is_top3 else '#CCCCCC'), font=(self.font_rating if is_top3 else self.font_rating_small), anchor='mt')

    def load_card_image(self, entry):
        try:
            if entry.get('image_data'):
                img = Image.open(io.BytesIO(base64.b64decode(entry['image_data'])))
                return img.convert('RGBA')
        except: return None
        
    def load_badge_image(self, base64_data, target_size):
        try:
            return Image.open(io.BytesIO(base64.b64decode(base64_data))).convert("RGBA").resize(target_size, Image.Resampling.LANCZOS)
        except: return None
    
    def draw_card_border(self, x, y, w, h, color, width):
        self.draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=12, outline=color, width=width)
