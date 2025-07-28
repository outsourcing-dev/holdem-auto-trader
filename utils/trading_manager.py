# ==================== 1. utils/trading_manager.py (메인 파일) ====================

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
        
        # 기타 상태
        self.wait_first_result = False
        self.stop_all_processes = False
        self.had_tie_last_round = False
        self.just_won = False
        self._should_move_to_next_room = False
        
    def _init_services(self):
        """서비스 객체들을 초기화"""
        try:
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
            
            self.logger.info("모든 서비스 초기화 완료")
        except Exception as e:
            self.logger.error(f"서비스 초기화 오류: {e}", exc_info=True)

    def start_trading(self):
        """자동 매매 시작 - 핵심 로직만 유지"""
        try:
            self.logger.info("🚀 연패 감지 자동 매매 시작")
            
            if not self.helpers.validate_trading_prerequisites():
                return
            
            self.refresh_settings()
            if hasattr(self.balance_service, '_target_amount_reached'):
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
                streak_threshold = getattr(self.settings_manager, 'streak_threshold', 3)
                self.websocket_manager.websocket_service.update_streak_threshold(streak_threshold)
                    
            self.logger.info(f"설정 새로고침 완료 - 마틴: {martin_count}단계, {martin_amounts}")
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
            'server_connected': bool(self.server_client and self.server_client.get_server_status())
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

    # 기존 호환성 메서드들
    def get_websocket_status(self):
        return self.get_interceptor_status()

    def get_recent_websocket_messages(self, count=10):
        return []

    def debug_interceptor_status(self):
        return self.debug_service_status()

    def __del__(self):
        try:
            if hasattr(self, 'websocket_manager'):
                self.websocket_manager.cleanup()
        except:
            pass