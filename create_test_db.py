"""
테스트 데이터베이스 생성 스크립트
"""
import sqlite3
import hashlib
from datetime import datetime, timedelta

# 데이터베이스 생성
conn = sqlite3.connect('user_accounts.db')
cursor = conn.cursor()

# 테이블 생성
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

# 테스트 사용자 추가
test_users = [
    ('coreashield', '1234', 5, (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')),
    ('admin', 'admin123', 5, (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')),
    ('test', 'test123', 3, (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')),
    ('user1', 'password', 1, None),
]

for username, password, level, expire_date in test_users:
    password_hash = hashlib.md5(password.encode()).hexdigest()
    try:
        cursor.execute('''
            INSERT INTO users (username, password, level, expire_date)
            VALUES (?, ?, ?, ?)
        ''', (username, password_hash, level, expire_date))
        print(f"Created user: {username} (level {level})")
    except sqlite3.IntegrityError:
        print(f"User {username} already exists")

conn.commit()
conn.close()

print("\n테스트 데이터베이스가 생성되었습니다.")
print("테스트 계정:")
print("  - coreashield / 1234 (레벨 5) - 관리자")
print("  - admin / admin123 (레벨 5)")
print("  - test / test123 (레벨 3)")
print("  - user1 / password (레벨 1)")