# utils/trading_manager.py - 전체 코드

import time
import logging
from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import QTimer

# 기존 imports
from services.room_entry_service import RoomEntryService
from services.excel_trading_service import ExcelTradingService
from services.betting_service import BettingService
from services.game_monitoring_service import GameMonitoringService
from services.balance_service import BalanceService
from services.martin_service import MartinBettingService
from utils.settings_manager import SettingsManager
from utils.trading_manager_helpers import TradingManagerHelpers, get_widget_position
from utils.devtools import DevToolsController
from utils.unified_server_client import get_server_client

# 분할된 모듈들 import
from utils.trading_manager_modules.streak_handler import StreakHandler
from utils.trading_manager_modules.websocket_manager import WebSocketManager
from utils.trading_manager_modules.game_processor import GameProcessor
from utils.trading_manager_modules.betting_executor import BettingExecutor
from utils.trading_manager_modules.room_entry_handler import RoomEntryHandler


class TradingManager:
    """연패 감지 및 자동 방 입장 기반 자동매매 매니저"""

    def __init__(self, main_window, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.main_window = main_window
        
        # DevTools 설정
        if hasattr(main_window, 'devtools') and main_window.devtools:
            self.devtools = main_window.devtools
            self.logger.info("✅ 메인 윈도우의 기존 DevTools 인스턴스 사용")
        else:
            self.devtools = DevToolsController(logger=self.logger)
            self.logger.info("⚠️ 새로운 DevTools 인스턴스 생성")
        
        self.room_manager = main_window.room_manager
        self.settings_manager = SettingsManager()
        self.server_client = get_server_client(logger=self.logger)
        
        # 상태 관리 속성들
        self._init_state_variables()
        
        # 서비스 클래스 초기화
        self._init_services()

        # 기존 헬퍼 클래스들
        from utils.trading_manager_helpers import TradingManagerHelpers
        from utils.trading_manager_bet import TradingManagerBet  
        from utils.trading_manager_game import TradingManagerGame
        
        self.helpers = TradingManagerHelpers(self)
        self.bet_helper = TradingManagerBet(self)
        self.game_helper = TradingManagerGame(self)
        
        # 새로운 분할된 매니저들 초기화
        self.streak_handler = StreakHandler(self)
        self.websocket_manager = WebSocketManager(self)
        self.game_processor = GameProcessor(self)
        self.betting_executor = BettingExecutor(self)
        self.room_manager_handler = RoomEntryHandler(self)
        
    def _init_state_variables(self):
        """상태 변수들 초기화"""
        # 기본 상태
        self.is_trading_active = False
        self.current_room_name = ""
        self.game_count = 0
        self.result_count = 0
        self.current_pick = None
        self.processed_rounds = set()
        
        # 웹소켓 상태
        self.websocket_intercepting = False
        self.last_game_data = None
        self.message_count = 0
        
        # 연패 방 관리
        self.target_streak_rooms = []
        self.current_target_room = None
        self.is_entering_room = False
        self.room_entry_in_progress = False
        self.excluded_rooms = {}  # 🔥 제외된 방 리스트 {room_id: {'timestamp': time, 'reason': 'martin_fail|condition_fail'}}
        self.first_bet_after_entry = False  # 🔥 입장 직후 첫 베팅 플래그
        
        # 기타 상태
        self.wait_first_result = False
        self.stop_all_processes = False
        self.had_tie_last_round = False
        self.just_won = False
        self._should_move_to_next_room = False
        
    def _init_services(self):
        """서비스 객체들을 초기화 (지연 초기화로 변경)"""
        # 서비스들을 None으로 초기화
        self.betting_service = None
        self.game_monitoring_service = None
        self.balance_service = None
        self.room_entry_service = None
        self.excel_trading_service = None
        self.martin_service = None
        
        # devtools가 있지만 driver가 없는 경우는 정상적인 초기 상태
        if self.devtools and hasattr(self.devtools, 'driver') and self.devtools.driver:
            self._create_services()
        else:
            self.logger.info("DevTools driver가 아직 초기화되지 않음 - 서비스 생성 지연")
    
    def _create_services(self):
        """실제 서비스 객체 생성"""
        try:
            if not self.devtools or not self.devtools.driver:
                self.logger.warning("DevTools driver가 여전히 None입니다")
                return False
                
            self.betting_service = BettingService(
                devtools=self.devtools, main_window=self.main_window, logger=self.logger)
            self.game_monitoring_service = GameMonitoringService(
                devtools=self.devtools, main_window=self.main_window, logger=self.logger)
            self.balance_service = BalanceService(
                devtools=self.devtools, main_window=self.main_window, logger=self.logger)
            self.room_entry_service = RoomEntryService(
                devtools=self.devtools, main_window=self.main_window, 
                room_manager=self.room_manager, logger=self.logger)
            self.excel_trading_service = ExcelTradingService(
                main_window=self.main_window, logger=self.logger)
            self.martin_service = MartinBettingService(
                main_window=self.main_window, logger=self.logger)
            
            self.logger.info(f"모든 서비스 초기화 완료 (driver: {type(self.devtools.driver)})")
            return True
        except Exception as e:
            self.logger.error(f"서비스 생성 오류: {e}", exc_info=True)
            return False

    def start_trading(self):
        """자동 매매 시작 - 핵심 로직만 유지"""
        try:
            self.logger.info("🚀 연패 감지 자동 매매 시작")
            
            # 서비스가 아직 생성되지 않았다면 생성 시도
            if self.betting_service is None:
                self.logger.info("서비스가 아직 초기화되지 않음 - 생성 시도")
                if not self._create_services():
                    self.logger.error("서비스 생성 실패 - 자동매매 불가")
                    QMessageBox.critical(self.main_window, "오류", "서비스 초기화 실패\n브라우저가 실행되었는지 확인하세요.")
                    return
            
            if not self.helpers.validate_trading_prerequisites():
                return
            
            self.refresh_settings()
            if self.balance_service and hasattr(self.balance_service, '_target_amount_reached'):
                del self.balance_service._target_amount_reached
            
            self.stop_all_processes = False
            
            if not self._check_server_connection():
                return
            if not self._ensure_evolution_lobby_ready():
                return
            if not self.websocket_manager.start_websocket_service():
                QMessageBox.warning(self.main_window, "웹소켓 서비스 실패", 
                    "연패 감지 웹소켓 서비스를 시작할 수 없습니다.")
                return

            self.is_trading_active = True
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(True)
            self.main_window.update_button_styles()
            
            self.streak_handler.start_streak_monitoring()
            self.logger.info("🎯 연패 감지 자동 매매 시작 완료")

        except Exception as e:
            self.logger.error(f"자동 매매 시작 오류: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, "자동 매매 오류", 
                f"자동 매매 시작 중 오류가 발생했습니다.\n{str(e)}")

    def stop_trading(self):
        """자동 매매 중지"""
        if not self.is_trading_active:
            return
            
        self.logger.info("🛑 연패 감지 자동 매매 중지 중...")
        
        self.websocket_manager.stop_websocket_service()
        self._reset_all_states()
        self._reset_ui_states()
        
        self.logger.info("✅ 연패 감지 자동 매매 중지 완료")
        
        target_reached = (hasattr(self.balance_service, '_target_amount_reached') and 
                         self.balance_service._target_amount_reached)
        if not target_reached:
            QMessageBox.information(self.main_window, "알림", "자동 매매가 중지되었습니다.")

    def _reset_all_states(self):
        """모든 상태 초기화"""
        self.stop_all_processes = True
        self.is_trading_active = False
        self.websocket_intercepting = False
        self.game_count = 0
        self.result_count = 0
        self.current_pick = None
        self.processed_rounds = set()
        self.message_count = 0
        self.target_streak_rooms = []
        self.current_target_room = None
        self.room_entry_in_progress = False
        self.is_entering_room = False
        
        if hasattr(self, 'betting_service'):
            self.betting_service.reset_betting_state()
        if hasattr(self, 'martin_service'):
            self.martin_service.reset()

    def _reset_ui_states(self):
        """UI 상태 초기화"""
        if hasattr(self.main_window, 'timer') and self.main_window.timer.isActive():
            self.main_window.timer.stop()
            QApplication.processEvents()
        
        self.main_window.start_button.setEnabled(True)
        self.main_window.stop_button.setEnabled(False)
        self.main_window.update_button_styles()
        
        if self.current_room_name:
            try:
                if hasattr(self, 'game_monitoring_service'):
                    self.game_monitoring_service.close_current_room()
            except:
                pass

    def _check_server_connection(self) -> bool:
        """서버 연결 상태 확인"""
        try:
            self.logger.info("🔍 서버 연결 상태 확인 중...")
            if self.server_client.get_server_status():
                self.logger.info("✅ 서버 연결 성공")
                return True
            else:
                QMessageBox.warning(self.main_window, "서버 연결 실패", 
                    "서버에 연결할 수 없습니다.\n서버 상태를 확인해주세요.")
                return False
        except Exception as e:
            self.logger.error(f"서버 연결 확인 오류: {e}")
            QMessageBox.critical(self.main_window, "서버 오류", 
                f"서버 연결 확인 중 오류가 발생했습니다.\n{str(e)}")
            return False

    def _ensure_evolution_lobby_ready(self):
        """에볼루션 로비 준비 상태 확인"""
        try:
            window_handles = self.devtools.driver.window_handles
            if len(window_handles) < 2:
                QMessageBox.information(self.main_window, "에볼루션 접속 필요", 
                    "에볼루션 카지노에 먼저 접속해주세요.")
                return False
            
            self.devtools.driver.switch_to.window(window_handles[1])
            self.logger.info("에볼루션 로비 창으로 전환 완료")
            
            if not self.helpers.setup_browser_and_check_balance():
                return False
            return True
        except Exception as e:
            self.logger.error(f"에볼루션 로비 준비 오류: {e}")
            return False

    def refresh_settings(self):
        """설정 새로고침"""
        try:
            self.settings_manager = SettingsManager()
            services = ['balance_service', 'martin_service', 'room_entry_service', 'excel_trading_service']
            for service_name in services:
                if hasattr(self, service_name):
                    service = getattr(self, service_name)
                    if hasattr(service, 'settings_manager'):
                        service.settings_manager = self.settings_manager
            
            martin_count, martin_amounts = self.settings_manager.get_martin_settings()
            if hasattr(self, 'excel_trading_service'):
                self.excel_trading_service.set_martin_amounts(martin_amounts)
            
            if hasattr(self.websocket_manager, 'websocket_service') and self.websocket_manager.websocket_service:
                # 🔥 설정에서 최소 연패 조건 가져오기
                min_streak = self.settings_manager.get_min_streak()
                self.websocket_manager.websocket_service.update_streak_threshold(min_streak)
                    
            # 🔥 연패 조건도 로그에 출력
            min_streak = self.settings_manager.get_min_streak()
            self.logger.info(f"설정 새로고침 완료 - 마틴: {martin_count}단계, {martin_amounts}, 최소 연패: {min_streak}회")
            return True
        except Exception as e:
            self.logger.error(f"설정 새로고침 오류: {e}")
            return False

    # ==================== 위임 메서드들 ====================
    def get_interceptor_status(self) -> dict:
        return self.websocket_manager.get_interceptor_status()
    
    def get_current_status(self):
        service_status = self.get_interceptor_status()
        return {
            'is_active': self.is_trading_active,
            'websocket_intercepting': self.websocket_intercepting,
            'current_room': self.current_room_name,
            'game_count': self.game_count,
            'result_count': self.result_count,
            'has_bet': getattr(self.betting_service, 'has_bet_current_round', False) if hasattr(self, 'betting_service') else False,
            'wait_first_result': self.wait_first_result,
            'stop_flag': self.stop_all_processes,
            'service_status': service_status,
            'message_count': self.message_count,
            'last_game_data': self.last_game_data,
            'target_streak_rooms': len(self.target_streak_rooms),
            'current_target_room': self.current_target_room,  
            'room_entry_in_progress': self.room_entry_in_progress,
            'server_connected': bool(self.server_client and self.server_client.get_server_status()),
            'betting_tracker_status': self.get_current_bet_status() if hasattr(self, 'game_processor') else None
        }

    def force_collect_data(self):
        return self.websocket_manager.force_collect_data()

    def force_reconnect_websocket(self):
        return self.websocket_manager.force_reconnect_websocket()

    def get_streak_room_info(self):
        return self.streak_handler.get_streak_room_info()

    def debug_service_status(self):
        return self.websocket_manager.debug_service_status()

    def emergency_stop(self):
        self.logger.warning("🚨 비상 정지 실행")
        self.stop_all_processes = True
        self.is_trading_active = False
        self.websocket_intercepting = False
        self.websocket_manager.emergency_stop()
        
        if hasattr(self.main_window, 'timer'):
            self.main_window.timer.stop()
            QApplication.processEvents()
        
        self.target_streak_rooms = []
        self.current_target_room = None
        self.room_entry_in_progress = False
        self.is_entering_room = False
        
        self.main_window.start_button.setEnabled(True)
        self.main_window.stop_button.setEnabled(False)
        self.main_window.update_button_styles()
        self.logger.info("비상 정지 완료")

    # 베팅 추적 관련 메서드들
    def get_betting_status_summary(self):
        """베팅 상태 요약 정보 반환"""
        try:
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                betting_stats = self.game_processor.get_betting_statistics()
                tracker_info = self.game_processor.betting_tracker.get_current_bet_info()
                
                return {
                    'is_active': self.is_trading_active,
                    'current_room': self.current_room_name,
                    'game_count': self.game_count,
                    'betting_status': tracker_info.get('status', 'idle'),
                    'waiting_for_result': self.game_processor.betting_tracker.is_waiting_for_result(),
                    'bet_round': self.game_processor.betting_tracker.get_bet_round(),
                    'bet_type': self.game_processor.betting_tracker.get_bet_type(),
                    'statistics': betting_stats
                }
            else:
                return {
                    'is_active': self.is_trading_active,
                    'current_room': self.current_room_name,
                    'game_count': self.game_count,
                    'betting_status': 'idle',
                    'waiting_for_result': False,
                    'bet_round': None,
                    'bet_type': None,
                    'statistics': {}
                }
        except Exception as e:
            self.logger.error(f"베팅 상태 요약 조회 오류: {e}")
            return {'error': str(e)}

    def debug_betting_system(self):
        """베팅 시스템 전체 디버그"""
        try:
            self.logger.info("🔍 베팅 시스템 전체 상태 디버그:")
            
            # 기본 상태
            self.logger.info(f"  - 자동 매매 활성: {self.is_trading_active}")
            self.logger.info(f"  - 현재 방: {self.current_room_name}")
            self.logger.info(f"  - 게임 카운트: {self.game_count}")
            self.logger.info(f"  - 결과 카운트: {self.result_count}")
            
            # 베팅 추적기 상태
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                self.game_processor.debug_betting_tracker_status()
            
            # 연패 방 상태
            if hasattr(self, 'streak_handler'):
                streak_info = self.streak_handler.get_streak_room_info()
                self.logger.info(f"  - 타겟 연패 방: {streak_info.get('room_count', 0)}개")
                self.logger.info(f"  - 현재 타겟 방: {streak_info.get('current_target_room')}")
                self.logger.info(f"  - 방 입장 진행 중: {streak_info.get('room_entry_in_progress', False)}")
            
            # 웹소켓 상태
            websocket_status = self.get_interceptor_status()
            self.logger.info(f"  - 웹소켓 인터셉트: {websocket_status.get('is_intercepting', False)}")
            self.logger.info(f"  - 처리된 메시지: {websocket_status.get('processed_messages', 0)}")
            
        except Exception as e:
            self.logger.error(f"베팅 시스템 디버그 오류: {e}")

    def force_exit_current_room(self):
        """강제로 현재 방 나가기"""
        try:
            self.logger.info("🚪 강제 방 나가기 실행")
            
            # 베팅 추적기 초기화
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                self.game_processor.betting_tracker.reset_tracking()
            
            # 현재 방에서 나가기
            if hasattr(self, 'game_monitoring_service'):
                self.game_monitoring_service.close_current_room()
            
            # 상태 초기화
            self.current_room_name = ""
            self.current_target_room = None
            self.game_count = 0
            self.result_count = 0
            
            # 베팅 서비스 초기화
            if hasattr(self, 'betting_service'):
                self.betting_service.reset_betting_state()
            
            # 연패 모니터링으로 복귀
            if hasattr(self, 'streak_handler'):
                self.streak_handler.return_to_streak_monitoring()
            
            self.logger.info("✅ 강제 방 나가기 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"강제 방 나가기 오류: {e}")
            return False

    def get_betting_history(self, count: int = 10):
        """베팅 히스토리 조회"""
        try:
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                return self.game_processor.betting_tracker.get_recent_results(count)
            else:
                return []
        except Exception as e:
            self.logger.error(f"베팅 히스토리 조회 오류: {e}")
            return []

    def get_performance_metrics(self):
        """성과 지표 조회"""
        try:
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                tracker = self.game_processor.betting_tracker
                
                return {
                    'win_rate_5': tracker.get_win_rate(5),
                    'win_rate_10': tracker.get_win_rate(10),
                    'consecutive_wins': tracker.get_consecutive_results()['consecutive_wins'],
                    'consecutive_losses': tracker.get_consecutive_results()['consecutive_losses'],
                    'profit_loss_5': tracker.get_total_profit_loss(5),
                    'profit_loss_10': tracker.get_total_profit_loss(10),
                    'total_games': len(tracker.betting_history),
                    'should_change_room': tracker.should_change_room()
                }
            else:
                return {
                    'win_rate_5': 0.0,
                    'win_rate_10': 0.0,
                    'consecutive_wins': 0,
                    'consecutive_losses': 0,
                    'profit_loss_5': 0,
                    'profit_loss_10': 0,
                    'total_games': 0,
                    'should_change_room': False
                }
        except Exception as e:
            self.logger.error(f"성과 지표 조회 오류: {e}")
            return {'error': str(e)}

    def get_current_bet_status(self):
        """현재 베팅 상태만 간단히 반환"""
        try:
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                tracker = self.game_processor.betting_tracker
                bet_info = tracker.get_current_bet_info()
                
                return {
                    'status': bet_info.get('status', 'idle'),
                    'waiting_for_result': tracker.is_waiting_for_result(),
                    'bet_type': tracker.get_bet_type(),
                    'bet_round': tracker.get_bet_round(),
                    'bet_info': bet_info.get('bet_info', {}),
                    'result_info': bet_info.get('result_info', {})
                }
            else:
                return {
                    'status': 'idle',
                    'waiting_for_result': False,
                    'bet_type': None,
                    'bet_round': None,
                    'bet_info': {},
                    'result_info': {}
                }
        except Exception as e:
            self.logger.error(f"현재 베팅 상태 조회 오류: {e}")
            return {'error': str(e)}

    # 추가 메서드들
    def handle_betting_cycle_complete(self, betting_result: str):
        """베팅 사이클 완료 처리"""
        try:
            self.logger.info(f"🔄 베팅 사이클 완료: {betting_result}")
            
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                tracker = self.game_processor.betting_tracker
                
                recent_results = tracker.get_recent_results(10)
                win_rate = tracker.get_win_rate(10)
                consecutive = tracker.get_consecutive_results()
                total_pnl = tracker.get_total_profit_loss(10)
                
                self.logger.info(f"📊 베팅 성과 분석:")
                self.logger.info(f"  - 최근 10게임 승률: {win_rate}%")
                self.logger.info(f"  - 연속 승: {consecutive['consecutive_wins']}회")
                self.logger.info(f"  - 연속 패: {consecutive['consecutive_losses']}회")
                self.logger.info(f"  - 총 손익: {total_pnl:,}원")
                
                if tracker.should_change_room():
                    self.logger.info("🚪 3연패로 방 이동 필요")
                    self._initiate_room_change()
                elif betting_result == "win":
                    self.logger.info("🎉 승리로 새 연패 방 검색")
                    self._search_new_streak_room()
            
        except Exception as e:
            self.logger.error(f"베팅 사이클 완료 처리 오류: {e}")

    def _initiate_room_change(self):
        """방 이동 시작"""
        try:
            if hasattr(self, 'room_manager_handler'):
                self.room_manager_handler.handle_room_exit()
            
            if hasattr(self, 'game_monitoring_service'):
                self.game_monitoring_service.close_current_room()
            
            self._search_new_streak_room()
            
        except Exception as e:
            self.logger.error(f"방 이동 시작 오류: {e}")

    def _search_new_streak_room(self):
        """새 연패 방 검색"""
        try:
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                if self.game_processor.betting_tracker.is_waiting_for_result():
                    self.logger.warning("베팅 결과 대기 중 - 새 방 검색 보류")
                    return
            
            if hasattr(self, 'streak_handler'):
                self.streak_handler.return_to_streak_monitoring()
            
        except Exception as e:
            self.logger.error(f"새 연패 방 검색 오류: {e}")

    def validate_betting_conditions(self) -> bool:
        """베팅 조건 검증"""
        try:
            if not self.is_trading_active:
                return False
            
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                tracker = self.game_processor.betting_tracker
                
                if tracker.is_waiting_for_result():
                    self.logger.info("이미 베팅 결과 대기 중 - 새 베팅 불가")
                    return False
                
                consecutive = tracker.get_consecutive_results()
                if consecutive['consecutive_losses'] >= 3:
                    self.logger.warning("3연패 중 - 방 이동 필요")
                    return False
            
            if not self.current_target_room:
                self.logger.warning("타겟 방이 없음 - 베팅 불가")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"베팅 조건 검증 오류: {e}")
            return False

    def get_comprehensive_status(self) -> dict:
        """종합 상태 정보"""
        try:
            base_status = self.get_current_status()
            
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                betting_stats = self.game_processor.get_betting_statistics()
                tracker_status = self.game_processor.betting_tracker.get_current_bet_info()
                
                base_status.update({
                    'betting_tracker': {
                        'status': tracker_status.get('status', 'idle'),
                        'waiting_for_result': self.game_processor.betting_tracker.is_waiting_for_result(),
                        'bet_type': self.game_processor.betting_tracker.get_bet_type(),
                        'bet_round': self.game_processor.betting_tracker.get_bet_round(),
                        'statistics': betting_stats
                    }
                })
            
            if hasattr(self, 'room_manager_handler'):
                base_status['room_management'] = {
                    'current_room': self.current_room_name,
                    'target_room': self.current_target_room,
                    'entry_in_progress': self.room_entry_in_progress,
                    'streak_rooms_count': len(self.target_streak_rooms)
                }
            
            return base_status
            
        except Exception as e:
            self.logger.error(f"종합 상태 조회 오류: {e}")
            return {'error': str(e)}

    def handle_unexpected_disconnect(self):
        """예기치 않은 연결 끊김 처리"""
        try:
            self.logger.warning("⚠️ 예기치 않은 연결 끊김 감지")
            
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                tracker = self.game_processor.betting_tracker
                
                if tracker.is_waiting_for_result():
                    bet_info = tracker.get_current_bet_info()
                    self.logger.warning(f"미확인 베팅: {bet_info}")
                    self._save_pending_bet_info(bet_info)
            
            self.stop_trading()
            
        except Exception as e:
            self.logger.error(f"연결 끊김 처리 오류: {e}")

    def _save_pending_bet_info(self, bet_info: dict):
        """미확인 베팅 정보 저장"""
        try:
            import json
            import os
            
            temp_file = "pending_bet.json"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(bet_info, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"미확인 베팅 정보 저장: {temp_file}")
            
        except Exception as e:
            self.logger.error(f"베팅 정보 저장 오류: {e}")

    def restore_pending_bet_info(self):
        """저장된 미확인 베팅 정보 복구"""
        try:
            import json
            import os
            
            temp_file = "pending_bet.json"
            if os.path.exists(temp_file):
                with open(temp_file, 'r', encoding='utf-8') as f:
                    bet_info = json.load(f)
                
                self.logger.info(f"미확인 베팅 정보 복구: {bet_info}")
                os.remove(temp_file)
                return bet_info
            
            return None
            
        except Exception as e:
            self.logger.error(f"베팅 정보 복구 오류: {e}")
            return None

    # 기존 호환성 메서드들
    def get_websocket_status(self):
        return self.get_interceptor_status()

    def get_recent_websocket_messages(self, count=10):
        return []

    def debug_interceptor_status(self):
        return self.debug_service_status()

    def simulate_betting_result(self, game_result: str):
        """베팅 결과 시뮬레이션 (테스트용)"""
        try:
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                if self.game_processor.betting_tracker.is_waiting_for_result():
                    bet_round = self.game_processor.betting_tracker.get_bet_round()
                    if bet_round:
                        result = self.game_processor.betting_tracker.check_result(
                            bet_round + 1, game_result
                        )
                        
                        if result:
                            self.logger.info(f"🧪 시뮬레이션 결과: {result.value}")
                            
                            if result.value == 'tie':
                                self.game_processor._handle_tie_result_tracked()
                            elif result.value == 'win':
                                self.game_processor._handle_win_result_tracked()
                            elif result.value == 'lose':
                                self.game_processor._handle_lose_result_tracked()
                            
                            return True
                        else:
                            self.logger.warning("시뮬레이션 결과 처리 실패")
                            return False
                    else:
                        self.logger.warning("베팅 라운드 정보가 없음")
                        return False
                else:
                    self.logger.warning("베팅 결과 대기 중이 아님")
                    return False
            else:
                self.logger.warning("베팅 추적기가 없음")
                return False
                
        except Exception as e:
            self.logger.error(f"베팅 결과 시뮬레이션 오류: {e}")
            return False

    def reset_betting_tracker(self):
        """베팅 추적기 초기화"""
        try:
            if hasattr(self, 'game_processor') and hasattr(self.game_processor, 'betting_tracker'):
                self.game_processor.betting_tracker.reset_tracking()
                self.logger.info("베팅 추적기 초기화 완료")
                return True
            else:
                self.logger.warning("베팅 추적기가 없음")
                return False
        except Exception as e:
            self.logger.error(f"베팅 추적기 초기화 오류: {e}")
            return False

    def __del__(self):
        try:
            if hasattr(self, 'websocket_manager'):
                self.websocket_manager.cleanup()
        except:
            pass