# utils/trading_manager.py (웹소켓 직접 통신 버전)

import time
import logging
import asyncio
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
from services.websocket_parser import WebSocketParser
from utils.devtools import DevToolsController

# 새로운 웹소켓 직접 통신 클라이언트
from services.websocket_direct_client import WebSocketDirectClient, WebSocketThread, GameData

class TradingManager:
    """웹소켓 직접 통신 기반 TradingManager"""

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

        # 웹소켓 직접 통신 클라이언트
        self.websocket_client = None
        self.websocket_thread = None
        self.websocket_url = None
        
        # 상태 관리 속성
        self.is_trading_active = False
        self.current_room_name = ""
        self.game_count = 0
        self.result_count = 0
        self.current_pick = None
        self.processed_rounds = set()
        
        # 웹소켓 데이터 상태
        self.websocket_connected = False
        self.last_game_data = None
        self.message_count = 0
        
        # 기타 상태 변수
        self.wait_first_result = False
        self.stop_all_processes = False
        self.had_tie_last_round = False
        self.just_won = False

        # 웹소켓 파서
        self.ws_parser = None

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
        """웹소켓 직접 통신 기반 자동 매매 시작"""
        try:
            self.logger.info("🚀 웹소켓 직접 통신 기반 자동 매매 시작")
            
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

            # 웹소켓 URL 추출
            websocket_url = self._extract_websocket_async()
            
            if not websocket_url:
                QMessageBox.critical(
                    self.main_window,
                    "웹소켓 추출 실패",
                    "웹소켓 URL을 추출할 수 없습니다.\n에볼루션 게임을 시작해주세요."
                )
                return

            # 웹소켓 직접 연결 시작
            if not self._start_websocket_connection(websocket_url):
                QMessageBox.warning(
                    self.main_window,
                    "웹소켓 연결 실패",
                    "웹소켓 연결에 실패했습니다."
                )
                return

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info("🎯 웹소켓 직접 통신 기반 자동 매매 시작 완료")
            
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

    def _extract_websocket_async(self) -> str:
        """웹소켓 URL 추출 (기존 로직 유지)"""
        try:
            self.logger.info("⚡ 웹소켓 URL 추출 시작")

            self.ws_parser = WebSocketParser(self.devtools, self.logger)

            websocket_result = {"url": None, "completed": False}

            def on_websocket_result(result):
                websocket_result["completed"] = True
                if result.success and result.urls:
                    websocket_result["url"] = result.urls[0]
                    self.logger.info(f"✅ 웹소켓 URL 추출 성공: {result.urls[0]}")
                else:
                    self.logger.error(f"❌ 웹소켓 URL 추출 실패: {result.error}")

            future = self.ws_parser.auto_detect_websocket_urls_async(callback=on_websocket_result)
            
            # 완료 대기
            max_wait = 30
            start_time = time.time()
            
            while not websocket_result["completed"] and (time.time() - start_time) < max_wait:
                QApplication.processEvents()
                time.sleep(0.1)
            
            if not websocket_result["completed"]:
                self.logger.warning("웹소켓 추출 타임아웃")
                if self.ws_parser:
                    self.ws_parser.cancel_current_operation()
                return None
            
            return websocket_result["url"]

        except Exception as e:
            self.logger.error(f"웹소켓 URL 추출 오류: {e}")
            return None

    def _start_websocket_connection(self, websocket_url: str) -> bool:
        """웹소켓 직접 연결 시작"""
        try:
            self.websocket_url = websocket_url
            self.logger.info(f"🔌 웹소켓 직접 연결 시작: {websocket_url[:50]}...")
            
            # 웹소켓 클라이언트 생성
            self.websocket_client = WebSocketDirectClient(logger=self.logger)
            
            # 시그널 연결
            self._connect_websocket_signals()
            
            # 별도 스레드에서 웹소켓 연결
            self.websocket_thread = WebSocketThread(self.websocket_client, websocket_url)
            self.websocket_thread.start()
            
            # 연결 확인 대기 (최대 10초)
            connection_timeout = 10
            start_time = time.time()
            
            while (time.time() - start_time) < connection_timeout:
                if self.websocket_connected:
                    self.logger.info("✅ 웹소켓 연결 성공 확인")
                    return True
                
                QApplication.processEvents()
                time.sleep(0.5)
            
            self.logger.warning("웹소켓 연결 타임아웃")
            return False
            
        except Exception as e:
            self.logger.error(f"웹소켓 연결 시작 오류: {e}")
            return False

    def _connect_websocket_signals(self):
        """웹소켓 시그널 연결"""
        try:
            if not self.websocket_client:
                return
                
            # 게임 데이터 수신 시그널
            self.websocket_client.game_data_received.connect(self._on_game_data_received)
            
            # 연결 상태 변경 시그널
            self.websocket_client.connection_status_changed.connect(self._on_websocket_status_changed)
            
            # 오류 발생 시그널
            self.websocket_client.error_occurred.connect(self._on_websocket_error)
            
            # 방 데이터 업데이트 시그널
            self.websocket_client.room_data_updated.connect(self._on_room_data_updated)
            
            self.logger.info("웹소켓 시그널 연결 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 시그널 연결 오류: {e}")

    def _on_game_data_received(self, game_data: GameData):
        """웹소켓에서 게임 데이터 수신 시 처리"""
        try:
            self.message_count += 1
            self.last_game_data = game_data
            
            if self.message_count % 50 == 0:
                self.logger.info(f"📊 웹소켓 메시지 수신: {self.message_count}개")
            
            # 게임 데이터 분석 및 베팅 처리
            if self.is_trading_active:
                self._process_websocket_game_data(game_data)
                
        except Exception as e:
            self.logger.error(f"웹소켓 게임 데이터 처리 오류: {e}")

    def _on_websocket_status_changed(self, connected: bool):
        """웹소켓 연결 상태 변경 시 처리"""
        try:
            self.websocket_connected = connected
            status_text = "연결됨" if connected else "연결 끊김"
            self.logger.info(f"🔌 웹소켓 상태 변경: {status_text}")
            
            if not connected and self.is_trading_active:
                self.logger.warning("웹소켓 연결이 끊어졌습니다. 재연결 시도...")
                # 재연결 로직 추가 가능
                
        except Exception as e:
            self.logger.error(f"웹소켓 상태 변경 처리 오류: {e}")

    def _on_websocket_error(self, error_message: str):
        """웹소켓 오류 발생 시 처리"""
        try:
            self.logger.error(f"🚨 웹소켓 오류: {error_message}")
            
            # 심각한 오류인 경우 자동 매매 중지
            if "connection" in error_message.lower() or "timeout" in error_message.lower():
                self.logger.warning("심각한 웹소켓 오류로 인한 자동 매매 중지")
                self.stop_trading()
                
        except Exception as e:
            self.logger.error(f"웹소켓 오류 처리 중 오류: {e}")

    def _on_room_data_updated(self, room_data: dict):
        """방 데이터 업데이트 시 처리"""
        try:
            room_name = room_data.get('room_name', '')
            round_number = room_data.get('round', 0)
            latest_result = room_data.get('latest_result', '')
            
            if room_name and room_name != self.current_room_name:
                self.logger.info(f"🏠 새로운 방 감지: {room_name}")
                
            if latest_result and round_number > self.game_count:
                self.logger.info(f"🎯 새로운 게임 결과: 라운드 {round_number}, 결과 {latest_result}")
                
        except Exception as e:
            self.logger.error(f"방 데이터 업데이트 처리 오류: {e}")

    def _process_websocket_game_data(self, game_data: GameData):
        """웹소켓 게임 데이터 분석 및 베팅 처리"""
        try:
            # 현재 방과 일치하는 데이터인지 확인
            if self.current_room_name and game_data.room_name:
                if self.current_room_name not in game_data.room_name:
                    return  # 다른 방의 데이터는 무시
            
            # 게임 카운트 업데이트
            if game_data.round_number > self.game_count:
                self.game_count = game_data.round_number
            
            # 새로운 결과가 있는 경우 처리
            if game_data.latest_result and game_data.latest_result in ['P', 'B', 'T']:
                self._handle_websocket_game_result(game_data)
            
            # 베팅 타이밍 확인
            self._check_websocket_betting_opportunity(game_data)
            
        except Exception as e:
            self.logger.error(f"웹소켓 게임 데이터 처리 오류: {e}")

    def _handle_websocket_game_result(self, game_data: GameData):
        """웹소켓 게임 결과 처리"""
        try:
            latest_result = game_data.latest_result
            round_number = game_data.round_number
            
            # 중복 결과 방지
            result_id = f"{round_number}_{latest_result}"
            if result_id in self.processed_rounds:
                return
            
            self.processed_rounds.add(result_id)
            
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
            self.logger.error(f"웹소켓 게임 결과 처리 오류: {e}")

    def _check_websocket_betting_opportunity(self, game_data: GameData):
        """웹소켓 데이터 기반 베팅 기회 확인"""
        try:
            # 이미 베팅했으면 스킵
            if hasattr(self.betting_service, 'has_bet_current_round') and self.betting_service.has_bet_current_round:
                return
            
            # 첫 결과 대기 중이면 스킵
            if self.wait_first_result:
                if game_data.latest_result:
                    self.wait_first_result = False
                    self.logger.info("첫 결과 수신 - 대기 모드 해제")
                return
            
            # 베팅 가능 상태 확인 (게임 상태가 betting인지 등)
            if game_data.game_status and 'betting' not in game_data.game_status.lower():
                return
            
            # 픽 생성
            next_pick = self._generate_pick_from_websocket_data(game_data)
            
            if next_pick in ['P', 'B']:
                # 베팅 실행
                self._execute_websocket_betting(next_pick, game_data.round_number)
                
        except Exception as e:
            self.logger.error(f"웹소켓 베팅 기회 확인 오류: {e}")

    def _generate_pick_from_websocket_data(self, game_data: GameData) -> str:
        """웹소켓 데이터 기반 픽 생성"""
        try:
            # ExcelTradingService의 ChoicePickSystem 사용
            if hasattr(self.excel_trading_service, 'choice_pick_system'):
                pick = self.excel_trading_service.choice_pick_system.generate_choice_pick()
                if pick in ['P', 'B']:
                    return pick
            
            # 폴백: 최근 결과 기반 간단한 패턴
            if game_data.recent_results and len(game_data.recent_results) > 0:
                last_result = game_data.recent_results[-1]
                return 'B' if last_result == 'P' else 'P'  # 반대 패턴
            
            return 'P'  # 기본값
            
        except Exception as e:
            self.logger.error(f"픽 생성 오류: {e}")
            return 'P'

    def _execute_websocket_betting(self, pick: str, round_number: int):
        """웹소켓 기반 베팅 실행"""
        try:
            self.logger.info(f"🎯 웹소켓 베팅 실행: {pick} (라운드 {round_number})")
            
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
            self.logger.error(f"웹소켓 베팅 실행 오류: {e}")

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
        """방 모니터링 시작 (웹소켓 기반)"""
        try:
            self.logger.info("🏠 웹소켓 기반 방 모니터링 시작")
            
            # 방 입장 시도
            room_name = self.room_entry_service.enter_room()
            
            if room_name:
                self.current_room_name = room_name
                self.game_count = 0
                self.wait_first_result = True
                
                # 웹소켓 클라이언트에 현재 방 설정
                if self.websocket_client:
                    self.websocket_client.set_current_room(room_name)
                
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
        """웹소켓 직접 통신 기반 자동 매매 중지"""
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 이미 중지된 상태입니다.")
                return
                
            self.logger.info("🛑 웹소켓 직접 통신 자동 매매 중지 중...")
            
            # 웹소켓 연결 중지
            if self.websocket_client:
                self.websocket_client.stop_connection()
            
            if self.websocket_thread and self.websocket_thread.isRunning():
                self.websocket_thread.quit()
                self.websocket_thread.wait(3000)  # 3초 대기
            
            # WebSocket Parser 정리
            if self.ws_parser:
                self.ws_parser.cancel_current_operation()
                self.ws_parser.shutdown()
                self.ws_parser = None
            
            # 중지 플래그 설정
            self.stop_all_processes = True
            self.is_trading_active = False
            
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
            
            self.logger.info("✅ 웹소켓 직접 통신 자동 매매 중지 완료")
            
            # 목표 금액 도달이 아닌 경우에만 메시지 표시
            target_reached = (hasattr(self.balance_service, '_target_amount_reached') and 
                            self.balance_service._target_amount_reached)
            
            if not target_reached:
                QMessageBox.information(self.main_window, "알림", "자동 매매가 중지되었습니다.")

        except Exception as e:
            self.logger.error(f"자동 매매 중지 중 오류: {e}")
            # 강제 중지
            self.is_trading_active = False
            self.websocket_connected = False

    def get_websocket_status(self) -> dict:
        """웹소켓 상태 정보 반환"""
        try:
            if self.websocket_client:
                return self.websocket_client.get_connection_status()
            else:
                return {
                    'connected': False,
                    'running': False,
                    'url': None,
                    'message_count': 0,
                    'last_data_time': None,
                    'current_room': self.current_room_name
                }
        except Exception as e:
            self.logger.error(f"웹소켓 상태 확인 오류: {e}")
            return {'error': str(e)}

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
        websocket_status = self.get_websocket_status()
        
        return {
            'is_active': self.is_trading_active,
            'websocket_connected': self.websocket_connected,
            'current_room': self.current_room_name,
            'game_count': self.game_count,
            'result_count': self.result_count,
            'has_bet': getattr(self.betting_service, 'has_bet_current_round', False) if hasattr(self, 'betting_service') else False,
            'wait_first_result': self.wait_first_result,
            'stop_flag': self.stop_all_processes,
            'websocket_status': websocket_status,
            'message_count': self.message_count,
            'last_game_data': {
                'room_name': self.last_game_data.room_name if self.last_game_data else '',
                'round': self.last_game_data.round_number if self.last_game_data else 0,
                'result': self.last_game_data.latest_result if self.last_game_data else '',
                'timestamp': self.last_game_data.timestamp if self.last_game_data else 0
            } if self.last_game_data else None
        }

    def emergency_stop(self):
        """비상 정지"""
        try:
            self.logger.warning("🚨 비상 정지 실행")
            
            # 모든 플래그 즉시 설정
            self.stop_all_processes = True
            self.is_trading_active = False
            
            # 웹소켓 강제 종료
            if self.websocket_client:
                self.websocket_client.stop_connection()
            
            if self.websocket_thread:
                self.websocket_thread.terminate()
            
            # WebSocket Parser 정리
            if self.ws_parser:
                self.ws_parser.shutdown()
                self.ws_parser = None
            
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
            if hasattr(self, 'websocket_client') and self.websocket_client:
                self.websocket_client.stop_connection()
            
            if hasattr(self, 'websocket_thread') and self.websocket_thread:
                self.websocket_thread.quit()
                
            if hasattr(self, 'ws_parser') and self.ws_parser:
                self.ws_parser.shutdown()
                
        except:
            pass