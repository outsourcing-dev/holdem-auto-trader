# utils/trading_manager_helpers.py (서버 기반으로 단순화)
import time
import logging
from PyQt6.QtWidgets import QMessageBox
from utils.settings_manager import SettingsManager

def get_widget_position(main_window) -> int:
    """room_position_counter를 안전하게 가져오는 함수"""
    try:
        return getattr(main_window.betting_widget, 'room_position_counter', 0)
    except Exception:
        return 0

class TradingManagerHelpers:
    """TradingManager의 헬퍼 기능 모음 클래스 - 서버 기반으로 단순화"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager  # trading_manager 참조
        self.logger = trading_manager.logger or logging.getLogger(__name__)
        self.logger.info("단순화된 TradingManagerHelpers 초기화")
    
    def check_martin_balance(self, balance):
        """현재 잔고가 마틴 배팅을 하기에 충분한지 확인 - 단순화"""
        try:
            # 마틴 설정 확인
            _, martin_amounts = self.tm.settings_manager.get_martin_settings()
            first_martin_amount = martin_amounts[0] if martin_amounts else 1000
            
            if balance < first_martin_amount:
                self.logger.warning(f"잔고 부족: {balance:,}원 < {first_martin_amount:,}원")
                QMessageBox.warning(
                    self.tm.main_window, 
                    "잔액 부족",
                    f"현재 잔고({balance:,}원)가 마틴 1단계 금액({first_martin_amount:,}원)보다 적습니다."
                )
                return False
            
            self.logger.info(f"마틴 배팅 가능: 잔고 {balance:,}원")
            return True
            
        except Exception as e:
            self.logger.error(f"마틴 잔고 확인 오류: {e}")
            return False
    
    # utils/trading_manager_helpers.py의 validate_trading_prerequisites 메서드 수정

    def validate_trading_prerequisites(self):
        """자동 매매 시작 전 사전 검증 - 서버 기반으로 단순화"""
        try:
            # 이미 실행 중인지 확인
            if self.tm.is_trading_active:
                self.logger.warning("이미 자동 매매가 진행 중입니다.")
                return False
            
            # 서버 연결 상태 확인
            if hasattr(self.tm, 'server_client'):
                if not self.tm.server_client.get_server_status():
                    QMessageBox.warning(
                        self.tm.main_window, 
                        "서버 연결 오류", 
                        "바카라 분석 서버에 연결할 수 없습니다.\n서버가 실행되고 있는지 확인해주세요."
                    )
                    return False
                else:
                    self.logger.info("서버 연결 상태 확인 완료")
            
            # ✅ 웹소켓 URL 검증 제거 (자동 추출하므로 불필요)
            # 기존 코드:
            # if not hasattr(self.tm.main_window, 'websocket_url') or not self.tm.main_window.websocket_url:
            #     QMessageBox.warning(
            #         self.tm.main_window, 
            #         "설정 필요", 
            #         "웹소켓 URL을 먼저 설정해주세요."
            #     )
            #     return False
            
            # ✅ 브라우저 상태만 확인
            if not hasattr(self.tm, 'devtools') or not self.tm.devtools.driver:
                QMessageBox.warning(
                    self.tm.main_window, 
                    "브라우저 오류", 
                    "브라우저가 실행되지 않았습니다.\n먼저 브라우저를 시작해주세요."
                )
                return False
            
            self.logger.info("자동 매매 사전 검증 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"사전 검증 중 오류: {e}")
            return False
        
    def verify_license(self):
        """라이센스 검증 - 단순화"""
        try:
            # 기본적인 사용자 확인만 수행 (복잡한 DB 연동 제거)
            username = getattr(self.tm.main_window, 'username', None)
            
            if not username:
                QMessageBox.warning(self.tm.main_window, "오류", "로그인 정보를 찾을 수 없습니다.")
                return False
            
            # 관리자 계정 체크
            if username == "coreashield":
                self.logger.info("관리자 계정으로 라이센스 확인 완료")
                return True
            
            # 일반 사용자의 경우 기본적인 확인만
            try:
                from utils.db_manager import DBManager
                db_manager = DBManager()
                
                user_info = db_manager.get_user(username)
                if not user_info:
                    self.logger.warning(f"사용자 정보를 찾을 수 없음: {username}")
                    return False
                
                end_date = user_info[2]
                days_left = db_manager.calculate_days_left(end_date)
                
                if days_left <= 0:
                    QMessageBox.warning(self.tm.main_window, "사용 기간 만료", "사용 기간이 만료되었습니다.")
                    return False
                
                self.logger.info(f"라이센스 확인 완료: {days_left}일 남음")
                return True
                
            except Exception as e:
                # DB 연동 실패 시 기본 허용 (개발 환경)
                self.logger.warning(f"라이센스 DB 확인 실패, 기본 허용: {e}")
                return True
                
        except Exception as e:
            self.logger.error(f"라이센스 확인 오류: {e}")
            return False
            
    def init_trading_settings(self):
        """설정 초기화 - 단순화"""
        try:
            self.logger.info("자동 매매 설정 초기화")
            
            # 설정 매니저 갱신
            self.tm.settings_manager = SettingsManager()
            
            # 서버 기반 서비스들만 초기화
            self._init_server_based_services()
            
            # 마틴 설정 로드 및 적용
            self._apply_martin_settings()
            
            # 기본 상태 초기화
            self.tm.processed_rounds = set()
            self.tm.is_trading_active = False
            self.tm.current_pick = None
            
            self.logger.info("설정 초기화 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"설정 초기화 오류: {e}")
            return False

    def _init_server_based_services(self):
        """서버 기반 서비스들 초기화"""
        try:
            # 잔액 서비스 설정 갱신
            if hasattr(self.tm, 'balance_service'):
                self.tm.balance_service.settings_manager = self.tm.settings_manager
            
            # 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset()
                self.tm.martin_service.settings_manager = self.tm.settings_manager
                self.tm.martin_service.update_settings()
            
            # 베팅 서비스 상태 초기화
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.reset_betting_state()
            
            # 서버 클라이언트 초기화 (있는 경우)
            if hasattr(self.tm, 'server_client'):
                status = self.tm.server_client.get_connection_status()
                self.logger.info(f"서버 클라이언트 상태: {status}")
                
        except Exception as e:
            self.logger.warning(f"서버 기반 서비스 초기화 중 오류: {e}")

    def _apply_martin_settings(self):
        """마틴 설정 적용"""
        try:
            # 마틴 설정 로드
            martin_count, martin_amounts = self.tm.settings_manager.get_martin_settings()
            self.logger.info(f"마틴 설정 로드: {martin_count}단계, 금액={martin_amounts}")
            
            # ExcelTradingService에 마틴 금액 설정
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.set_martin_amounts(martin_amounts)
                self.logger.info("ExcelTradingService 마틴 금액 설정 완료")
                
        except Exception as e:
            self.logger.error(f"마틴 설정 적용 오류: {e}")

    def setup_browser_and_check_balance(self):
        """브라우저 설정 및 잔액 확인 - 단순화"""
        try:
            # 브라우저 실행 상태 확인
            if not self._ensure_browser_ready():
                return False
            
            # 잔액 확인
            balance = self._check_current_balance()
            if balance is None:
                return False
            
            # UI 초기화 및 업데이트
            self._update_ui_with_balance(balance)
            
            # 마틴 배팅 가능 여부 확인
            if not self.check_martin_balance(balance):
                return False
            
            self.logger.info("브라우저 설정 및 잔액 확인 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"브라우저 설정 오류: {e}")
            return False

    def _ensure_browser_ready(self):
        """브라우저 준비 상태 확인"""
        try:
            # 브라우저 실행 확인
            if not hasattr(self.tm, 'devtools') or not self.tm.devtools.driver:
                self.logger.warning("브라우저가 실행되지 않았습니다.")
                QMessageBox.warning(
                    self.tm.main_window, 
                    "브라우저 오류", 
                    "브라우저가 실행되지 않았습니다.\n먼저 브라우저를 시작해주세요."
                )
                return False
            
            # 창 개수 확인
            window_handles = self.tm.devtools.driver.window_handles
            if len(window_handles) < 2:
                QMessageBox.warning(
                    self.tm.main_window, 
                    "창 부족", 
                    "카지노 창이 필요합니다.\n사이트 이동 버튼을 이용해주세요."
                )
                return False
            
            # 카지노 로비 창으로 전환
            self.tm.devtools.driver.switch_to.window(window_handles[1])
            self.logger.info("카지노 로비 창으로 전환 완료")
            
            return True
            
        except Exception as e:
            self.logger.error(f"브라우저 준비 확인 중 오류: {e}")
            return False

    def _check_current_balance(self):
        """현재 잔액 확인"""
        try:
            if not hasattr(self.tm, 'balance_service'):
                self.logger.error("BalanceService가 없습니다.")
                return None
            
            balance = self.tm.balance_service.get_lobby_balance()
            
            if balance is None:
                QMessageBox.warning(
                    self.tm.main_window, 
                    "잔액 확인 오류", 
                    "로비에서 잔액 정보를 찾을 수 없습니다.\n페이지를 새로고침하거나 다시 로그인해주세요."
                )
                return None
            
            self.logger.info(f"현재 잔액: {balance:,}원")
            return balance
            
        except Exception as e:
            self.logger.error(f"잔액 확인 중 오류: {e}")
            return None

    def _update_ui_with_balance(self, balance):
        """UI에 잔액 정보 업데이트"""
        try:
            # UI 초기화
            self.tm.main_window.reset_ui()
            
            # 사용자 데이터 업데이트
            username = getattr(self.tm.main_window, 'username', 'Unknown')
            self.tm.main_window.update_user_data(
                username=username,
                start_amount=balance,
                current_amount=balance
            )
            
            self.logger.info("UI 잔액 정보 업데이트 완료")
            
        except Exception as e:
            self.logger.error(f"UI 업데이트 중 오류: {e}")

    def setup_server_monitoring(self):
        """서버 모니터링 설정 - 새로 추가"""
        try:
            if not hasattr(self.tm, 'server_client'):
                self.logger.error("ServerClient가 없습니다.")
                return False
            
            # 웹소켓 URL 확인
            websocket_url = getattr(self.tm.main_window, 'websocket_url', None)
            if not websocket_url:
                self.logger.error("웹소켓 URL이 설정되지 않았습니다.")
                return False
            
            # 사용자 ID 설정
            user_id = getattr(self.tm.main_window, 'username', 'default_user')
            
            # 서버에 설정 전송 및 모니터링 시작
            if not self.tm.server_client.setup_complete_monitoring(websocket_url, user_id):
                QMessageBox.warning(
                    self.tm.main_window,
                    "서버 설정 오류",
                    "서버 모니터링 설정에 실패했습니다.\n서버 상태를 확인해주세요."
                )
                return False
            
            self.logger.info("서버 모니터링 설정 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"서버 모니터링 설정 오류: {e}")
            return False

    def get_server_recommended_room(self, streak_count=3):
        """서버에서 추천 방 가져오기 - 새로 추가"""
        try:
            if not hasattr(self.tm, 'server_client'):
                self.logger.error("ServerClient가 없습니다.")
                return None
            
            user_id = getattr(self.tm.main_window, 'username', 'default_user')
            
            # 서버에서 연패 방 검색
            response = self.tm.server_client.find_streak_rooms(user_id, streak_count)
            
            if response.get('status') == 'success':
                streak_rooms = response.get('streak_rooms', [])
                
                if streak_rooms:
                    # 첫 번째 추천 방 반환
                    recommended_room = streak_rooms[0]
                    self.logger.info(f"서버 추천 방: {recommended_room['room_name']}")
                    return recommended_room
                else:
                    self.logger.info("서버에서 추천할 방이 없습니다.")
                    return None
            else:
                self.logger.warning(f"서버에서 방 검색 실패: {response.get('message')}")
                return None
                
        except Exception as e:
            self.logger.error(f"서버 추천 방 검색 오류: {e}")
            return None

    def cleanup_trading_session(self):
        """트레이딩 세션 정리 - 새로 추가"""
        try:
            # 서버 모니터링 중지
            if hasattr(self.tm, 'server_client'):
                user_id = getattr(self.tm.main_window, 'username', 'default_user')
                self.tm.server_client.stop_monitoring(user_id)
            
            # 게임방에서 나가기
            if hasattr(self.tm, 'game_monitoring_service'):
                self.tm.game_monitoring_service.close_current_room()
            
            # 상태 초기화
            self.tm.is_trading_active = False
            self.tm.current_pick = None
            self.tm.processed_rounds = set()
            
            self.logger.info("트레이딩 세션 정리 완료")
            
        except Exception as e:
            self.logger.error(f"트레이딩 세션 정리 중 오류: {e}")