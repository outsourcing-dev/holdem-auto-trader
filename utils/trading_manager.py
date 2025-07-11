"""
JavaScript 하이브리드 웹소켓 기반 TradingManager
- 기존 DevTools 구조 유지
- JavaScript로 웹소켓 직접 연결
- 실시간 데이터를 Python으로 전달
"""

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

class TradingManager:
    """JavaScript 하이브리드 웹소켓 기반 자동매매 매니저"""

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

        # JavaScript 하이브리드 웹소켓 서비스
        self.websocket_service = None
        self.websocket_interceptor = None  # 호환성 유지
        
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
        """JavaScript 하이브리드 웹소켓 기반 자동 매매 시작"""
        try:
            self.logger.info("🚀 JavaScript 하이브리드 웹소켓 기반 자동 매매 시작")
            
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

            # JavaScript 하이브리드 웹소켓 서비스 시작
            if not self._start_websocket_service():
                QMessageBox.warning(
                    self.main_window,
                    "웹소켓 서비스 실패",
                    "JavaScript 웹소켓 서비스를 시작할 수 없습니다."
                )
                return

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info("🎯 JavaScript 하이브리드 웹소켓 기반 자동 매매 시작 완료")
            
            # UI 업데이트
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(True)
            self.main_window.update_button_styles()
            
            # 방 모니터링 시작
            self._start_room_monitoring()

        except Exception as e:
            self.logger.error(f"자동 매매 시작 오류: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window, 
                "자동 매매 오류", 
                f"자동 매매 시작 중 오류가 발생했습니다.\n{str(e)}"
            )

    def _start_websocket_service(self) -> bool:
        """JavaScript 하이브리드 웹소켓 서비스 시작 - 간단 버전"""
        try:
            self.logger.info("🎯 웹소켓 URL 추출 및 연결 시작")
            
            # 웹소켓 URL 추출
            websocket_urls = self._extract_websocket_urls_for_logging()
            
            if not websocket_urls:
                self.logger.error("❌ 웹소켓 URL을 찾을 수 없습니다")
                return False
            
            # 첫 번째 URL 사용
            websocket_url = websocket_urls[0]
            self.logger.info(f"📡 사용할 웹소켓 URL: {websocket_url[:100]}...")
            
            # JavaScript 하이브리드 서비스 생성
            from services.websocket_hybrid_service import WebSocketHybridService
            self.websocket_service = WebSocketHybridService(
                devtools=self.devtools,
                logger=self.logger
            )
            
            # 기존 호환성을 위한 변수 설정
            self.websocket_interceptor = self.websocket_service
            
            # 시그널 연결
            self._connect_hybrid_service_signals()
            
            # JavaScript 웹소켓 연결 시작 (새로고침 없이 바로 연결)
            if self.websocket_service.start_websocket_connection(websocket_url):
                self.websocket_intercepting = True
                self.logger.info("✅ JavaScript 하이브리드 웹소켓 서비스 시작 성공")
                return True
            else:
                self.logger.error("❌ JavaScript 웹소켓 연결 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"JavaScript 하이브리드 웹소켓 서비스 시작 오류: {e}")
            return False
        
    def _extract_websocket_urls_for_logging(self) -> list:
        """웹소켓 URL 추출 및 로깅"""
        try:
            self.logger.info("⚡ 웹소켓 URL 추출 시작")
            start_time = time.time()
            
            # WebSocketParser 사용
            from services.websocket_parser import WebSocketParser
            ws_parser = WebSocketParser(self.devtools, self.logger)
            
            # URL 추출 실행
            websocket_urls = []
            try:
                websocket_urls = ws_parser.auto_detect_websocket_urls()
            except Exception as e:
                self.logger.warning(f"웹소켓 URL 추출 중 오류: {e}")
                websocket_urls = []
            
            elapsed_time = time.time() - start_time
            
            # 로그 출력
            if websocket_urls:
                first_url = websocket_urls[0]
                self.logger.info(f"📡 WebSocket 연결 감지: {first_url}")
                self.logger.info(f"✅ 웹소켓 URL 추출 완료 ({elapsed_time:.1f}초, {len(websocket_urls)}개 발견)")
                self.logger.info(f"✅ 웹소켓 URL 추출 성공: {first_url[:100]}...")
            else:
                self.logger.warning(f"❌ 웹소켓 URL 추출 실패 ({elapsed_time:.1f}초)")
            
            # 정리
            if hasattr(ws_parser, 'shutdown'):
                ws_parser.shutdown()
            
            return websocket_urls
            
        except Exception as e:
            self.logger.error(f"웹소켓 URL 추출 오류: {e}")
            return []

    def _extract_websocket_urls_after_refresh(self) -> list:
        """새로고침 후 웹소켓 URL 재추출"""
        try:
            self.logger.info("🔄 새로고침 후 웹소켓 URL 재추출 시작")
            
            # 페이지가 완전히 로드될 때까지 대기
            max_wait_time = 10  # 최대 10초 대기
            wait_interval = 0.5  # 0.5초마다 체크
            
            for attempt in range(int(max_wait_time / wait_interval)):
                try:
                    # 페이지 로드 상태 확인
                    page_ready = self.devtools.driver.execute_script("return document.readyState === 'complete';")
                    
                    if page_ready:
                        self.logger.info(f"✅ 페이지 로드 완료 ({attempt * wait_interval:.1f}초 후)")
                        break
                        
                    time.sleep(wait_interval)
                    
                except Exception as e:
                    self.logger.debug(f"페이지 상태 확인 중 오류: {e}")
                    time.sleep(wait_interval)
            
            # 추가 대기 (웹소켓 연결이 생성될 시간)
            time.sleep(2)
            
            # 실시간 활성 웹소켓 URL 확인
            active_websocket_url = self._get_current_active_websocket_url()
            
            if active_websocket_url:
                self.logger.info(f"🎯 실시간 활성 웹소켓 발견: {active_websocket_url[:100]}...")
                return [active_websocket_url]
            
            # 폴백: 일반적인 웹소켓 파서 재실행
            self.logger.info("🔄 일반 웹소켓 파서로 재시도...")
            
            from services.websocket_parser import WebSocketParser
            ws_parser = WebSocketParser(self.devtools, self.logger)
            
            try:
                websocket_urls = ws_parser.auto_detect_websocket_urls()
                
                if websocket_urls:
                    new_url = websocket_urls[0]
                    self.logger.info(f"✅ 새로고침 후 웹소켓 URL 재추출 성공: {new_url[:100]}...")
                    return websocket_urls
                else:
                    self.logger.warning("❌ 새로고침 후 웹소켓 URL 재추출 실패")
                    return []
                    
            finally:
                if hasattr(ws_parser, 'shutdown'):
                    ws_parser.shutdown()
            
        except Exception as e:
            self.logger.error(f"새로고침 후 웹소켓 URL 재추출 오류: {e}")
            return []

    def _get_current_active_websocket_url(self) -> str:
        """현재 활성 웹소켓 URL 실시간 확인"""
        try:
            # JavaScript로 현재 활성 웹소켓 찾기
            script = """
            // 현재 활성 웹소켓 찾기
            const activeWebSockets = [];
            
            // 전역에서 웹소켓 연결 찾기 시도
            for (let prop in window) {
                try {
                    if (window[prop] && window[prop].constructor === WebSocket) {
                        if (window[prop].readyState === 1 && window[prop].url.includes('evo-games.com')) {
                            activeWebSockets.push(window[prop].url);
                        }
                    }
                } catch (e) {
                    // 무시
                }
            }
            
            // 활성 웹소켓이 없으면 인터셉터 설정하여 새 연결 감지
            if (activeWebSockets.length === 0) {
                if (!window.websocketInterceptorInstalled) {
                    const originalWebSocket = WebSocket;
                    window.detectedWebSockets = [];
                    
                    window.WebSocket = function(url, protocols) {
                        if (url.includes('evo-games.com')) {
                            window.detectedWebSockets.push(url);
                            console.log('🎯 Evolution 웹소켓 감지:', url);
                        }
                        return new originalWebSocket(url, protocols);
                    };
                    
                    window.websocketInterceptorInstalled = true;
                }
                
                // 이미 감지된 웹소켓이 있으면 반환
                if (window.detectedWebSockets && window.detectedWebSockets.length > 0) {
                    return window.detectedWebSockets[window.detectedWebSockets.length - 1];
                }
            }
            
            return activeWebSockets.length > 0 ? activeWebSockets[0] : null;
            """
            
            result = self.devtools.driver.execute_script(script)
            
            if result:
                self.logger.info(f"🎯 실시간 활성 웹소켓 발견: {result}")
                return result
            else:
                self.logger.debug("실시간 활성 웹소켓 없음")
                return None
                
        except Exception as e:
            self.logger.debug(f"실시간 웹소켓 확인 오류: {e}")
            return None
        """웹소켓 URL 추출 및 로깅"""
        try:
            self.logger.info("⚡ 웹소켓 URL 추출 시작")
            start_time = time.time()
            
            # WebSocketParser 사용
            from services.websocket_parser import WebSocketParser
            ws_parser = WebSocketParser(self.devtools, self.logger)
            
            # URL 추출 실행
            websocket_urls = []
            try:
                websocket_urls = ws_parser.auto_detect_websocket_urls()
            except Exception as e:
                self.logger.warning(f"웹소켓 URL 추출 중 오류: {e}")
                websocket_urls = []
            
            elapsed_time = time.time() - start_time
            
            # 로그 출력
            if websocket_urls:
                first_url = websocket_urls[0]
                self.logger.info(f"📡 WebSocket 연결 감지: {first_url}")
                self.logger.info(f"✅ 웹소켓 URL 추출 완료 ({elapsed_time:.1f}초, {len(websocket_urls)}개 발견)")
                self.logger.info(f"✅ 웹소켓 URL 추출 성공: {first_url[:100]}...")
            else:
                self.logger.warning(f"❌ 웹소켓 URL 추출 실패 ({elapsed_time:.1f}초)")
            
            # 정리
            if hasattr(ws_parser, 'shutdown'):
                ws_parser.shutdown()
            
            return websocket_urls
            
        except Exception as e:
            self.logger.error(f"웹소켓 URL 추출 오류: {e}")
            return []

    def _connect_hybrid_service_signals(self):
        """JavaScript 하이브리드 서비스 시그널 연결"""
        try:
            if not self.websocket_service:
                return
                
            # 게임 데이터 수신 시그널
            self.websocket_service.game_data_received.connect(
                self._on_game_data_extracted
            )
            
            # 연결 상태 변경 시그널
            self.websocket_service.connection_status_changed.connect(
                self._on_hybrid_connection_status_changed
            )
            
            # 오류 발생 시그널
            self.websocket_service.error_occurred.connect(
                self._on_websocket_error
            )
            
            self.logger.info("JavaScript 하이브리드 서비스 시그널 연결 완료")
            
        except Exception as e:
            self.logger.error(f"하이브리드 서비스 시그널 연결 오류: {e}")

    def _on_hybrid_connection_status_changed(self, connected: bool):
        """하이브리드 서비스 연결 상태 변경 처리"""
        try:
            status_text = "연결됨" if connected else "연결 끊김"
            self.logger.info(f"🔌 JavaScript 웹소켓 상태 변경: {status_text}")
            
            if connected:
                self.logger.info("✅ 실시간 게임 데이터 수신 시작")
            else:
                if self.is_trading_active:
                    self.logger.warning("⚠️ 자동 매매 중 연결 끊김")
                    
        except Exception as e:
            self.logger.error(f"연결 상태 변경 처리 오류: {e}")

    def _on_game_data_extracted(self, game_data: dict):
        """게임 데이터 추출 시 처리"""
        try:
            self.last_game_data = game_data
            self.message_count += 1
            
            # 게임 데이터 로깅
            room_name = game_data.get('room_name', '')
            round_number = game_data.get('round_number', 0)
            latest_result = game_data.get('latest_result', '')
            
            if room_name or latest_result:
                self.logger.info(f"🎮 JavaScript 게임 데이터: 방={room_name}, 라운드={round_number}, 결과={latest_result}")
            
            # 자동 매매가 활성화된 경우 게임 데이터 처리
            if self.is_trading_active:
                self._process_game_data(game_data)
                
        except Exception as e:
            self.logger.error(f"게임 데이터 추출 처리 오류: {e}")

    def _on_websocket_error(self, error_message: str):
        """웹소켓 오류 발생 시 처리"""
        try:
            self.logger.error(f"🚨 JavaScript 웹소켓 오류: {error_message}")
            
            # 심각한 오류인 경우 자동 매매 중지
            if "connection" in error_message.lower() or "timeout" in error_message.lower():
                self.logger.warning("심각한 웹소켓 오류로 인한 자동 매매 중지")
                self.stop_trading()
                
        except Exception as e:
            self.logger.error(f"웹소켓 오류 처리 중 오류: {e}")

    def _process_game_data(self, game_data: dict):
        """수집한 게임 데이터 처리"""
        try:
            # 현재 방과 일치하는 데이터인지 확인
            room_name = game_data.get('room_name', '')
            if self.current_room_name and room_name:
                if self.current_room_name not in room_name and "데이터_수집_모드" not in self.current_room_name:
                    return  # 다른 방의 데이터는 무시
            
            # 게임 카운트 업데이트
            round_number = game_data.get('round_number', 0)
            if round_number > self.game_count:
                self.game_count = round_number
            
            # 새로운 결과가 있는 경우 처리
            latest_result = game_data.get('latest_result', '')
            if latest_result and latest_result in ['P', 'B', 'T']:
                self._handle_game_result(game_data)
            
            # 베팅 타이밍 확인
            self._check_betting_opportunity(game_data)
            
        except Exception as e:
            self.logger.error(f"게임 데이터 처리 오류: {e}")

    def _handle_game_result(self, game_data: dict):
        """게임 결과 처리"""
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
            self.logger.error(f"게임 결과 처리 오류: {e}")

    def _check_betting_opportunity(self, game_data: dict):
        """베팅 기회 확인"""
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
            
            # 베팅 가능 상태 확인
            game_status = game_data.get('game_status', '')
            if game_status and 'betting' not in game_status.lower():
                return
            
            # 픽 생성
            next_pick = self._generate_pick_from_data(game_data)
            
            if next_pick in ['P', 'B']:
                # 베팅 실행
                round_number = game_data.get('round_number', self.game_count + 1)
                self._execute_betting(next_pick, round_number)
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")

    def _generate_pick_from_data(self, game_data: dict) -> str:
        """데이터 기반 픽 생성"""
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

    def _execute_betting(self, pick: str, round_number: int):
        """베팅 실행"""
        try:
            self.logger.info(f"🎯 베팅 실행: {pick} (라운드 {round_number})")
            
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
            self.logger.error(f"베팅 실행 오류: {e}")

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
        """방 모니터링 시작 - 데이터 수집 모드"""
        try:
            self.logger.info("🏠 JavaScript 웹소켓 기반 방 모니터링 시작")
            self.logger.info("💡 웹소켓 데이터 수집에 집중")
            
            # 데이터 수집 모드
            self.current_room_name = "웹소켓_데이터_수집_모드"
            self.game_count = 0
            self.wait_first_result = True
            
            # UI 업데이트
            self.main_window.update_betting_status(room_name="JavaScript 데이터 수집 중...")
            
            self.logger.info("✅ JavaScript 웹소켓 데이터 수집 모드 활성화")
            
            # 데이터 수집 모니터링 시작
            self._start_data_monitoring()
                
        except Exception as e:
            self.logger.error(f"방 모니터링 시작 오류: {e}")

    def _start_data_monitoring(self):
        """데이터 수집 모니터링 시작"""
        try:
            self.logger.info("🔍 JavaScript 웹소켓 데이터 모니터링 시작")
            
            # 즉시 상태 체크
            self._check_service_status()
            
            # 10초마다 상태 체크
            self.data_check_timer = QTimer()
            self.data_check_timer.timeout.connect(self._periodic_status_check)
            self.data_check_timer.start(10000)  # 10초마다
            
        except Exception as e:
            self.logger.error(f"데이터 모니터링 시작 오류: {e}")

    def _check_service_status(self):
        """서비스 상태 체크 (강화된 디버그)"""
        try:
            if self.websocket_service:
                status = self.websocket_service.get_connection_status()
                js_status = status.get('javascript_status', {})
                
                self.logger.info(f"📊 JavaScript 웹소켓 서비스 상태:")
                self.logger.info(f"  - 활성: {status.get('active', False)}")
                self.logger.info(f"  - 연결: {status.get('connected', False)}")
                self.logger.info(f"  - Python 메시지 수: {status.get('message_count', 0)}")
                self.logger.info(f"  - JavaScript 메시지 수: {js_status.get('messageCount', 0)}")
                self.logger.info(f"  - JavaScript 게임데이터 수: {js_status.get('gameDataCount', 0)}")
                
                # 불일치 감지
                python_count = status.get('message_count', 0)
                js_count = js_status.get('messageCount', 0)
                
                if abs(python_count - js_count) > 5:
                    self.logger.warning(f"⚠️ 메시지 카운트 불일치: Python={python_count}, JS={js_count}")
                
                # JavaScript에서 메시지는 있는데 게임 데이터가 없는 경우
                js_game_count = js_status.get('gameDataCount', 0)
                if js_count > 0 and js_game_count == 0:
                    self.logger.warning(f"⚠️ 게임 데이터 생성 문제: 메시지={js_count}개, 게임데이터={js_game_count}개")
                    
                    # 수동으로 최근 메시지 디버그
                    self.websocket_service._debug_javascript_messages()
            
            self.logger.info(f"📈 총 처리된 게임 데이터: {self.message_count}개")
            
        except Exception as e:
            self.logger.error(f"서비스 상태 체크 오류: {e}")

    def _periodic_status_check(self):
        """주기적 상태 체크 (문제 진단 강화)"""
        try:
            self.logger.info(f"🔎 주기적 상태 체크 - 처리된 데이터: {self.message_count}개")
            
            # 연결 상태 및 데이터 수집 상태 확인
            if self.websocket_service:
                status = self.websocket_service.get_connection_status()
                js_status = status.get('javascript_status', {})
                
                # 상세 진단
                python_count = self.message_count
                js_count = js_status.get('messageCount', 0)
                js_game_count = js_status.get('gameDataCount', 0)
                
                self.logger.info(f"📊 상세 진단:")
                self.logger.info(f"  Python 처리: {python_count}개")
                self.logger.info(f"  JS 메시지: {js_count}개")
                self.logger.info(f"  JS 게임데이터: {js_game_count}개")
                
                # 문제 상황 감지
                if js_count > 0 and js_game_count == 0:
                    self.logger.warning("🚨 데이터 파싱 문제 감지 - 메시지는 있지만 게임데이터 생성 안됨")
                elif js_count == 0:
                    self.logger.warning("🚨 메시지 수신 문제 감지 - JavaScript에서 메시지를 받지 못함")
                elif python_count != js_game_count:
                    self.logger.warning(f"🚨 데이터 전송 문제 감지 - JS게임데이터({js_game_count}) != Python처리({python_count})")
                else:
                    self.logger.info("✅ 데이터 수집 정상")
                
                # 연결 끊김 확인
                if not status.get('connected', False):
                    self.logger.warning("⚠️ JavaScript 웹소켓 연결 끊김 감지")
                    
                    # 재연결 시도
                    if self.is_trading_active:
                        self.logger.info("🔄 자동 재연결 시도")
                        self.websocket_service.force_reconnect()
            
        except Exception as e:
            self.logger.error(f"주기적 상태 체크 오류: {e}")

    def stop_trading(self):
        """JavaScript 하이브리드 웹소켓 기반 자동 매매 중지"""
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 이미 중지된 상태입니다.")
                return
                
            self.logger.info("🛑 JavaScript 하이브리드 웹소켓 자동 매매 중지 중...")
            
            # 데이터 체크 타이머 정리
            if hasattr(self, 'data_check_timer'):
                self.data_check_timer.stop()
            
            # JavaScript 하이브리드 서비스 중지
            if self.websocket_service:
                self.websocket_service.stop_websocket_connection()
                self.websocket_service = None
            
            # 호환성을 위한 기존 변수도 정리
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
            self.message_count = 0
            
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
            
            self.logger.info("✅ JavaScript 하이브리드 웹소켓 자동 매매 중지 완료")
            
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

    # ==================== 상태 확인 및 디버그 메서드들 ====================

    def get_interceptor_status(self) -> dict:
        """하이브리드 서비스 상태 정보 반환 (기존 호환성 유지)"""
        try:
            if self.websocket_service:
                js_status = self.websocket_service.get_connection_status()
                
                # 기존 인터셉터 형식으로 변환
                return {
                    'is_intercepting': js_status.get('active', False),
                    'performance_logs_enabled': True,  # JavaScript 방식이므로 항상 true
                    'cdp_session_active': js_status.get('connected', False),
                    'websocket_connections': 1 if js_status.get('connected') else 0,
                    'active_connections': 1 if js_status.get('connected') else 0,
                    'message_buffer_size': js_status.get('message_count', 0),
                    'processed_messages': js_status.get('message_count', 0),
                    'javascript_status': js_status
                }
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
            self.logger.error(f"하이브리드 서비스 상태 확인 오류: {e}")
            return {'error': str(e)}

    def get_current_status(self):
        """현재 상태 반환"""
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
            'last_game_data': self.last_game_data
        }

    def get_connection_stats(self):
        """연결 통계 반환"""
        try:
            return {
                'service_active': self.websocket_intercepting,
                'trading_active': self.is_trading_active,
                'message_count': self.message_count,
                'current_room': self.current_room_name,
                'game_count': self.game_count,
                'result_count': self.result_count,
                'service_stats': self.get_interceptor_status()
            }
        except Exception as e:
            self.logger.error(f"연결 통계 수집 오류: {e}")
            return {}

    def force_collect_data(self):
        """수동 데이터 수집 트리거 (하이브리드 서비스용)"""
        try:
            if self.websocket_service and self.websocket_intercepting:
                # JavaScript 상태 확인
                status = self.websocket_service.get_connection_status()
                self.logger.info(f"🔍 수동 데이터 수집: {status}")
                
                # JavaScript 상태 디버그
                debug_result = self.websocket_service.debug_javascript_state()
                self.logger.info(f"🔍 JavaScript 디버그: {debug_result}")
                
                return status.get('connected', False)
            else:
                self.logger.warning("하이브리드 서비스가 활성화되지 않음")
                return False
                
        except Exception as e:
            self.logger.error(f"수동 데이터 수집 오류: {e}")
            return False

    def debug_service_status(self):
        """디버그용 하이브리드 서비스 상태 출력"""
        try:
            if self.websocket_service:
                self.logger.info("🔍 JavaScript 하이브리드 서비스 디버그 상태:")
                
                # 연결 상태
                status = self.websocket_service.get_connection_status()
                for key, value in status.items():
                    self.logger.info(f"  - {key}: {value}")
                
                # JavaScript 상태
                js_debug = self.websocket_service.debug_javascript_state()
                self.logger.info("🔍 JavaScript 환경:")
                for key, value in js_debug.items():
                    self.logger.info(f"  - {key}: {value}")
                    
            else:
                self.logger.info("  - 하이브리드 서비스 인스턴스 없음")
                
        except Exception as e:
            self.logger.error(f"디버그 상태 출력 오류: {e}")

    def force_reconnect_websocket(self):
        """웹소켓 강제 재연결"""
        try:
            if self.websocket_service:
                self.logger.info("🔄 웹소켓 강제 재연결 시도")
                return self.websocket_service.force_reconnect()
            else:
                self.logger.warning("재연결할 웹소켓 서비스가 없습니다")
                return False
                
        except Exception as e:
            self.logger.error(f"강제 재연결 오류: {e}")
            return False

    def get_websocket_connection_info(self):
        """웹소켓 연결 정보 반환"""
        try:
            if self.websocket_service:
                return self.websocket_service.get_connection_status()
            return {'connected': False, 'error': 'No websocket service'}
            
        except Exception as e:
            self.logger.error(f"연결 정보 확인 오류: {e}")
            return {'connected': False, 'error': str(e)}

    def emergency_stop(self):
        """비상 정지"""
        try:
            self.logger.warning("🚨 비상 정지 실행")
            
            # 모든 플래그 즉시 설정
            self.stop_all_processes = True
            self.is_trading_active = False
            self.websocket_intercepting = False
            
            # 웹소켓 서비스 강제 종료
            if self.websocket_service:
                self.websocket_service.stop_websocket_connection()
                self.websocket_service = None
            
            self.websocket_interceptor = None
            
            # 타이머 강제 중지
            if hasattr(self.main_window, 'timer'):
                self.main_window.timer.stop()
                QApplication.processEvents()
            
            # 데이터 체크 타이머도 정리
            if hasattr(self, 'data_check_timer'):
                self.data_check_timer.stop()
            
            # UI 상태 강제 복원
            self.main_window.start_button.setEnabled(True)
            self.main_window.stop_button.setEnabled(False)
            self.main_window.update_button_styles()
            
            self.logger.info("비상 정지 완료")
            
        except Exception as e:
            self.logger.error(f"비상 정지 중 오류: {e}")

    # ==================== 기존 호환성 메서드들 ====================

    def get_websocket_status(self):
        """기존 호환성을 위한 메서드"""
        return self.get_interceptor_status()

    def get_recent_websocket_messages(self, count=10):
        """기존 호환성을 위한 메서드 (더미)"""
        # JavaScript 방식에서는 메시지 버퍼를 직접 노출하지 않음
        return []

    def debug_interceptor_status(self):
        """기존 호환성을 위한 메서드"""
        return self.debug_service_status()

    # ==================== 정리 ====================

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            if hasattr(self, 'websocket_service') and self.websocket_service:
                self.websocket_service.stop_websocket_connection()
            
            if hasattr(self, 'data_check_timer'):
                self.data_check_timer.stop()
                
        except:
            pass