# utils/db_manager.py

import pymysql
from datetime import datetime
import logging

class DBManager:
    def __init__(self):
        # DB 설정
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
            self.logger.info("데이터베이스 연결 성공")
            return True
        except Exception as e:
            self.logger.error(f"데이터베이스 연결 실패: {str(e)}")
            return False
            
    def authenticate_user(self, user_id, password):
        """
        사용자 인증 함수 - hol_user 테이블에서 사용자 확인
        
        Args:
            user_id (str): 사용자 ID
            password (str): 사용자 비밀번호
            
        Returns:
            tuple: (인증 성공 여부, 남은 기간, 오류 메시지)
        """
        if not self.conn:
            if not self.connect():
                return False, None, "데이터베이스 연결 실패"
        
        try:
            with self.conn.cursor() as cursor:
                # hol_user 테이블에서 사용자 검증
                cursor.execute('SELECT id, pw, end_date FROM hol_user WHERE id = %s', (user_id,))
                user = cursor.fetchone()
                
                if not user:
                    return False, None, "사용자를 찾을 수 없습니다."
                
                # 비밀번호 확인
                if user[1] != password:
                    return False, None, "비밀번호가 일치하지 않습니다."
                    
                # 만료일 확인
                end_date = user[2]
                days_left = self.calculate_days_left(end_date)
                
                if days_left < 0:
                    return False, days_left, "사용 기간이 만료되었습니다."
                
                return True, days_left, "인증 성공"
                
        except Exception as e:
            self.logger.error(f"사용자 인증 중 오류 발생: {str(e)}")
            return False, None, f"인증 오류: {str(e)}"
            
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
            
        try:
            # 현재 날짜와 비교
            today = datetime.now().date()
            
            # end_date가 문자열인 경우 datetime으로 변환
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                
            days_left = (end_date - today).days
            return days_left
        except Exception as e:
            self.logger.error(f"남은 일수 계산 오류: {str(e)}")
            return -1
        
    def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.logger.info("데이터베이스 연결 종료")