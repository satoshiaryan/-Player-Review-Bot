import sqlite3
import json
import shutil
import os
import io
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
            
            cursor.execute("PRAGMA table_info(reviews)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'event' not in columns:
                cursor.execute('ALTER TABLE reviews ADD COLUMN event TEXT DEFAULT ""')
            if 'skill_move' not in columns:
                cursor.execute('ALTER TABLE reviews ADD COLUMN skill_move INTEGER DEFAULT 0')
            if 'weak_foot' not in columns:
                cursor.execute('ALTER TABLE reviews ADD COLUMN weak_foot INTEGER DEFAULT 0')
            if 'strong_foot' not in columns:
                cursor.execute('ALTER TABLE reviews ADD COLUMN strong_foot TEXT DEFAULT ""')
            if 'skill_points' not in columns:
                cursor.execute('ALTER TABLE reviews ADD COLUMN skill_points TEXT DEFAULT ""')
            if 'image_data' not in columns:
                cursor.execute('ALTER TABLE reviews ADD COLUMN image_data TEXT DEFAULT NULL')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    review_count INTEGER,
                    file_path TEXT
                )
            ''')
    
    def add_review(self, player_name: str, rating: str, image_url: str, 
                   base_stats: str, reviewer_id: str, reviewer_name: str, 
                   event: str = "", skill_move: int = 0, weak_foot: int = 0, 
                   strong_foot: str = "", skill_points: str = "") -> int:
        image_base64 = None
        if image_url:
            try:
                req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    image_data = response.read()
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
            except Exception as e:
                print(f"⚠️ Could not download image: {e}")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reviews 
                (player_name, rating, event, image_url, image_data, base_stats, skill_move, weak_foot, strong_foot, skill_points, reviewer_id, reviewer_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (player_name, rating, event, image_url, image_base64, base_stats, skill_move, weak_foot, strong_foot, skill_points, reviewer_id, reviewer_name))
            conn.commit()
            return cursor.lastrowid
    
    def update_review_field(self, review_id: int, field: str, value):
        valid_fields = ['pros', 'cons', 'verdict', 'alternatives', 'event', 'skill_points']
        if field not in valid_fields:
            raise ValueError(f"Invalid field: {field}")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE reviews SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (value, review_id))
            conn.commit()
    
    def update_image(self, review_id: int, image_url: str) -> bool:
        try:
            req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                image_data = response.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE reviews SET image_url = ?, image_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (image_url, image_base64, review_id))
                conn.commit()
            return True
        except Exception as e:
            print(f"❌ Failed to update image: {e}")
            return False
    
    def get_review(self, review_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM reviews WHERE id = ?', (review_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_reviews(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM reviews ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_review(self, review_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def create_backup(self, backup_path: str = None) -> str:
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_{timestamp}.db"
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.commit()
        except:
            pass
        shutil.copy2(self.db_path, backup_path)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM reviews')
            count = cursor.fetchone()[0]
            cursor.execute('INSERT INTO backups (review_count, file_path) VALUES (?, ?)', (count, backup_path))
            conn.commit()
        return backup_path
    
    def restore_backup(self, backup_path: str) -> bool:
        if not os.path.exists(backup_path):
            return False
        try:
            shutil.copy2(backup_path, self.db_path)
            return True
        except:
            return False
    
    def get_review_count(self) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM reviews')
                return cursor.fetchone()[0]
        except:
            return 0


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
        for db_name, positions in self.DB_MAP.items():
            with sqlite3.connect(db_name) as conn:
                cursor = conn.cursor()
                for position in positions:
                    cursor.execute(f'''CREATE TABLE IF NOT EXISTS top10_{position}
                                     (rank INTEGER PRIMARY KEY,
                                      player_name TEXT,
                                      card_name TEXT,
                                      rating TEXT,
                                      image_url TEXT,
                                      image_data TEXT DEFAULT NULL,
                                      badge_data TEXT DEFAULT NULL,
                                      updated_by TEXT,
                                      updated_at TIMESTAMP)''')
                # Add badge_data column if missing
                for position in positions:
                    cursor.execute(f"PRAGMA table_info(top10_{position})")
                    cols = [c[1] for c in cursor.fetchall()]
                    if 'badge_data' not in cols:
                        cursor.execute(f"ALTER TABLE top10_{position} ADD COLUMN badge_data TEXT DEFAULT NULL")
    
    def get_top10(self, position: str):
        db_name = self.get_db_for_position(position)
        with sqlite3.connect(db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM top10_{position} ORDER BY CAST(rank AS INTEGER)")
            return [dict(row) for row in cursor.fetchall()]
    
    def add_top10_entry(self, position: str, rank: int, player_name: str, card_name: str, 
                        rating: str, image_url: str, updated_by: str, badge_url: str = "") -> bool:
        image_base64 = None
        if image_url:
            try:
                req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    image_data = response.read()
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
            except:
                pass
        
        badge_base64 = None
        if badge_url:
            try:
                req = urllib.request.Request(badge_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    badge_data = response.read()
                    badge_base64 = base64.b64encode(badge_data).decode('utf-8')
            except:
                pass
        
        db_name = self.get_db_for_position(position)
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            # Check if entry exists
            cursor.execute(f"SELECT rank FROM top10_{position} WHERE rank = ?", (rank,))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing, preserve badge if not providing new one
                if badge_base64:
                    cursor.execute(f'''UPDATE top10_{position} 
                                     SET player_name=?, card_name=?, rating=?, image_url=?, image_data=?, badge_data=?, updated_by=?, updated_at=?
                                     WHERE rank=?''',
                                  (player_name, card_name, rating, image_url, image_base64, badge_base64, updated_by, datetime.now().isoformat(), rank))
                else:
                    cursor.execute(f'''UPDATE top10_{position} 
                                     SET player_name=?, card_name=?, rating=?, image_url=?, image_data=?, updated_by=?, updated_at=?
                                     WHERE rank=?''',
                                  (player_name, card_name, rating, image_url, image_base64, updated_by, datetime.now().isoformat(), rank))
            else:
                cursor.execute(f'''INSERT INTO top10_{position} 
                                 (rank, player_name, card_name, rating, image_url, image_data, badge_data, updated_by, updated_at)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                              (rank, player_name, card_name, rating, image_url, image_base64, badge_base64, updated_by, datetime.now().isoformat()))
            conn.commit()
        return True
    
    def update_badge(self, position: str, rank: int, badge_url: str) -> bool:
        badge_base64 = None
        if badge_url:
            try:
                req = urllib.request.Request(badge_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    badge_data = response.read()
                    badge_base64 = base64.b64encode(badge_data).decode('utf-8')
            except:
                return False
        
        db_name = self.get_db_for_position(position)
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE top10_{position} SET badge_data = ?, updated_at = ? WHERE rank = ?",
                          (badge_base64, datetime.now().isoformat(), rank))
            conn.commit()
            return cursor.rowcount > 0
    
    def remove_top10_entry(self, position: str, rank: int) -> bool:
        db_name = self.get_db_for_position(position)
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM top10_{position} WHERE rank = ?", (rank,))
            conn.commit()
            return cursor.rowcount > 0
    
    def swap_top10_entries(self, position: str, rank1: int, rank2: int) -> bool:
        db_name = self.get_db_for_position(position)
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM top10_{position} WHERE rank = ?", (rank1,))
            entry1 = cursor.fetchone()
            cursor.execute(f"SELECT * FROM top10_{position} WHERE rank = ?", (rank2,))
            entry2 = cursor.fetchone()
            if entry1 and entry2:
                cursor.execute(f"UPDATE top10_{position} SET player_name=?, card_name=?, rating=?, image_url=?, image_data=?, badge_data=?, updated_by=?, updated_at=? WHERE rank=?",
                              (entry2[1], entry2[2], entry2[3], entry2[4], entry2[5], entry2[6], "system", datetime.now().isoformat(), rank1))
                cursor.execute(f"UPDATE top10_{position} SET player_name=?, card_name=?, rating=?, image_url=?, image_data=?, badge_data=?, updated_by=?, updated_at=? WHERE rank=?",
                              (entry1[1], entry1[2], entry1[3], entry1[4], entry1[5], entry1[6], "system", datetime.now().isoformat(), rank2))
                conn.commit()
                return True
        return False
