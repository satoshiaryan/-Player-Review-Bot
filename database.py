import sqlite3
import shutil
import os
import base64
import urllib.request
from datetime import datetime
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, db_path: str = "fcm_reviews.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    rating TEXT,
                    event TEXT DEFAULT "",
                    image_url TEXT,
                    image_data TEXT DEFAULT NULL,
                    base_stats TEXT,
                    skill_move INTEGER DEFAULT 0,
                    weak_foot INTEGER DEFAULT 0,
                    strong_foot TEXT DEFAULT "",
                    skill_points TEXT DEFAULT "",
                    pros TEXT DEFAULT 'Not filled',
                    cons TEXT DEFAULT 'Not filled',
                    verdict TEXT DEFAULT 'Pending',
                    alternatives TEXT DEFAULT 'None',
                    reviewer_id TEXT,
                    reviewer_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    
    # --- Add standard review methods here ---
    def add_review(self, *args, **kwargs): pass
    def update_review_field(self, *args, **kwargs): pass
    def update_image(self, *args, **kwargs): pass
    def get_review(self, *args, **kwargs): pass
    def get_all_reviews(self, *args, **kwargs): pass
    def delete_review(self, *args, **kwargs): pass
    def create_backup(self, *args, **kwargs): pass
    def restore_backup(self, *args, **kwargs): pass
    def get_review_count(self) -> int: return 0

# =============================================
# === TOP 10 DATABASE (SPLIT INTO 3 FILES) ===
# =============================================
class Top10Database:
    DB_MAP = {
        "top10_1.db": ["GK", "LB", "RB", "CB"],
        "top10_2.db": ["CM", "CDM", "CAM", "LM"],
        "top10_3.db": ["RM", "LW", "RW", "ST"],
    }
    
    def __init__(self):
        self.migrate_all_dbs()
    
    def get_db_for_position(self, position: str) -> str:
        for db_name, positions in self.DB_MAP.items():
            if position in positions:
                return db_name
        return "top10_1.db"
    
    def migrate_all_dbs(self):
        """Ensures all tables exist and have badge columns."""
        for db_name, positions in self.DB_MAP.items():
            with sqlite3.connect(db_name) as conn:
                cursor = conn.cursor()
                for pos in positions:
                    table = f"top10_{pos}"
                    # Create table if it doesn't exist
                    cursor.execute(f'''CREATE TABLE IF NOT EXISTS {table}
                                     (rank INTEGER PRIMARY KEY, player_name TEXT, card_name TEXT, 
                                      rating TEXT, image_url TEXT, image_data TEXT DEFAULT NULL, 
                                      updated_by TEXT, updated_at TIMESTAMP)''')
                    
                    # Force add new badge columns if they are missing
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in cursor.fetchall()]
                    for col in ['badge1_url', 'badge1_data', 'badge2_url', 'badge2_data']:
                        if col not in columns:
                            try:
                                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT NULL')
                            except: pass
                conn.commit()

    def _download_to_base64(self, url: str) -> Optional[str]:
        if not url: return None
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return base64.b64encode(response.read()).decode('utf-8')
        except: return None
    
    def get_top10(self, position: str):
        db_name = self.get_db_for_position(position)
        with sqlite3.connect(db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM top10_{position} ORDER BY CAST(rank AS INTEGER)")
            return [dict(row) for row in cursor.fetchall()]
    
    def add_top10_entry(self, position: str, rank: int, player_name: str, card_name: str, rating: str, image_url: str, updated_by: str, badge1_url: str = None, badge2_url: str = None) -> bool:
        img_b64 = self._download_to_base64(image_url)
        b1_b64 = self._download_to_base64(badge1_url)
        b2_b64 = self._download_to_base64(badge2_url)
        
        with sqlite3.connect(self.get_db_for_position(position)) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''INSERT OR REPLACE INTO top10_{position} 
                             (rank, player_name, card_name, rating, image_url, image_data, badge1_url, badge1_data, badge2_url, badge2_data, updated_by, updated_at)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (rank, player_name, card_name, rating, image_url, img_b64, badge1_url, b1_b64, badge2_url, b2_b64, updated_by, datetime.now().isoformat()))
            conn.commit()
        return True

    def update_top10_badges(self, position: str, rank: int, badge1_url: str = None, badge2_url: str = None) -> bool:
        b1_b64 = self._download_to_base64(badge1_url)
        b2_b64 = self._download_to_base64(badge2_url)
        with sqlite3.connect(self.get_db_for_position(position)) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''UPDATE top10_{position} SET badge1_url=?, badge1_data=?, badge2_url=?, badge2_data=?, updated_at=? WHERE rank=?''',
                           (badge1_url, b1_b64, badge2_url, b2_b64, datetime.now().isoformat(), rank))
            conn.commit()
            return cursor.rowcount > 0
    
    def remove_top10_entry(self, position: str, rank: int) -> bool:
        with sqlite3.connect(self.get_db_for_position(position)) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM top10_{position} WHERE rank = ?", (rank,))
            conn.commit()
            return cursor.rowcount > 0
    
    def swap_top10_entries(self, position: str, rank1: int, rank2: int) -> bool:
        db_name = self.get_db_for_position(position)
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cols = "player_name, card_name, rating, image_url, image_data, badge1_url, badge1_data, badge2_url, badge2_data"
            cursor.execute(f"SELECT {cols} FROM top10_{position} WHERE rank = ?", (rank1,))
            e1 = cursor.fetchone()
            cursor.execute(f"SELECT {cols} FROM top10_{position} WHERE rank = ?", (rank2,))
            e2 = cursor.fetchone()
            if e1 and e2:
                q = f'''UPDATE top10_{position} SET player_name=?, card_name=?, rating=?, image_url=?, image_data=?, 
                        badge1_url=?, badge1_data=?, badge2_url=?, badge2_data=?, updated_by=?, updated_at=? WHERE rank=?'''
                cursor.execute(q, (*e2, "system", datetime.now().isoformat(), rank1))
                cursor.execute(q, (*e1, "system", datetime.now().isoformat(), rank2))
                conn.commit()
                return True
        return False
