# utils/trading_manager_helpers.py
import time
import logging
from PyQt6.QtWidgets import QMessageBox
from utils.settings_manager import SettingsManager

class TradingManagerHelpers:
    """TradingManager의 헬퍼 기능 모음 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager  # trading_manager 참조
        self.logger = trading_manager.logger or logging.getLogger(__name__)
    
    def check_martin_balance(self, balance):
        """현재 잔고가 마틴 배팅을 하기에 충분한지 확인"""
        try:
            martin_count, martin_amounts = self.tm.settings_manager.get_martin_settings()
            first_martin_amount = martin_amounts[0] if martin_amounts else 1000
            
            if balance < first_martin_amount:
                self.logger.warning(f"잔고 부족: {balance:,}원 < {first_martin_amount:,}원")
                QMessageBox.warning(
                    self.tm.main_window, 
                    "잔액 부족",
                    f"현재 잔고({balance:,}원)가 마틴 1단계 금액({first_martin_amount:,}원)보다 적습니다."
                )
                return False
            
            self.logger.info(f"마틴 배팅 가능: 잔고 {balance:,}원 > 필요금액 {first_martin_amount:,}원")
            return True
        except Exception as e:
            self.logger.error(f"마틴 잔고 확인 오류: {e}")
            return False
    
    def validate_trading_prerequisites(self):
        """자동 매매 시작 전 사전 검증"""
        if self.tm.is_trading_active:
            self.logger.warning("이미 자동 매매가 진행 중입니다.")
            return False
        
        if not self.tm.room_manager.rooms_data:
            QMessageBox.warning(self.tm.main_window, "알림", "방 목록을 먼저 불러와주세요.")
            return False
        
        checked_rooms = self.tm.room_manager.get_checked_rooms()
        if not checked_rooms:
            QMessageBox.warning(self.tm.main_window, "알림", "자동 매매를 시작할 방을 선택해주세요.")
            return False
        
        self.logger.info(f"선택된 방 {len(checked_rooms)}개")
        return True
        
    def verify_license(self):
        """사용자 확인 및 라이센스 검증"""
        try:
            from utils.db_manager import DBManager
            db_manager = DBManager()
            
            username = self.tm.main_window.username
            if not username:
                QMessageBox.warning(self.tm.main_window, "오류", "로그인 정보를 찾을 수 없습니다.")
                return False
                
            # 관리자 계정 확인
            if username == "coreashield":
                days_left = 99999
            else:
                user_info = db_manager.get_user(username)
                if not user_info:
                    QMessageBox.warning(self.tm.main_window, "오류", "사용자 정보를 찾을 수 없습니다.")
                    return False
                    
                end_date = user_info[2]
                days_left = db_manager.calculate_days_left(end_date)
            
            # 남은 일수 확인
            if days_left <= 0:
                QMessageBox.warning(self.tm.main_window, "사용 기간 만료", "사용 기간이 만료되었습니다.")
                self.tm.main_window.set_license_remaining_time(0)
                self.tm.main_window.enable_application_features(False)
                return False
                
            self.logger.info(f"남은 사용 기간: {days_left}일")
            
            # 라이센스 시간 재설정
            if hasattr(self.tm.main_window, 'set_license_remaining_time'):
                self.tm.main_window.set_license_remaining_time(days_left)
                
            return True
        except Exception as e:
            self.logger.error(f"라이센스 확인 오류: {e}")
            return False
            
    # utils/trading_manager_helpers.py - 주요 수정 내용
    def init_trading_settings(self):
        """설정 초기화"""
        try:
            self.logger.info("자동 매매 설정 초기화")
            
            # 설정 매니저 갱신
            self.tm.settings_manager = SettingsManager()
            
            # 서비스 설정 갱신
            if hasattr(self.tm, 'balance_service'):
                self.tm.balance_service.settings_manager = SettingsManager()

            # 마틴 서비스 초기화 및 갱신
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset()
                self.tm.martin_service.settings_manager = self.tm.settings_manager
                self.tm.martin_service.update_settings()
                
            # 초이스 픽 시스템 설정 - 마틴 금액 설정
            if hasattr(self.tm, 'excel_trading_service'):
                martin_count, martin_amounts = self.tm.settings_manager.get_martin_settings()
                self.tm.excel_trading_service.set_martin_amounts(martin_amounts)

            # 베팅 서비스 상태 초기화
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.reset_betting_state()

            # 게임 처리 기록 초기화
            self.tm.processed_rounds = set()
            
            return True
        except Exception as e:
            self.logger.error(f"설정 초기화 오류: {e}")
            return False
        
    def setup_browser_and_check_balance(self):
        """브라우저 실행 및 잔액 확인"""
        try:
            # 브라우저 실행 확인
            if not self.tm.devtools.driver:
                self.tm.devtools.start_browser()
                    
            # 창 개수 확인
            window_handles = self.tm.devtools.driver.window_handles
            if len(window_handles) < 2:
                QMessageBox.warning(self.tm.main_window, "오류", "카지노 창이 필요합니다. 사이트 이동 버튼을 이용해주세요.")
                return False

            # 카지노 로비 창으로 전환
            if len(window_handles) >= 2:
                self.tm.devtools.driver.switch_to.window(window_handles[1])
                self.logger.info("카지노 로비 창으로 포커싱 전환")
                
            # 잔액 확인
            balance = self.tm.balance_service.get_lobby_balance()
            if balance is None:
                QMessageBox.warning(self.tm.main_window, "오류", "로비에서 잔액 정보를 찾을 수 없습니다.")
                return False

            # UI 초기화 및 잔액 표시
            self.tm.main_window.reset_ui()
            self.tm.main_window.update_user_data(
                username=self.tm.main_window.username,
                start_amount=balance,
                current_amount=balance
            )

            # 마틴 배팅을 위한 잔고 확인
            if not self.check_martin_balance(balance):
                return False
                    
            return True
        except Exception as e:
            self.logger.error(f"브라우저 설정 오류: {e}")
            return False