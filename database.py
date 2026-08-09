import sqlite3
import shutil
import os
import base64
import urllib.request
from datetime import datetime
from typing import Optional, List, Dict, Any

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
        self.init_all_db()
    
    def get_db_for_position(self, position: str) -> str:
        for db_name, positions in self.DB_MAP.items():
            if position in positions:
                return db_name
        return "top10_1.db"
    
    def init_all_db(self):
        """Ensures all tables exist and have required columns."""
        for db_name, positions in self.DB_MAP.items():
            with sqlite3.connect(db_name) as conn:
                cursor = conn.cursor()
                for pos in positions:
                    table = f"top10_{pos}"
                    cursor.execute(f'''CREATE TABLE IF NOT EXISTS {table}
                                     (rank INTEGER PRIMARY KEY, player_name TEXT, card_name TEXT, 
                                      rating TEXT, image_url TEXT, image_data TEXT DEFAULT NULL, 
                                      updated_by TEXT, updated_at TIMESTAMP)''')
                    
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
    
    def add_top10_entry(self, position: str, rank: int, player_name: str, card_name: str, 
                        rating: str, image_url: str, updated_by: str, 
                        badge1_url: str = None, badge2_url: str = None) -> bool:
        img_b64 = self._download_to_base64(image_url)
        b1_b64 = self._download_to_base64(badge1_url)
        b2_b64 = self._download_to_base64(badge2_url)
        
        with sqlite3.connect(self.get_db_for_position(position)) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''INSERT OR REPLACE INTO top10_{position} 
                             (rank, player_name, card_name, rating, image_url, image_data, 
                              badge1_url, badge1_data, badge2_url, badge2_data, updated_by, updated_at)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (rank, player_name, card_name, rating, image_url, img_b64, 
                            badge1_url, b1_b64, badge2_url, b2_b64, updated_by, datetime.now().isoformat()))
            conn.commit()
        return True

    def update_top10_badges(self, position: str, rank: int, 
                            badge1_url: str = None, badge2_url: str = None) -> bool:
        b1_b64 = self._download_to_base64(badge1_url)
        b2_b64 = self._download_to_base64(badge2_url)
        with sqlite3.connect(self.get_db_for_position(position)) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''UPDATE top10_{position} 
                             SET badge1_url=?, badge1_data=?, badge2_url=?, badge2_data=?, updated_at=? 
                             WHERE rank=?''',
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
                q = f'''UPDATE top10_{position} SET player_name=?, card_name=?, rating=?, 
                        image_url=?, image_data=?, badge1_url=?, badge1_data=?, 
                        badge2_url=?, badge2_data=?, updated_by=?, updated_at=? WHERE rank=?'''
                cursor.execute(q, (*e2, "system", datetime.now().isoformat(), rank1))
                cursor.execute(q, (*e1, "system", datetime.now().isoformat(), rank2))
                conn.commit()
                return True
        return False


# =============================================
# === SHARD DATABASE ===
# =============================================
class ShardDatabase:
    def __init__(self, db_path: str = "shards.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS shard_players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    ovr TEXT,
                    shard_cost INTEGER DEFAULT 0,
                    value_tier TEXT DEFAULT "B",
                    week INTEGER DEFAULT 1,
                    image_url TEXT,
                    image_data TEXT DEFAULT NULL,
                    added_by TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Check for missing columns in existing DB
            cursor.execute("PRAGMA table_info(shard_players)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'image_data' not in columns:
                cursor.execute('ALTER TABLE shard_players ADD COLUMN image_data TEXT DEFAULT NULL')
            if 'week' not in columns:
                cursor.execute('ALTER TABLE shard_players ADD COLUMN week INTEGER DEFAULT 1')
            conn.commit()
    
    def _download_to_base64(self, url: str) -> Optional[str]:
        if not url: return None
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return base64.b64encode(response.read()).decode('utf-8')
        except: return None
    
    def add_player(self, player_name: str, ovr: str, shard_cost: int, value_tier: str,
                   week: int, image_url: str, added_by: str) -> bool:
        img_b64 = self._download_to_base64(image_url)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO shard_players (player_name, ovr, shard_cost, value_tier, week, image_url, image_data, added_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (player_name, ovr, shard_cost, value_tier, week, image_url, img_b64, added_by))
            conn.commit()
            return True
    
    def get_players_by_week(self, week: int) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM shard_players 
                WHERE week = ? 
                ORDER BY CASE value_tier 
                    WHEN 'S' THEN 1 
                    WHEN 'A' THEN 2 
                    WHEN 'B' THEN 3 
                    WHEN 'C' THEN 4 
                    WHEN 'D' THEN 5 
                END, shard_cost ASC
            """, (week,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_weeks(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT week FROM shard_players ORDER BY week DESC")
            return [row[0] for row in cursor.fetchall()]
    
    def get_player(self, player_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM shard_players WHERE id = ?", (player_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def remove_player(self, player_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM shard_players WHERE id = ?", (player_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def remove_week(self, week: int) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM shard_players WHERE week = ?", (week,))
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM shard_players WHERE week = ?", (week,))
            conn.commit()
            return count
    
    def get_count(self, week: int = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if week:
                cursor.execute("SELECT COUNT(*) FROM shard_players WHERE week = ?", (week,))
            else:
                cursor.execute("SELECT COUNT(*) FROM shard_players")
            return cursor.fetchone()[0]
