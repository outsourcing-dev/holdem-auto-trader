# utils/db_manager.py

import pymysql
from datetime import datetime
import logging

class DBManager:
    def __init__(self):
        # DB 설정 - config/settings.py에서 가져옵니다
        self.db_config = {
            'host': 'svc.sel4.cloudtype.app',
            'port': 32481,
            'user': 'admin',
            'password': 'hanapf1121',
            'db': 'manager',
            'charset': 'utf8mb4'
        }
        self.conn = None
        self.logger = logging.getLogger(__name__)
        
    def connect(self):
        """데이터베이스 연결"""
        try:
            self.conn = pymysql.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                db=self.db_config['db'],
                charset=self.db_config['charset']
            )
            return True
        except Exception as e:
            self.logger.error(f"데이터베이스 연결 실패: {str(e)}")
            return False
            
    def get_user(self, user_id):
        """사용자 정보 조회"""
        if not self.conn:
            if not self.connect():
                return None
        
        try:
            with self.conn.cursor() as cursor:
                cursor.execute('SELECT id, pw, end_date FROM hol_user WHERE id = %s', (user_id,))
                return cursor.fetchone()
        except Exception as e:
            self.logger.error(f"사용자 조회 실패: {str(e)}")
            return None
            
    def calculate_days_left(self, end_date):
        """만료일까지 남은 일수 계산"""
        if not end_date:
            return -1
            
        today = datetime.now().date()
        days_left = (end_date - today).days
        return days_left
        
    def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()
            self.conn = None