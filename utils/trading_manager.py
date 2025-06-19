# utils/trading_manager.py (Performance Logging 없는 웹소켓 추출 버전)
from cmath import e
import time
import logging
import os
from PyQt6.QtWidgets import QMessageBox, QApplication
from services.room_entry_service import RoomEntryService
from services.excel_trading_service import ExcelTradingService
from services.betting_service import BettingService
from services.game_monitoring_service import GameMonitoringService
from services.balance_service import BalanceService
from services.martin_service import MartinBettingService
from utils.settings_manager import SettingsManager
from utils.trading_manager_helpers import TradingManagerHelpers, get_widget_position
from utils.server_client import BaccaratServerClient
from services.websocket_parser import WebSocketParser
from utils.devtools import DevToolsController

class TradingManager:
    def __init__(self, main_window, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.main_window = main_window
        self.devtools = DevToolsController(logger=self.logger)  # ✅ 새로운 DevToolsController 사용
        self.room_manager = main_window.room_manager
        self.settings_manager = SettingsManager()

        self.server_client = BaccaratServerClient(logger=self.logger)
        self.user_id = f"user_{int(time.time())}"
        
        # 상태 관리 속성
        self.is_trading_active = False
        self.current_room_name = ""
        self.game_count = 0
        self.result_count = 0
        self.current_pick = None
        self.processed_rounds = set()
        
        # 서버 모니터링 상태
        self.server_monitoring_active = False
        self.last_server_check = 0
        self.server_check_interval = 10  # 10초마다 서버 체크
        
        # 추가 상태 관리 변수
        self.wait_first_result = False
        self.wait_first_result_count = 0
        self.game_state_check_count = 0
        self.same_round_count = 0
        self.no_result_counter = 0
        self.entered_round = -1
        self.stop_all_processes = False

        # 여기에 추가: 마틴 상태 추적 변수
        self.last_martin_step = 0  # 마지막으로 기록된 마틴 단계

        # 서비스 클래스 초기화
        self._init_services()
        
        self.recent_game_results = []  # 최근 게임 결과 (P, B, T 포함)
        self.filtered_game_results = []  # 최근 게임 결과 (P, B만 포함)

        # 헬퍼 클래스들 초기화 - 모듈 임포트
        from utils.trading_manager_helpers import TradingManagerHelpers
        from utils.trading_manager_bet import TradingManagerBet
        from utils.trading_manager_game import TradingManagerGame
        
        self.helpers = TradingManagerHelpers(self)
        self.bet_helper = TradingManagerBet(self)
        self.game_helper = TradingManagerGame(self)
        self._should_move_to_next_room = False
        self.had_tie_last_round = False  # 타이 직후 플래그
        self.just_won = False  # 승리 플래그 추가
        
    def _init_services(self):
        """서비스 객체들을 초기화"""
        try:
            self.betting_service = BettingService(
                devtools=self.devtools,
                main_window=self.main_window,
                logger=self.logger
            )
            
            self.game_monitoring_service = GameMonitoringService(
                devtools=self.devtools,
                main_window=self.main_window,
                logger=self.logger
            )
            
            self.balance_service = BalanceService(
                devtools=self.devtools,
                main_window=self.main_window,
                logger=self.logger
            )
            
            self.room_entry_service = RoomEntryService(
                devtools=self.devtools, 
                main_window=self.main_window, 
                room_manager=self.room_manager, 
                logger=self.logger
            )

            self.excel_trading_service = ExcelTradingService(
                main_window=self.main_window, 
                logger=self.logger
            )
            
            self.martin_service = MartinBettingService(
                main_window=self.main_window,
                logger=self.logger
            )
            
            self.logger.info("모든 서비스 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"베팅 조건 확인 오류: {e}", exc_info=True)
            if self.is_trading_active:
                self.main_window.set_remaining_time(0, 0, 2)

    def start_trading(self):
        """자동 매매 시작 - Performance Logging 없는 웹소켓 추출"""
        try:
            # 브라우저 드라이버 확인
            if not self.devtools.driver:
                print("[INFO] 브라우저가 실행되지 않았습니다. 자동 매매를 시작하지 않습니다.")
                return
                
            # 시작 전 설정 새로고침
            self.refresh_settings()
            
            # 목표 금액 도달 플래그 초기화
            if hasattr(self.balance_service, '_target_amount_reached'):
                del self.balance_service._target_amount_reached
                self.logger.info("목표 금액 도달 플래그 초기화")
            
            # stop_all_processes 플래그 초기화
            self.stop_all_processes = False
            
            # 사전 검증
            if not self.helpers.validate_trading_prerequisites():
                return

            # 사용자 확인 및 라이센스 검증
            if not self.helpers.verify_license():
                return
                    
            # 설정 초기화
            self.helpers.init_trading_settings()
            
            # ✅ 핵심: 에볼루션 로비 확인 및 전환
            if not self._ensure_evolution_lobby_ready():
                return
            
            # ✅ Performance Logging 없는 웹소켓 URL 추출
            websocket_url = self._extract_websocket_without_performance_logging()
            
            if not websocket_url:
                # 완전 실패 시 프로그램 종료
                QMessageBox.critical(
                    self.main_window,
                    "시작 실패",
                    "웹소켓 URL을 추출할 수 없어 자동 매매를 시작할 수 없습니다.\n\n" +
                    "다음을 확인해주세요:\n" +
                    "• 에볼루션 카지노에 정상 접속되어 있는지\n" +
                    "• 네트워크 연결 상태\n" +
                    "• 브라우저에서 게임이 정상 로딩되는지"
                )
                return

            # ✅ 서버 기반 모드로 진행
            self.logger.info("🌐 서버 기반 모드로 자동 매매 시작")
            
            # 서버 상태 확인
            if not self.server_client.get_server_status():
                QMessageBox.warning(
                    self.main_window,
                    "서버 연결 실패",
                    "바카라 분석 서버에 연결할 수 없습니다.\n" +
                    "서버 상태를 확인해주세요."
                )
                return
            
            # ✅ 서버 설정 및 모니터링 시작
            if not self.server_client.send_websocket_config(websocket_url, self.user_id):
                QMessageBox.warning(
                    self.main_window,
                    "서버 설정 실패",
                    "서버에 웹소켓 설정을 전송하지 못했습니다."
                )
                return
            elif not self.server_client.start_monitoring(self.user_id):
                QMessageBox.warning(
                    self.main_window,
                    "모니터링 시작 실패",
                    "서버에서 모니터링을 시작하지 못했습니다."
                )
                return
            else:
                self.server_monitoring_active = True
                self.logger.info("✅ 서버 모니터링 활성화 완료")

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info(f"🚀 자동 매매 시작!")
            
            # UI 업데이트
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(False)
            self.main_window.update_button_styles()
            QApplication.processEvents()
            
            # 목표 금액 체크
            balance = getattr(self.main_window, 'current_amount', 0)
            if balance and self.balance_service.check_target_amount(balance):
                self.logger.info("목표 금액에 이미 도달")
                return
            
            # 서버 기반 방 입장 시작
            self.start_server_based_room_search()
            
        except Exception as e:
            self.logger.error(f"자동 매매 시작 오류: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window, 
                "자동 매매 오류", 
                f"자동 매매 중 심각한 오류가 발생했습니다.\n자동 매매가 중지됩니다.\n오류: {str(e)}"
            )
 
    def stop_trading(self):
        """자동 매매 중지 - 서버 모니터링도 중지"""
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 이미 중지된 상태입니다.")
                return
                
            self.logger.info("자동 매매 중지 중...")
            
            # 서버 모니터링 중지
            if self.server_monitoring_active:
                self.server_client.stop_monitoring(self.user_id)
                self.server_monitoring_active = False
                self.logger.info("서버 모니터링 중지 완료")
            
            # 중지 플래그 설정
            self.stop_all_processes = True
            
            # 실행 중인 모든 타이머 이벤트 취소
            if hasattr(self.main_window, 'timer') and self.main_window.timer.isActive():
                self.main_window.timer.stop()
                QApplication.processEvents()
                self.logger.info("타이머 중지 및 이벤트 큐 처리 완료")
            
            # 1초 대기하여 진행 중인 작업들이 중지 플래그를 확인할 시간 제공
            time.sleep(1)
            
            # 그 다음 trading_active 플래그 비활성화
            self.is_trading_active = False
            
            # 베팅 상태 초기화
            if hasattr(self, 'betting_service'):
                self.betting_service.reset_betting_state()
            
            # 마틴 서비스 초기화
            if hasattr(self, 'martin_service'):
                self.martin_service.reset()
            
            # 게임 상태 완전 초기화
            self.game_count = 0
            self.result_count = 0
            self.current_pick = None
            self.processed_rounds = set()  # 처리된 라운드 기록 초기화
            
            # 게임 모니터링 서비스 카운트 초기화
            if hasattr(self, 'game_monitoring_service'):
                if hasattr(self.game_monitoring_service, 'last_detected_count'):
                    self.game_monitoring_service.last_detected_count = 0
                if hasattr(self.game_monitoring_service, 'game_detector'):
                    from modules.game_detector import GameDetector
                    self.game_monitoring_service.game_detector = GameDetector()  # 새로운 인스턴스로 교체
            
            # 중요: 이전에 예약된 타이머 이벤트를 모두 취소 (추가)
            if hasattr(self.main_window, 'timer'):
                if self.main_window.timer.isActive():
                    self.main_window.timer.stop()
                # 이벤트 큐 처리
                QApplication.processEvents()
            
            # 버튼 상태 업데이트
            self.main_window.start_button.setEnabled(True)
            self.main_window.stop_button.setEnabled(False)  # 중지 버튼 항상 비활성화
            
            # 현재 게임방에서 나가기 시도
            self.logger.info("현재 방에서 나가기만 수행")
            if hasattr(self, 'game_helper'):
                self.game_helper.exit_current_game_room()

            # 목표 금액에 도달했는지 확인하여 메시지 표시 결정
            target_reached = hasattr(self.balance_service, '_target_amount_reached') and self.balance_service._target_amount_reached
            
            # 목표 금액 도달로 인한 중지가 아닌 경우에만 메시지 표시
            if not target_reached:
                QMessageBox.information(self.main_window, "알림", "자동 매매가 중지되었습니다.")

        except Exception as e:
            self.logger.error(f"자동 매매 중지 중 오류 발생: {e}", exc_info=True)
            
            # 강제 중지 시도
            self.is_trading_active = False
            self.server_monitoring_active = False
            if hasattr(self.main_window, 'timer'):
                self.main_window.timer.stop()
                
            # 게임 카운트 강제 초기화
            self.game_count = 0
            
            # 버튼 상태 업데이트 시도
            try:
                self.main_window.start_button.setEnabled(True)
                self.main_window.stop_button.setEnabled(False)  # 중지 버튼 항상 비활성화
            except:
                pass

            QMessageBox.warning(
                self.main_window, 
                "중지 오류", 
                f"자동 매매 중지 중 문제가 발생했습니다.\n수동으로 중지되었습니다."
            )        
            
    def update_settings(self):
        """설정이 변경된 경우 호출될 설정 업데이트 메서드"""
        try:
            # 설정 매니저 갱신 - 파일에서 다시 로드
            self.settings_manager = SettingsManager()
            self.settings_manager.load_settings()
            
            # 각 서비스의 설정 매니저도 갱신
            if hasattr(self, 'balance_service'):
                self.balance_service.settings_manager = self.settings_manager
            
            # 마틴 서비스의 설정 업데이트
            if hasattr(self, 'martin_service'):
                # 설정 매니저 갱신
                self.martin_service.settings_manager = self.settings_manager
                # 마틴 설정 업데이트 메서드 호출
                if hasattr(self.martin_service, 'update_settings'):
                    self.martin_service.update_settings()
            
            # 설정 업데이트 로깅
            martin_count, martin_amounts = self.settings_manager.get_martin_settings()
            target_amount = self.settings_manager.get_target_amount()
            double_half_start, double_half_stop = self.settings_manager.get_double_half_settings()
            
            self.logger.info(f"설정 업데이트 완료 - 마틴 설정: {martin_count}단계, {martin_amounts}")
            self.logger.info(f"목표 금액: {target_amount:,}원, Double & Half: 시작={double_half_start}, 중지={double_half_stop}")
            
            return True
        except Exception as e:
            self.logger.error(f"설정 업데이트 중 오류 발생: {e}")
            return False
        
    def refresh_settings(self):
        """설정을 파일에서 새로 로드하여 적용합니다."""
        try:
            # 설정 매니저 재생성 (항상 파일에서 다시 로드)
            self.settings_manager = SettingsManager()
            
            # 각 서비스의 설정 매니저도 갱신
            services = ['balance_service', 'martin_service', 'room_entry_service', 'excel_trading_service']
            for service_name in services:
                if hasattr(self, service_name):
                    service = getattr(self, service_name)
                    if hasattr(service, 'settings_manager'):
                        # 기존 객체가 있으면 업데이트
                        service.settings_manager = self.settings_manager
            
            # 마틴 설정 로드
            martin_count, martin_amounts = self.settings_manager.get_martin_settings()
            
            # 초이스 픽 시스템에 마틴 금액 설정
            if hasattr(self, 'excel_trading_service'):
                self.excel_trading_service.set_martin_amounts(martin_amounts)
                    
            # 설정 로그 출력
            self.logger.info(f"설정 새로고침 완료 - 마틴 설정: {martin_count}단계, {martin_amounts}")
            
            return True
        except Exception as e:
            self.logger.error(f"설정 새로고침 중 오류 발생: {e}")
            return False

    # 기존 메서드들 (서버 기반으로 단순화하거나 유지)
    def change_room(self, due_to_consecutive_n=False):
        """
        다음 방으로 이동 - 서버 기반으로 단순화
        """
        # 서버 기반 시스템에서는 서버가 추천하는 방으로 이동
        self.logger.info("방 이동 요청 - 서버에서 새로운 방 검색")
        self.start_server_based_room_search()
        
    def check_after_win_status(self):
        """승리 후 모든 상태가 올바르게 초기화되었는지 확인"""
        if getattr(self, 'just_won', False):
            self.logger.info("승리 후 상태 확인 - 모든 상태 초기화 중")
            
            # 위젯 초기화
            if hasattr(self.main_window, 'betting_widget'):
                self.main_window.betting_widget.room_position_counter = 0
                self.main_window.betting_widget.reset_step_markers()
            
            # 마틴 서비스 초기화
            if hasattr(self, 'martin_service'):
                self.martin_service.current_step = 0
                self.martin_service.consecutive_failures = 0
            
            # 첫 결과 대기 플래그 초기화
            self.wait_first_result = False
            
            # 플래그 초기화
            self.just_won = False
            
            self.logger.info("승리 후 상태 초기화 완료")

    @property
    def should_move_to_next_room(self):
        """
        Property to check if we should move to the next room.
        서버 기반 시스템에서는 서버가 판단하므로 단순화
        """
        # 중지 명령 확인
        if getattr(self, 'stop_all_processes', False):
            return False
            
        # 목표 금액 도달 확인
        if hasattr(self.balance_service, '_target_amount_reached') and self.balance_service._target_amount_reached:
            return False
        
        # 서버 기반 시스템에서는 대부분의 방 이동 결정을 서버에서 처리
        # 클라이언트에서는 기본적인 조건만 확인
        return self._should_move_to_next_room

    @should_move_to_next_room.setter
    def should_move_to_next_room(self, value):
        """Setter for the should_move_to_next_room property."""
        self._should_move_to_next_room = value

    def start_server_based_room_search(self):
        """서버 기반 방 검색 및 입장"""
        try:
            self.logger.info("서버에서 연패 조건에 맞는 방 검색 중...")
            
            # 연패 조건 설정 (기본값: 3연패)
            streak_count = 3
            
            # 서버에서 연패 방 검색
            response = self.server_client.find_streak_rooms(self.user_id, streak_count)
            
            if not response or response.get('status') != 'success':
                self.logger.info("조건에 맞는 방이 없습니다. 5초 후 다시 검색합니다.")
                # 5초 후 다시 검색
                self.main_window.set_remaining_time(0, 0, 5)
                return
            
            streak_rooms = response.get('streak_rooms', [])
            if not streak_rooms:
                self.logger.info("추천할 방이 없습니다. 5초 후 다시 검색합니다.")
                self.main_window.set_remaining_time(0, 0, 5)
                return
            
            # 첫 번째 추천 방으로 입장
            target_room = streak_rooms[0]
            room_name = target_room.get("room_name", "")
            
            self.logger.info(f"추천 방 발견: {room_name} (연패: {target_room.get('streak_failures', 0)}회)")
            
            # 방 입장 시도
            if self.enter_recommended_room(room_name):
                # 입장 성공 시 베팅 모니터링 시작
                self.start_betting_monitoring()
            else:
                # 입장 실패 시 다른 방 시도 또는 재검색
                self.logger.warning(f"방 입장 실패: {room_name}")
                self.start_server_based_room_search()  # 재시도
                
        except Exception as e:
            self.logger.error(f"서버 기반 방 검색 오류: {e}", exc_info=True)
            # 5초 후 재시도
            self.main_window.set_remaining_time(0, 0, 5)

    def enter_recommended_room(self, room_name: str) -> bool:
        """추천받은 방으로 입장"""
        try:
            self.logger.info(f"추천 방 '{room_name}'으로 입장 시도")
            
            # 방 입장 서비스 사용
            success = self.room_entry_service.enter_specific_room(room_name)
            
            if success:
                self.current_room_name = room_name
                self.game_count = 0
                self.result_count = 0
                self.wait_first_result = True  # 첫 결과 대기 설정
                
                # UI 업데이트
                self.main_window.update_betting_status(room_name=room_name)
                self.main_window.stop_button.setEnabled(True)
                self.main_window.update_button_styles()
                
                # 방 로그 업데이트
                if hasattr(self.main_window, 'room_log_widget'):
                    self.main_window.room_log_widget.set_current_room(room_name, is_new_visit=True)
                
                self.logger.info(f"방 입장 성공: {room_name}")
                return True
            else:
                self.logger.warning(f"방 입장 실패: {room_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"방 입장 중 오류: {e}", exc_info=True)
            return False

    def start_betting_monitoring(self):
        """베팅 모니터링 시작"""
        try:
            self.logger.info("베팅 모니터링 시작")
            
            # 현재 게임 상태 확인 및 베팅 준비
            self.check_betting_conditions()
            
            # 주기적 체크 시작 (2초마다)
            self.main_window.set_remaining_time(0, 0, 2)
            
        except Exception as e:
            self.logger.error(f"베팅 모니터링 시작 오류: {e}", exc_info=True)

    def check_betting_conditions(self):
        """베팅 조건 확인 및 베팅 실행"""
        try:
            # 중지 플래그 확인
            if getattr(self, 'stop_all_processes', False):
                return

            # 목표 금액 도달 확인
            if hasattr(self.balance_service, '_target_amount_reached') and self.balance_service._target_amount_reached:
                return

            # 서버에서 현재 모니터링 데이터 확인
            current_time = time.time()
            if current_time - self.last_server_check > self.server_check_interval:
                monitoring_data = self.server_client.get_monitoring_data(self.user_id)
                self.last_server_check = current_time
                
                if monitoring_data:
                    self.process_server_monitoring_data(monitoring_data)

            # 베팅 가능 상태 확인
            game_state = self.game_monitoring_service.get_current_game_state(log_always=False)
            
            if game_state and game_state.get('betting_available', False):
                # 베팅 로직 실행
                self.execute_betting_if_needed(game_state)
            
            # 다음 체크 예약
            if self.is_trading_active:
                self.main_window.set_remaining_time(0, 0, 2)
                
        except Exception as e:
            self.logger.error(f"베팅 조건 확인 오류: {e}", exc_info=True)
            if self.is_trading_active:
                self.main_window.set_remaining_time(0, 0, 2)

    # 추가 유틸리티 메서드들
    def get_current_status(self):
        """현재 트레이딩 상태 반환"""
        return {
            'is_active': self.is_trading_active,
            'server_monitoring': self.server_monitoring_active,
            'current_room': self.current_room_name,
            'game_count': self.game_count,
            'result_count': self.result_count,
            'has_bet': getattr(self.betting_service, 'has_bet_current_round', False) if hasattr(self, 'betting_service') else False,
            'wait_first_result': self.wait_first_result,
            'stop_flag': getattr(self, 'stop_all_processes', False)
        }

    def emergency_stop(self):
        """비상 정지 - 모든 프로세스 즉시 중단"""
        try:
            self.logger.warning("🚨 비상 정지 실행")
            
            # 즉시 플래그 설정
            self.stop_all_processes = True
            self.is_trading_active = False
            self.server_monitoring_active = False
            
            # 서버 연결 강제 해제
            try:
                if hasattr(self, 'server_client'):
                    self.server_client.force_disconnect()
            except:
                pass
            
            # 타이머 강제 중지
            try:
                if hasattr(self.main_window, 'timer'):
                    self.main_window.timer.stop()
                    QApplication.processEvents()
            except:
                pass
            
            # UI 상태 강제 복원
            try:
                self.main_window.start_button.setEnabled(True)
                self.main_window.stop_button.setEnabled(False)
                self.main_window.update_button_styles()
            except:
                pass
            
            self.logger.info("비상 정지 완료")
            
        except Exception as e:
            self.logger.error(f"비상 정지 중 오류: {e}")

    def reset_all_states(self):
        """모든 상태 완전 초기화"""
        try:
            self.logger.info("모든 상태 완전 초기화 시작")
            
            # 플래그 초기화
            self.is_trading_active = False
            self.server_monitoring_active = False
            self.stop_all_processes = False
            self.wait_first_result = False
            self.just_won = False
            self.had_tie_last_round = False
            
            # 카운터 초기화
            self.game_count = 0
            self.result_count = 0
            self.wait_first_result_count = 0
            self.game_state_check_count = 0
            self.same_round_count = 0
            self.no_result_counter = 0
            self.entered_round = -1
            self.last_martin_step = 0
            
            # 데이터 구조 초기화
            self.current_room_name = ""
            self.current_pick = None
            self.processed_rounds = set()
            self.recent_game_results = []
            self.filtered_game_results = []
            
            # 서버 모니터링 초기화
            self.last_server_check = 0
            
            # 서비스별 초기화
            if hasattr(self, 'betting_service'):
                self.betting_service.reset_betting_state()
            
            if hasattr(self, 'martin_service'):
                self.martin_service.reset()
            
            self.logger.info("모든 상태 완전 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"상태 초기화 중 오류: {e}")

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            if hasattr(self, 'server_monitoring_active') and self.server_monitoring_active:
                if hasattr(self, 'server_client'):
                    self.server_client.stop_monitoring(getattr(self, 'user_id', ''))
            
            # 타이머 정리
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'timer'):
                if self.main_window.timer.isActive():
                    self.main_window.timer.stop()
                    
        except:
            pass  # 소멸자에서는 예외를 조용히 처리류", 
            
            

    def _ensure_evolution_lobby_ready(self):
        """에볼루션 로비 준비 상태 확인 및 전환"""
        try:
            # 창 개수 확인
            window_handles = self.devtools.driver.window_handles
            print(f"전체 창 개수: {len(window_handles)}")
            
            if len(window_handles) < 2:
                QMessageBox.information(
                    self.main_window, 
                    "에볼루션 접속 필요", 
                    "에볼루션 카지노에 먼저 접속해주세요.\n사이트 버튼을 눌러 에볼루션에 접속 후 다시 시도해주세요."
                )
                return False
            
            # 에볼루션 로비 창으로 전환 (보통 2번째 창)
            print(f"2번째 창으로 전환: {window_handles[1]}")
            self.devtools.driver.switch_to.window(window_handles[1])
            self.logger.info("에볼루션 로비 창으로 전환 완료")
            
            # 페이지 로딩 대기
            print("페이지 로딩을 위해 3초 대기 중...")
            time.sleep(3)
            
            # 에볼루션 페이지인지 확인
            try:
                evolution_found = False
                
                # 1. URL 기반 확인 (가장 확실한 방법)
                current_url = self.devtools.driver.current_url
                if any(keyword in current_url.lower() for keyword in ['evolution', 'evo']):
                    self.logger.info(f"URL에서 에볼루션 확인: {current_url}")
                    evolution_found = True
                
                # 2. 페이지 소스에서 키워드 확인
                if not evolution_found:
                    try:
                        page_source = self.devtools.driver.page_source.lower()
                        if ('evolution' in page_source or 'evologo' in page_source):
                            self.logger.info("페이지 소스에서 에볼루션 키워드 확인")
                            evolution_found = True
                    except:
                        pass
                
                # 에볼루션 페이지가 아닌 경우 사용자에게 확인
                if not evolution_found:
                    reply = QMessageBox.question(
                        self.main_window,
                        "에볼루션 페이지 확인",
                        "자동으로 에볼루션 페이지를 확인하지 못했습니다.\n\n" +
                        "현재 페이지가 에볼루션 카지노가 맞습니까?\n\n" +
                        f"현재 URL: {current_url[:100]}...",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        self.logger.info("사용자가 에볼루션 페이지임을 확인")
                        evolution_found = True
                    else:
                        QMessageBox.information(
                            self.main_window,
                            "에볼루션 접속 필요",
                            "사이트 버튼을 눌러 에볼루션에 접속해주세요."
                        )
                        return False
                
                if not evolution_found:
                    return False
                    
            except Exception as e:
                self.logger.warning(f"에볼루션 페이지 확인 중 오류: {e}")
                
                # 오류 발생시에도 사용자에게 확인 요청
                reply = QMessageBox.question(
                    self.main_window,
                    "페이지 확인 오류",
                    "페이지 확인 중 오류가 발생했습니다.\n\n" +
                    "현재 페이지가 에볼루션 카지노가 맞습니까?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply != QMessageBox.StandardButton.Yes:
                    return False
            
            # 잔액 확인 (로비 상태 검증)
            if not self.helpers.setup_browser_and_check_balance():
                return False
                
            self.logger.info("에볼루션 로비 준비 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"에볼루션 로비 준비 중 오류: {e}")
            return False

    def _extract_websocket_without_performance_logging(self):
        """새 DevTools + WebSocketParser로 웹소켓 URL 추출"""
        try:
            self.logger.info("🚀 새로운 방식의 웹소켓 URL 추출 시작")

            ws_parser = WebSocketParser(self.devtools, self.logger)

            QMessageBox.information(
                self.main_window,
                "웹소켓 URL 추출 중",
                "자동으로 웹소켓 URL을 추출 중입니다. 잠시만 기다려주세요."
            )

            websocket_url = ws_parser.get_best_websocket_url()

            if websocket_url:
                self.logger.info(f"✅ 웹소켓 URL 추출 성공: {websocket_url[:100]}...")
                QMessageBox.information(
                    self.main_window,
                    "성공",
                    "웹소켓 URL을 성공적으로 추출했습니다."
                )
                return websocket_url

            else:
                self.logger.error("❌ 웹소켓 URL 추출 실패")
                QMessageBox.critical(
                    self.main_window,
                    "실패",
                    "웹소켓 URL을 추출할 수 없습니다."
                )
                return None

        except Exception as e:
            self.logger.error(f"웹소켓 URL 추출 오류: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "오류",
                f"웹소켓 URL 추출 중 오류가 발생했습니다: {e}"
            )
            return None
            
    def _show_websocket_extraction_progress(self):
        """웹소켓 추출 진행 상황 안내"""
        try:
            QMessageBox.information(
                self.main_window,
                "웹소켓 URL 추출 중",
                "웹소켓 URL을 자동으로 추출하고 있습니다.\n\n" +
                "⏳ 최대 1분 정도 소요될 수 있습니다.\n" +
                "🎮 이 시간 동안 에볼루션 페이지에서 게임을 클릭하거나\n" +
                "    로비를 둘러보시면 추출이 더 빨라집니다.\n\n" +
                "잠시만 기다려주세요..."
            )
        except Exception as e:
            self.logger.warning(f"진행 상황 안내 표시 실패: {e}")

    def _request_manual_websocket_url(self):
        """최후의 수단: 사용자에게 수동 입력 요청"""
        try:
            self.logger.info("🙋 사용자에게 수동 웹소켓 URL 입력 요청")
            
            from PyQt6.QtWidgets import QInputDialog, QTextEdit, QVBoxLayout, QDialog, QPushButton, QLabel
            
            # 커스텀 다이얼로그 생성
            dialog = QDialog(self.main_window)
            dialog.setWindowTitle("웹소켓 URL 수동 입력 (최후의 수단)")
            dialog.setFixedSize(700, 500)
            
            layout = QVBoxLayout()
            
            # 안내 텍스트
            instructions = QLabel("""
❌ 자동 웹소켓 URL 추출에 실패했습니다.

🔍 수동으로 웹소켓 URL을 찾는 방법:

1. F12 키를 눌러 개발자 도구를 엽니다
2. 'Network' 탭을 클릭합니다  
3. 필터에서 'WS' (WebSocket)를 선택합니다
4. 에볼루션 페이지에서 게임을 클릭하거나 새로고침(F5)합니다
5. 웹소켓 연결이 나타나면 클릭합니다
6. 'Headers' 탭에서 'Request URL'을 복사합니다

📝 예시 URL 형태:
wss://skylinestart.evo-games.com/public/lobby/socket/v2?sessionId=...

⚠️ 이 단계를 건너뛰면 자동 매매를 사용할 수 없습니다.
            """)
            instructions.setWordWrap(True)
            instructions.setStyleSheet("font-size: 11px; padding: 10px;")
            layout.addWidget(instructions)
            
            # 입력 필드
            url_input = QTextEdit()
            url_input.setPlaceholderText("웹소켓 URL을 여기에 붙여넣기하세요 (wss://로 시작)")
            url_input.setMaximumHeight(80)
            layout.addWidget(url_input)
            
            # 버튼들
            button_layout = QVBoxLayout()
            
            confirm_btn = QPushButton("✅ 확인하고 계속 진행")
            cancel_btn = QPushButton("❌ 취소 (자동 매매 중단)")
            
            button_layout.addWidget(confirm_btn)
            button_layout.addWidget(cancel_btn)
            
            layout.addLayout(button_layout)
            dialog.setLayout(layout)
            
            result = {"url": None}
            
            def on_confirm():
                url = url_input.toPlainText().strip()
                if url:
                    # 기본 검증
                    if url.startswith('wss://') and len(url) > 30:
                        result["url"] = url
                        dialog.accept()
                    else:
                        QMessageBox.warning(dialog, "입력 오류", 
                                          "올바른 웹소켓 URL을 입력해주세요.\n(wss://로 시작하는 긴 URL)")
                else:
                    QMessageBox.warning(dialog, "입력 오류", "웹소켓 URL을 입력해주세요.")
            
            def on_cancel():
                dialog.reject()
            
            confirm_btn.clicked.connect(on_confirm)
            cancel_btn.clicked.connect(on_cancel)
            
            if dialog.exec() == QDialog.DialogCode.Accepted and result["url"]:
                manual_url = result["url"]
                self.logger.info(f"✅ 사용자가 수동으로 입력한 웹소켓 URL: {manual_url[:100]}...")
                return manual_url
            
            return None
            
        except Exception as e:
            self.logger.error(f"수동 입력 처리 중 오류: {e}")
            return None

    def process_server_monitoring_data(self, monitoring_data):
        """서버 모니터링 데이터 처리"""
        try:
            # 서버에서 받은 연패 데이터 확인
            streak_data = monitoring_data.get('streak_data', {})
            player_streak_rooms = streak_data.get('player_streak_rooms', [])
            
            # 현재 방이 여전히 조건에 맞는지 확인
            current_room_still_valid = False
            for room in player_streak_rooms:
                if room.get('room_name') == self.current_room_name:
                    current_room_still_valid = True
                    break
            
            # 현재 방이 조건에 맞지 않으면 새로운 방 검색
            if not current_room_still_valid and player_streak_rooms:
                self.logger.info("현재 방이 더 이상 조건에 맞지 않습니다. 새로운 방으로 이동합니다.")
                self.change_to_new_recommended_room(player_streak_rooms[0])
                
        except Exception as e:
            self.logger.error(f"서버 모니터링 데이터 처리 오류: {e}")

    def change_to_new_recommended_room(self, new_room_data):
        """새로 추천받은 방으로 이동"""
        try:
            new_room_name = new_room_data.get('room_name', '')
            
            if new_room_name and new_room_name != self.current_room_name:
                self.logger.info(f"새로운 추천 방으로 이동: {new_room_name}")
                
                # 현재 방 나가기
                self.game_monitoring_service.close_current_room()
                
                # 새 방 입장
                if self.enter_recommended_room(new_room_name):
                    self.logger.info(f"방 이동 완료: {self.current_room_name} → {new_room_name}")
                else:
                    self.logger.warning("새 방 입장 실패, 방 검색 재시작")
                    self.start_server_based_room_search()
                    
        except Exception as e:
            self.logger.error(f"방 이동 오류: {e}", exc_info=True)

    def execute_betting_if_needed(self, game_state):
        """필요시 베팅 실행"""
        try:
            # 이미 베팅했다면 결과 대기
            if self.betting_service.has_bet_current_round:
                latest_result = game_state.get('latest_result')
                if latest_result and latest_result in ['P', 'B', 'T']:
                    # 베팅 결과 처리
                    last_bet = self.betting_service.get_last_bet()
                    if last_bet:
                        result_status = self.bet_helper.process_bet_result(
                            last_bet['type'], 
                            latest_result, 
                            game_state.get('round', 0)
                        )
                        self.logger.info(f"베팅 결과: {result_status}")
                        
                        # 결과에 따른 후속 처리
                        if result_status == 'win':
                            # 승리 시 새로운 방 검색
                            self.start_server_based_room_search()
                        elif result_status == 'lose':
                            # 패배 시 계속 진행 (마틴 베팅)
                            pass
                return
            
            # 첫 결과 대기 중이면 베팅하지 않음
            if self.wait_first_result:
                self.logger.debug("첫 결과 대기 중 - 베팅 보류")
                return
            
            # 새로운 베팅 필요한 경우
            if game_state.get('betting_available', False):
                # 베팅 픽 결정 (ExcelTradingService 활용)
                pick = self._determine_bet_pick(game_state)
                
                if pick in ['P', 'B']:
                    current_widget_pos = get_widget_position(self.main_window)
                    bet_amount = self.excel_trading_service.get_current_bet_amount(widget_position=current_widget_pos)
                    
                    # 베팅 실행
                    bet_success = self.betting_service.place_bet(
                        pick,
                        self.current_room_name,
                        game_state.get('round', 0),
                        self.is_trading_active,
                        bet_amount
                    )
                    
                    if bet_success:
                        self.logger.info(f"베팅 성공: {pick}, 금액: {bet_amount:,}원")
                        self.main_window.update_betting_status(pick=pick, bet_amount=bet_amount)
                
        except Exception as e:
            self.logger.error(f"베팅 실행 오류: {e}", exc_info=True)

    def _determine_bet_pick(self, game_state):
        """베팅 픽 결정"""
        try:
            # ExcelTradingService의 choice_pick_system 사용
            if hasattr(self.excel_trading_service, 'choice_pick_system'):
                pick = self.excel_trading_service.choice_pick_system.generate_choice_pick()
                if pick in ['P', 'B']:
                    return pick
            
            # 폴백: 간단한 패턴 기반 픽
            recent_results = game_state.get('filtered_results', [])
            if recent_results:
                last_result = recent_results[-1]
                return 'B' if last_result == 'P' else 'P'  # 반대 패턴
            
            return 'P'  # 기본값
            
        except Exception as e:
            self.logger.error(f"베팅 픽 결정 오류: {e}")
            return 'P'

    # 이전 복잡한 분석 메서드들은 주석 처리하거나 단순화
    def analyze_current_game(self):
        """현재 게임 상태 분석 - 단순화됨"""
        # 서버 기반 시스템에서는 이 메서드가 필요하지 않음
        # 대신 check_betting_conditions()를 사용
        if self.is_trading_active:
            self.check_betting_conditions()

    def run_auto_trading(self):
        """자동 매매 루프 - 단순화됨"""
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 비활성화되어 있습니다.")
                return
                
            self.logger.info("자동 매매 진행 중...")
            
            # 베팅 조건 확인
            self.check_betting_conditions()
            
            # 게임 모니터링 루프 설정
            monitoring_interval = 2  # 2초마다 체크
            self.main_window.set_remaining_time(0, 0, monitoring_interval)

        except Exception as e:
            self.logger.error(f"자동 매매 실행 중 오류 발생: {e}", exc_info=True)
            self.stop_trading()
            
            QMessageBox.critical(
                self.main_window, 
                "자동 매매 오류", 
                f"자동 매매 중 심각한 오류가 발생했습니다.\n자동 매매가 중지됩니다.\n오류: {str(e)}"
            )