# utils/trading_manager_interceptor.py
"""
웹소켓 인터셉터 기반 TradingManager
- 기존 웹소켓 연결을 모니터링하여 게임 데이터 수집
- 직접 연결 없이 CDP를 통한 메시지 가로채기
"""

import time
import logging
from PyQt6.QtWidgets import QMessageBox, QApplication
from PyQt6.QtCore import QThread

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

# 새로운 웹소켓 인터셉터
from services.websocket_interceptor import WebSocketInterceptor

class TradingManagerInterceptor:
    """웹소켓 인터셉터 기반 자동매매 매니저"""

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

        # 웹소켓 인터셉터
        self.websocket_interceptor = None
        
        # 상태 관리 속성
        self.is_trading_active = False
        self.current_room_name = ""
        self.game_count = 0
        self.result_count = 0
        self.current_pick = None
        self.processed_rounds = set()
        
        # 웹소켓 데이터 상태
        self.websocket_intercepting = False
        self.last_game_data = None
        self.message_count = 0
        
        # 기타 상태 변수
        self.wait_first_result = False
        self.stop_all_processes = False
        self.had_tie_last_round = False
        self.just_won = False

        # 서비스 클래스 초기화
        self._init_services()

        # 헬퍼 클래스들 초기화
        from utils.trading_manager_helpers import TradingManagerHelpers
        from utils.trading_manager_bet import TradingManagerBet
        from utils.trading_manager_game import TradingManagerGame
        
        self.helpers = TradingManagerHelpers(self)
        self.bet_helper = TradingManagerBet(self)
        self.game_helper = TradingManagerGame(self)
        self._should_move_to_next_room = False
        
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
            self.logger.error(f"서비스 초기화 오류: {e}", exc_info=True)

    def start_trading(self):
        """웹소켓 인터셉터 기반 자동 매매 시작"""
        try:
            self.logger.info("🚀 웹소켓 인터셉터 기반 자동 매매 시작")
            
            # 기본 검증
            if not self.helpers.validate_trading_prerequisites():
                return

            # 설정 초기화
            self.refresh_settings()
            
            # 목표 금액 도달 플래그 초기화
            if hasattr(self.balance_service, '_target_amount_reached'):
                del self.balance_service._target_amount_reached

            self.stop_all_processes = False

            # 에볼루션 로비 준비
            if not self._ensure_evolution_lobby_ready():
                return

            # 웹소켓 인터셉터 시작
            if not self._start_websocket_interceptor():
                QMessageBox.warning(
                    self.main_window,
                    "웹소켓 인터셉터 실패",
                    "웹소켓 메시지 인터셉터를 시작할 수 없습니다."
                )
                return

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info("🎯 웹소켓 인터셉터 기반 자동 매매 시작 완료")
            
            # UI 업데이트
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(True)
            self.main_window.update_button_styles()
            
            # 방 입장 시작
            self._start_room_monitoring()

        except Exception as e:
            self.logger.error(f"자동 매매 시작 오류: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window, 
                "자동 매매 오류", 
                f"자동 매매 시작 중 오류가 발생했습니다.\n{str(e)}"
            )

    def _start_websocket_interceptor(self) -> bool:
        """웹소켓 인터셉터 시작"""
        try:
            self.logger.info("🎯 웹소켓 인터셉터 초기화")
            
            # 웹소켓 인터셉터 생성
            self.websocket_interceptor = WebSocketInterceptor(
                devtools=self.devtools,
                logger=self.logger
            )
            
            # 시그널 연결
            self._connect_interceptor_signals()
            
            # 인터셉터 시작
            if self.websocket_interceptor.start_intercepting():
                self.websocket_intercepting = True
                self.logger.info("✅ 웹소켓 인터셉터 시작 성공")
                return True
            else:
                self.logger.error("❌ 웹소켓 인터셉터 시작 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"웹소켓 인터셉터 시작 오류: {e}")
            return False

    def _connect_interceptor_signals(self):
        """웹소켓 인터셉터 시그널 연결"""
        try:
            if not self.websocket_interceptor:
                return
                
            # 웹소켓 메시지 수신 시그널
            self.websocket_interceptor.websocket_message_received.connect(
                self._on_websocket_message_received
            )
            
            # 게임 데이터 추출 시그널
            self.websocket_interceptor.game_data_extracted.connect(
                self._on_game_data_extracted
            )
            
            # 웹소켓 연결 감지 시그널
            self.websocket_interceptor.connection_detected.connect(
                self._on_websocket_connection_detected
            )
            
            # 오류 발생 시그널
            self.websocket_interceptor.error_occurred.connect(
                self._on_interceptor_error
            )
            
            self.logger.info("웹소켓 인터셉터 시그널 연결 완료")
            
        except Exception as e:
            self.logger.error(f"인터셉터 시그널 연결 오류: {e}")

    def _on_websocket_message_received(self, ws_message: dict):
        """웹소켓 메시지 수신 시 처리"""
        try:
            self.message_count += 1
            
            if self.message_count % 100 == 0:
                self.logger.info(f"📊 웹소켓 메시지 수신: {self.message_count}개")
            
            # 디버그용 로그 (첫 10개 메시지만)
            if self.message_count <= 10:
                direction = ws_message.get('direction', 'unknown')
                payload_preview = ws_message.get('payload', '')[:100]
                self.logger.info(f"📨 웹소켓 메시지 [{direction}]: {payload_preview}...")
                
        except Exception as e:
            self.logger.error(f"웹소켓 메시지 수신 처리 오류: {e}")

    def _on_game_data_extracted(self, game_data: dict):
        """게임 데이터 추출 시 처리"""
        try:
            self.last_game_data = game_data
            
            # 게임 데이터 로깅
            room_name = game_data.get('room_name', '')
            round_number = game_data.get('round_number', 0)
            latest_result = game_data.get('latest_result', '')
            
            if room_name or latest_result:
                self.logger.info(f"🎮 게임 데이터 추출: 방={room_name}, 라운드={round_number}, 결과={latest_result}")
            
            # 자동 매매가 활성화된 경우 게임 데이터 처리
            if self.is_trading_active:
                self._process_intercepted_game_data(game_data)
                
        except Exception as e:
            self.logger.error(f"게임 데이터 추출 처리 오류: {e}")

    def _on_websocket_connection_detected(self, websocket_url: str):
        """웹소켓 연결 감지 시 처리"""
        try:
            self.logger.info(f"🔌 Evolution 웹소켓 연결 감지: {websocket_url[:100]}...")
            
        except Exception as e:
            self.logger.error(f"웹소켓 연결 감지 처리 오류: {e}")

    def _on_interceptor_error(self, error_message: str):
        """인터셉터 오류 발생 시 처리"""
        try:
            self.logger.error(f"🚨 웹소켓 인터셉터 오류: {error_message}")
            
            # 심각한 오류인 경우 자동 매매 중지
            if "connection" in error_message.lower() or "timeout" in error_message.lower():
                self.logger.warning("심각한 인터셉터 오류로 인한 자동 매매 중지")
                self.stop_trading()
                
        except Exception as e:
            self.logger.error(f"인터셉터 오류 처리 중 오류: {e}")

    def _process_intercepted_game_data(self, game_data: dict):
        """인터셉터에서 수집한 게임 데이터 처리"""
        try:
            # 현재 방과 일치하는 데이터인지 확인
            room_name = game_data.get('room_name', '')
            if self.current_room_name and room_name:
                if self.current_room_name not in room_name:
                    return  # 다른 방의 데이터는 무시
            
            # 게임 카운트 업데이트
            round_number = game_data.get('round_number', 0)
            if round_number > self.game_count:
                self.game_count = round_number
            
            # 새로운 결과가 있는 경우 처리
            latest_result = game_data.get('latest_result', '')
            if latest_result and latest_result in ['P', 'B', 'T']:
                self._handle_intercepted_game_result(game_data)
            
            # 베팅 타이밍 확인
            self._check_intercepted_betting_opportunity(game_data)
            
        except Exception as e:
            self.logger.error(f"인터셉터 게임 데이터 처리 오류: {e}")

    def _handle_intercepted_game_result(self, game_data: dict):
        """인터셉터 게임 결과 처리"""
        try:
            latest_result = game_data.get('latest_result', '')
            round_number = game_data.get('round_number', 0)
            
            # 중복 결과 방지
            result_id = f"{round_number}_{latest_result}"
            if result_id in self.processed_rounds:
                return
            
            self.processed_rounds.add(result_id)
            self.result_count += 1
            
            self.logger.info(f"🎯 새로운 게임 결과: 라운드 {round_number}, 결과 {latest_result}")
            
            # 베팅 결과 확인
            if hasattr(self.betting_service, 'has_bet_current_round') and self.betting_service.has_bet_current_round:
                last_bet = self.betting_service.get_last_bet()
                
                if last_bet and last_bet['type'] in ['P', 'B']:
                    # 베팅 결과 처리
                    result_status = self.bet_helper.process_bet_result(
                        last_bet['type'], 
                        latest_result, 
                        round_number
                    )
                    
                    self.logger.info(f"베팅 결과 처리: {result_status}")
                    
                    # 결과에 따른 후속 처리
                    if result_status == 'win':
                        self.just_won = True
                        self._handle_win_result()
                    elif result_status == 'lose':
                        self._handle_lose_result()
                    elif result_status == 'tie':
                        self._handle_tie_result()
            
            # ExcelTradingService에 결과 추가
            if hasattr(self.excel_trading_service, 'choice_pick_system'):
                if latest_result in ['P', 'B']:
                    self.excel_trading_service.choice_pick_system.add_result(latest_result)
                    
        except Exception as e:
            self.logger.error(f"인터셉터 게임 결과 처리 오류: {e}")

    def _check_intercepted_betting_opportunity(self, game_data: dict):
        """인터셉터 데이터 기반 베팅 기회 확인"""
        try:
            # 이미 베팅했으면 스킵
            if hasattr(self.betting_service, 'has_bet_current_round') and self.betting_service.has_bet_current_round:
                return
            
            # 첫 결과 대기 중이면 스킵
            if self.wait_first_result:
                if game_data.get('latest_result'):
                    self.wait_first_result = False
                    self.logger.info("첫 결과 수신 - 대기 모드 해제")
                return
            
            # 베팅 가능 상태 확인 (게임 상태가 betting인지 등)
            game_status = game_data.get('game_status', '')
            if game_status and 'betting' not in game_status.lower():
                return
            
            # 픽 생성
            next_pick = self._generate_pick_from_intercepted_data(game_data)
            
            if next_pick in ['P', 'B']:
                # 베팅 실행
                round_number = game_data.get('round_number', self.game_count + 1)
                self._execute_intercepted_betting(next_pick, round_number)
                
        except Exception as e:
            self.logger.error(f"인터셉터 베팅 기회 확인 오류: {e}")

    def _generate_pick_from_intercepted_data(self, game_data: dict) -> str:
        """인터셉터 데이터 기반 픽 생성"""
        try:
            # ExcelTradingService의 ChoicePickSystem 사용
            if hasattr(self.excel_trading_service, 'choice_pick_system'):
                pick = self.excel_trading_service.choice_pick_system.generate_choice_pick()
                if pick in ['P', 'B']:
                    return pick
            
            # 폴백: 간단한 패턴
            latest_result = game_data.get('latest_result', '')
            if latest_result in ['P', 'B']:
                return 'B' if latest_result == 'P' else 'P'  # 반대 패턴
            
            return 'P'  # 기본값
            
        except Exception as e:
            self.logger.error(f"픽 생성 오류: {e}")
            return 'P'

    def _execute_intercepted_betting(self, pick: str, round_number: int):
        """인터셉터 기반 베팅 실행"""
        try:
            self.logger.info(f"🎯 인터셉터 베팅 실행: {pick} (라운드 {round_number})")
            
            # 베팅 금액 계산
            widget_pos = get_widget_position(self.main_window)
            bet_amount = self.excel_trading_service.get_current_bet_amount(widget_position=widget_pos)
            
            # 베팅 실행
            bet_success = self.betting_service.place_bet(
                pick,
                self.current_room_name,
                round_number,
                self.is_trading_active,
                bet_amount
            )
            
            if bet_success:
                self.logger.info(f"✅ 베팅 성공: {pick}, 금액: {bet_amount:,}원")
                self.main_window.update_betting_status(pick=pick, bet_amount=bet_amount)
            else:
                self.logger.warning(f"❌ 베팅 실패: {pick}")
                
        except Exception as e:
            self.logger.error(f"인터셉터 베팅 실행 오류: {e}")

    def _handle_win_result(self):
        """승리 결과 처리"""
        try:
            self.logger.info("🎉 승리 처리")
            
            # 위젯 초기화
            if hasattr(self.main_window, 'betting_widget'):
                self.main_window.betting_widget.room_position_counter = 0
                self.main_window.betting_widget.reset_step_markers()
            
            # 마틴 서비스 초기화
            if hasattr(self, 'martin_service'):
                self.martin_service.reset()
            
            # 새로운 방 검색
            self._start_room_monitoring()
            
        except Exception as e:
            self.logger.error(f"승리 처리 오류: {e}")

    def _handle_lose_result(self):
        """패배 결과 처리"""
        try:
            self.logger.info("❌ 패배 처리")
            
            # 위젯 카운터 증가
            if hasattr(self.main_window, 'betting_widget'):
                current_pos = getattr(self.main_window.betting_widget, 'room_position_counter', 0)
                self.main_window.betting_widget.room_position_counter = current_pos + 1
                self.main_window.betting_widget.set_step_marker(current_pos, "X")
            
            # 연패 확인
            if self._check_consecutive_losses():
                self.logger.info("연패 조건 달성 - 방 이동")
                self._start_room_monitoring()
                
        except Exception as e:
            self.logger.error(f"패배 처리 오류: {e}")

    def _handle_tie_result(self):
        """무승부 결과 처리"""
        try:
            self.logger.info("🤝 무승부 처리")
            
            # 베팅 상태 초기화
            self.betting_service.has_bet_current_round = False
            self.had_tie_last_round = True
            
        except Exception as e:
            self.logger.error(f"무승부 처리 오류: {e}")

    def _check_consecutive_losses(self) -> bool:
        """연패 확인"""
        try:
            # ExcelTradingService를 통한 방 이동 조건 확인
            if hasattr(self, 'excel_trading_service'):
                return self.excel_trading_service.should_change_room()
            
            return False
            
        except Exception as e:
            self.logger.error(f"연패 확인 오류: {e}")
            return False

    def _start_room_monitoring(self):
        """방 모니터링 시작 (인터셉터 기반)"""
        try:
            self.logger.info("🏠 인터셉터 기반 방 모니터링 시작")
            
            # 방 입장 시도
            room_name = self.room_entry_service.enter_room()
            
            if room_name:
                self.current_room_name = room_name
                self.game_count = 0
                self.wait_first_result = True
                
                # UI 업데이트
                self.main_window.update_betting_status(room_name=room_name)
                
                self.logger.info(f"✅ 방 입장 성공: {room_name}")
                
                # 게임 상태 확인
                self._verify_room_game_state()
                
            else:
                self.logger.warning("❌ 방 입장 실패 - 재시도")
                # 5초 후 재시도
                self.main_window.set_remaining_time(0, 0, 5)
                
        except Exception as e:
            self.logger.error(f"방 모니터링 시작 오류: {e}")

    def _verify_room_game_state(self):
        """방 입장 후 게임 상태 검증"""
        try:
            # 기존 게임 모니터링 서비스로 현재 상태 확인
            game_state = self.game_monitoring_service.get_current_game_state()
            
            if game_state:
                current_round = game_state.get('round', 0)
                self.game_count = current_round
                
                # ChoicePickSystem에 라운드 정보 설정
                if hasattr(self.excel_trading_service, 'choice_pick_system'):
                    cps = self.excel_trading_service.choice_pick_system
                    cps._entered_round = current_round
                    cps._current_game_round = current_round
                    cps.wait_first_result = True
                
                self.logger.info(f"🎮 현재 게임 라운드: {current_round}")
            else:
                self.logger.warning("게임 상태 확인 실패")
                
        except Exception as e:
            self.logger.error(f"게임 상태 검증 오류: {e}")

    def stop_trading(self):
        """웹소켓 인터셉터 기반 자동 매매 중지"""
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 이미 중지된 상태입니다.")
                return
                
            self.logger.info("🛑 웹소켓 인터셉터 자동 매매 중지 중...")
            
            # 웹소켓 인터셉터 중지
            if self.websocket_interceptor:
                self.websocket_interceptor.stop_intercepting()
                self.websocket_interceptor = None
            
            # 중지 플래그 설정
            self.stop_all_processes = True
            self.is_trading_active = False
            self.websocket_intercepting = False
            
            # 타이머 중지
            if hasattr(self.main_window, 'timer') and self.main_window.timer.isActive():
                self.main_window.timer.stop()
                QApplication.processEvents()
            
            # 상태 초기화
            self.game_count = 0
            self.result_count = 0
            self.current_pick = None
            self.processed_rounds = set()
            
            # 서비스 초기화
            if hasattr(self, 'betting_service'):
                self.betting_service.reset_betting_state()
            
            if hasattr(self, 'martin_service'):
                self.martin_service.reset()
            
            # UI 상태 복원
            self.main_window.start_button.setEnabled(True)
            self.main_window.stop_button.setEnabled(False)
            self.main_window.update_button_styles()
            
            # 현재 방에서 나가기
            if self.current_room_name:
                try:
                    if hasattr(self, 'game_monitoring_service'):
                        self.game_monitoring_service.close_current_room()
                except:
                    pass
            
            self.logger.info("✅ 웹소켓 인터셉터 자동 매매 중지 완료")
            
            # 목표 금액 도달이 아닌 경우에만 메시지 표시
            target_reached = (hasattr(self.balance_service, '_target_amount_reached') and 
                            self.balance_service._target_amount_reached)
            
            if not target_reached:
                QMessageBox.information(self.main_window, "알림", "자동 매매가 중지되었습니다.")

        except Exception as e:
            self.logger.error(f"자동 매매 중지 중 오류: {e}")
            # 강제 중지
            self.is_trading_active = False
            self.websocket_intercepting = False

    def get_interceptor_status(self) -> dict:
        """인터셉터 상태 정보 반환"""
        try:
            if self.websocket_interceptor:
                return self.websocket_interceptor.get_interceptor_stats()
            else:
                return {
                    'is_intercepting': False,
                    'performance_logs_enabled': False,
                    'cdp_session_active': False,
                    'websocket_connections': 0,
                    'active_connections': 0,
                    'message_buffer_size': 0,
                    'processed_messages': 0
                }
        except Exception as e:
            self.logger.error(f"인터셉터 상태 확인 오류: {e}")
            return {'error': str(e)}

    def get_recent_websocket_messages(self, count=10):
        """최근 웹소켓 메시지 반환"""
        try:
            if self.websocket_interceptor:
                return self.websocket_interceptor.get_recent_messages(count)
            return []
        except Exception as e:
            self.logger.error(f"최근 메시지 가져오기 오류: {e}")
            return []

    # 기존 메서드들 유지
    def refresh_settings(self):
        """설정 새로고침"""
        try:
            self.settings_manager = SettingsManager()
            
            # 서비스들의 설정 매니저 갱신
            services = ['balance_service', 'martin_service', 'room_entry_service', 'excel_trading_service']
            for service_name in services:
                if hasattr(self, service_name):
                    service = getattr(self, service_name)
                    if hasattr(service, 'settings_manager'):
                        service.settings_manager = self.settings_manager
            
            # 마틴 설정 적용
            martin_count, martin_amounts = self.settings_manager.get_martin_settings()
            if hasattr(self, 'excel_trading_service'):
                self.excel_trading_service.set_martin_amounts(martin_amounts)
                    
            self.logger.info(f"설정 새로고침 완료 - 마틴: {martin_count}단계, {martin_amounts}")
            return True
            
        except Exception as e:
            self.logger.error(f"설정 새로고침 오류: {e}")
            return False

    def _ensure_evolution_lobby_ready(self):
        """에볼루션 로비 준비 상태 확인"""
        try:
            window_handles = self.devtools.driver.window_handles
            
            if len(window_handles) < 2:
                QMessageBox.information(
                    self.main_window, 
                    "에볼루션 접속 필요", 
                    "에볼루션 카지노에 먼저 접속해주세요."
                )
                return False
            
            # 에볼루션 로비 창으로 전환
            self.devtools.driver.switch_to.window(window_handles[1])
            self.logger.info("에볼루션 로비 창으로 전환 완료")
            
            # 잔액 확인
            if not self.helpers.setup_browser_and_check_balance():
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"에볼루션 로비 준비 오류: {e}")
            return False

    def get_current_status(self):
        """현재 상태 반환"""
        interceptor_status = self.get_interceptor_status()
        
        return {
            'is_active': self.is_trading_active,
            'websocket_intercepting': self.websocket_intercepting,
            'current_room': self.current_room_name,
            'game_count': self.game_count,
            'result_count': self.result_count,
            'has_bet': getattr(self.betting_service, 'has_bet_current_round', False) if hasattr(self, 'betting_service') else False,
            'wait_first_result': self.wait_first_result,
            'stop_flag': self.stop_all_processes,
            'interceptor_status': interceptor_status,
            'message_count': self.message_count,
            'last_game_data': self.last_game_data
        }

    def emergency_stop(self):
        """비상 정지"""
        try:
            self.logger.warning("🚨 비상 정지 실행")
            
            # 모든 플래그 즉시 설정
            self.stop_all_processes = True
            self.is_trading_active = False
            self.websocket_intercepting = False
            
            # 웹소켓 인터셉터 강제 종료
            if self.websocket_interceptor:
                self.websocket_interceptor.stop_intercepting()
                self.websocket_interceptor = None
            
            # 타이머 강제 중지
            if hasattr(self.main_window, 'timer'):
                self.main_window.timer.stop()
                QApplication.processEvents()
            
            # UI 상태 강제 복원
            self.main_window.start_button.setEnabled(True)
            self.main_window.stop_button.setEnabled(False)
            self.main_window.update_button_styles()
            
            self.logger.info("비상 정지 완료")
            
        except Exception as e:
            self.logger.error(f"비상 정지 중 오류: {e}")

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            if hasattr(self, 'websocket_interceptor') and self.websocket_interceptor:
                self.websocket_interceptor.stop_intercepting()
                
        except:
            pass