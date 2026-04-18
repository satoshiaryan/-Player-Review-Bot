import sqlite3
import json
import shutil
import os
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
            
            # Reviews table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    rating TEXT,
                    image_url TEXT,
                    base_stats TEXT,
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
            
            # Backup history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    review_count INTEGER,
                    file_path TEXT
                )
            ''')
    
    def add_review(self, player_name: str, rating: str, image_url: str, 
                   base_stats: str, reviewer_id: str, reviewer_name: str) -> int:
        """Add a new review and return its ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reviews 
                (player_name, rating, image_url, base_stats, reviewer_id, reviewer_name)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (player_name, rating, image_url, base_stats, reviewer_id, reviewer_name))
            return cursor.lastrowid
    
    def update_review_field(self, review_id: int, field: str, value: str):
        """Update a specific field of a review"""
        valid_fields = ['pros', 'cons', 'verdict', 'alternatives']
        if field not in valid_fields:
            raise ValueError(f"Invalid field: {field}")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE reviews 
                SET {field} = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (value, review_id))
    
    def get_review(self, review_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific review by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM reviews WHERE id = ?', (review_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_reviews(self) -> List[Dict[str, Any]]:
        """Get all reviews"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM reviews ORDER BY created_at DESC')
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_review(self, review_id: int) -> bool:
        """Delete a review"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
            return cursor.rowcount > 0
    
    def create_backup(self, backup_path: str = None) -> str:
        """Create a backup of the database"""
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_{timestamp}.db"
        
        # Create backup
        shutil.copy2(self.db_path, backup_path)
        
        # Log backup
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM reviews')
            count = cursor.fetchone()[0]
            cursor.execute('''
                INSERT INTO backups (review_count, file_path)
                VALUES (?, ?)
            ''', (count, backup_path))
        
        return backup_path
    
    def restore_backup(self, backup_path: str) -> bool:
        """Restore database from backup file"""
        if not os.path.exists(backup_path):
            return False
        
        # Close current connection if open
        shutil.copy2(backup_path, self.db_path)
        return True
    
    def get_review_count(self) -> int:
        """Get total number of reviews"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM reviews')
            return cursor.fetchone()[0]
