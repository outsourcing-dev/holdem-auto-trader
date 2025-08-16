"""
데이터베이스 서비스
기존 user_accounts.db 재사용
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict, Any
import hashlib
from pathlib import Path

class DatabaseService:
    def __init__(self):
        # 기존 데이터베이스 파일 경로
        db_path = Path(__file__).parent.parent.parent / "user_accounts.db"
        if not db_path.exists():
            # 상위 디렉토리에서 찾기
            parent_db = Path(__file__).parent.parent.parent.parent / "user_accounts.db"
            if parent_db.exists():
                db_path = parent_db
        
        self.db_path = str(db_path)
        self._init_db()
    
    def _init_db(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 사용자 테이블 생성 (기존 구조 유지)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                expire_date TEXT,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def verify_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """사용자 인증"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # MD5 해시 (기존 시스템 호환)
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        cursor.execute('''
            SELECT id, username, level, expire_date 
            FROM users 
            WHERE username = ? AND password = ?
        ''', (username, password_hash))
        
        user = cursor.fetchone()
        
        if user:
            # 만료일 체크
            expire_date = user[3]
            if expire_date:
                expire_dt = datetime.strptime(expire_date, '%Y-%m-%d')
                if expire_dt < datetime.now():
                    conn.close()
                    return None  # 만료된 계정
            
            # 마지막 로그인 업데이트
            cursor.execute('''
                UPDATE users 
                SET last_login = ? 
                WHERE id = ?
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user[0]))
            conn.commit()
            
            result = {
                'id': user[0],
                'username': user[1],
                'level': user[2],
                'expire_date': user[3] or 'unlimited'
            }
        else:
            result = None
        
        conn.close()
        return result
    
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """사용자 정보 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, level, expire_date 
            FROM users 
            WHERE username = ?
        ''', (username,))
        
        user = cursor.fetchone()
        
        if user:
            result = {
                'id': user[0],
                'username': user[1],
                'level': user[2],
                'expire_date': user[3] or 'unlimited'
            }
        else:
            result = None
        
        conn.close()
        return result
    
    def create_user(self, username: str, password: str, level: int = 1, 
                   expire_date: Optional[str] = None) -> bool:
        """사용자 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # MD5 해시 (기존 시스템 호환)
            password_hash = hashlib.md5(password.encode()).hexdigest()
            
            cursor.execute('''
                INSERT INTO users (username, password, level, expire_date)
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, level, expire_date))
            
            conn.commit()
            result = True
        except sqlite3.IntegrityError:
            result = False  # 이미 존재하는 사용자
        finally:
            conn.close()
        
        return result
    
    def update_user_level(self, username: str, level: int) -> bool:
        """사용자 레벨 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET level = ? 
            WHERE username = ?
        ''', (level, username))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def update_user_expire_date(self, username: str, expire_date: str) -> bool:
        """사용자 만료일 업데이트"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET expire_date = ? 
            WHERE username = ?
        ''', (expire_date, username))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success

# 싱글톤 인스턴스
_database_service = None

def get_database_service() -> DatabaseService:
    """데이터베이스 서비스 인스턴스 반환"""
    global _database_service
    if _database_service is None:
        _database_service = DatabaseService()
    return _database_service