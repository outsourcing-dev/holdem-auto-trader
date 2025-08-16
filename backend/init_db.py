"""
초기 데이터베이스 설정
"""
import sqlite3
import hashlib
from datetime import datetime, timedelta

def init_database():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # users 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            expire_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 비밀번호 해시
    password = hashlib.sha256("asd123".encode()).hexdigest()
    expire_date = (datetime.now() + timedelta(days=365)).isoformat()
    
    # 초기 사용자 추가
    try:
        cursor.execute('''
            INSERT INTO users (username, password, level, expire_date)
            VALUES (?, ?, ?, ?)
        ''', ('coreashield', password, 5, expire_date))
        print("사용자 coreashield 생성 완료")
    except sqlite3.IntegrityError:
        print("사용자 coreashield가 이미 존재합니다")
    
    conn.commit()
    
    # 확인
    cursor.execute("SELECT username, level, expire_date FROM users")
    users = cursor.fetchall()
    print("현재 사용자 목록:")
    for user in users:
        print(f"  - {user[0]} (레벨 {user[1]})")
    
    conn.close()

if __name__ == "__main__":
    init_database()