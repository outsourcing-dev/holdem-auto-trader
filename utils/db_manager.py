# utils/db_manager.py

import pymysql
from datetime import datetime, timedelta
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
        
        # 로그인 타임아웃 - 3시간 (단위: 초)
        self.login_timeout = 3 * 60 * 60
        
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
        중복 로그인 방지 기능 추가
        
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
                # 우선 자동 로그아웃 처리 (일정 시간 이상 지난 로그인)
                self.auto_logout_inactive_users()
                
                # hol_user 테이블에서 사용자 검증
                cursor.execute('SELECT id, pw, end_date, logged_in, last_login FROM hol_user WHERE id = %s', (user_id,))
                user = cursor.fetchone()
                
                if not user:
                    return False, None, "사용자를 찾을 수 없습니다."
                
                # 비밀번호 확인
                if user[1] != password:
                    return False, None, "비밀번호가 일치하지 않습니다."
                
                # 로그인 상태 확인 (user[3] == logged_in)
                if user[3] == 1:
                    # 마지막 로그인 시간 확인 (일정 시간 이상 지났는지)
                    last_login = user[4]
                    if last_login:
                        time_diff = datetime.now() - last_login
                        if time_diff.total_seconds() < self.login_timeout:
                            return False, None, "이미 다른 기기에서 로그인 중입니다."
                    
                    # 시간이 지났다면 로그인 허용 (아래에서 상태 업데이트)
                    
                # 만료일 확인
                end_date = user[2]
                days_left = self.calculate_days_left(end_date)
                
                if days_left < 0:
                    return False, days_left, "사용 기간이 만료되었습니다."
                
                # 로그인 상태 업데이트 - 로그인 중으로 변경
                cursor.execute(
                    'UPDATE hol_user SET logged_in = 1, last_login = %s WHERE id = %s',
                    (datetime.now(), user_id)
                )
                self.conn.commit()
                
                return True, days_left, "인증 성공"
                
        except Exception as e:
            self.logger.error(f"사용자 인증 중 오류 발생: {str(e)}")
            return False, None, f"인증 오류: {str(e)}"
            
    def logout_user(self, user_id):
        """
        사용자 로그아웃 처리 - logged_in 상태 초기화
        
        Args:
            user_id (str): 사용자 ID
                
        Returns:
            bool: 성공 여부
        """
        if not self.conn:
            if not self.connect():
                return False
                
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    'UPDATE hol_user SET logged_in = 0 WHERE id = %s',
                    (user_id,)
                )
                self.conn.commit()
                self.logger.info(f"사용자 {user_id} 로그아웃 처리 완료")
                return True
        except Exception as e:
            self.logger.error(f"로그아웃 처리 중 오류 발생: {str(e)}")
            return False
            
    def auto_logout_inactive_users(self):
        """
        일정 시간 이상 로그인된 사용자 자동 로그아웃 처리
        """
        if not self.conn:
            if not self.connect():
                return False
                
        try:
            with self.conn.cursor() as cursor:
                # 현재 시간에서 타임아웃 시간을 뺀 시간보다 이전인 경우 로그아웃 처리
                timeout_datetime = datetime.now() - timedelta(seconds=self.login_timeout)
                
                cursor.execute(
                    'UPDATE hol_user SET logged_in = 0 WHERE logged_in = 1 AND last_login < %s',
                    (timeout_datetime,)
                )
                affected_rows = cursor.rowcount
                self.conn.commit()
                
                if affected_rows > 0:
                    self.logger.info(f"자동 로그아웃 처리: {affected_rows}명의 사용자")
                return True
        except Exception as e:
            self.logger.error(f"자동 로그아웃 처리 중 오류 발생: {str(e)}")
            return False
    
    def admin_reset_login_status(self, user_id=None):
        """
        관리자용 로그인 상태 초기화 함수
        특정 사용자 또는 모든 사용자의 로그인 상태를 초기화
        
        Args:
            user_id (str, optional): 초기화할 특정 사용자 ID (None이면 모든 사용자)
                
        Returns:
            tuple: (성공 여부, 처리된 사용자 수)
        """
        if not self.conn:
            if not self.connect():
                return False, 0
                
        try:
            with self.conn.cursor() as cursor:
                if user_id:
                    # 특정 사용자 로그인 상태 초기화
                    cursor.execute(
                        'UPDATE hol_user SET logged_in = 0 WHERE id = %s',
                        (user_id,)
                    )
                else:
                    # 모든 사용자 로그인 상태 초기화
                    cursor.execute('UPDATE hol_user SET logged_in = 0')
                
                affected_rows = cursor.rowcount
                self.conn.commit()
                
                self.logger.info(f"관리자 로그인 상태 초기화: {affected_rows}명의 사용자")
                return True, affected_rows
        except Exception as e:
            self.logger.error(f"로그인 상태 초기화 중 오류 발생: {str(e)}")
            return False, 0
    
    def get_user(self, user_id):
        """사용자 정보 조회"""
        if not self.conn:
            if not self.connect():
                return None
        
        try:
            with self.conn.cursor() as cursor:
                cursor.execute('SELECT id, pw, end_date, logged_in, last_login FROM hol_user WHERE id = %s', (user_id,))
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