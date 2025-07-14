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
from utils.server_client import BaccaratServerClient

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

        # 서버 클라이언트 초기화
        self.server_client = BaccaratServerClient(logger=self.logger)
        
        # 웹소켓 서비스
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
        
        # 연패 방 관리
        self.target_streak_rooms = []     # 연패 기준을 만족하는 방 목록
        self.current_target_room = None   # 현재 입장할 타겟 방
        self.is_entering_room = False     # 방 입장 진행 중
        self.room_entry_in_progress = False
        
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
        """연패 감지 및 자동 방 입장 기반 자동 매매 시작"""
        try:
            self.logger.info("🚀 연패 감지 자동 매매 시작")
            
            # 기본 검증
            if not self.helpers.validate_trading_prerequisites():
                return

            # 설정 초기화
            self.refresh_settings()
            
            # 목표 금액 도달 플래그 초기화
            if hasattr(self.balance_service, '_target_amount_reached'):
                del self.balance_service._target_amount_reached

            self.stop_all_processes = False

            # 서버 상태 확인
            if not self._check_server_connection():
                return

            # 에볼루션 로비 준비
            if not self._ensure_evolution_lobby_ready():
                return

            # 웹소켓 서비스 시작
            if not self._start_websocket_service():
                QMessageBox.warning(
                    self.main_window,
                    "웹소켓 서비스 실패",
                    "연패 감지 웹소켓 서비스를 시작할 수 없습니다."
                )
                return

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info("🎯 연패 감지 자동 매매 시작 완료")
            
            # UI 업데이트
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(True)
            self.main_window.update_button_styles()
            
            # 연패 감지 시작
            self._start_streak_monitoring()

        except Exception as e:
            self.logger.error(f"자동 매매 시작 오류: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window, 
                "자동 매매 오류", 
                f"자동 매매 시작 중 오류가 발생했습니다.\n{str(e)}"
            )

    def _check_server_connection(self) -> bool:
        """서버 연결 상태 확인"""
        try:
            self.logger.info("🔍 서버 연결 상태 확인 중...")
            
            if self.server_client.get_server_status():
                self.logger.info("✅ 서버 연결 성공")
                return True
            else:
                QMessageBox.warning(
                    self.main_window,
                    "서버 연결 실패",
                    "서버에 연결할 수 없습니다.\n서버 상태를 확인해주세요."
                )
                return False
                
        except Exception as e:
            self.logger.error(f"서버 연결 확인 오류: {e}")
            QMessageBox.critical(
                self.main_window,
                "서버 오류",
                f"서버 연결 확인 중 오류가 발생했습니다.\n{str(e)}"
            )
            return False

    def _start_websocket_service(self) -> bool:
        """연패 감지 웹소켓 서비스 시작"""
        try:
            self.logger.info("🎯 연패 감지 웹소켓 서비스 시작")
            
            # 웹소켓 URL 추출
            websocket_urls = self._extract_websocket_urls_for_logging()
            
            if not websocket_urls:
                self.logger.error("❌ 웹소켓 URL을 찾을 수 없습니다")
                return False
            
            websocket_url = websocket_urls[0]
            self.logger.info(f"📡 사용할 웹소켓 URL: {websocket_url[:100]}...")
            
            # 연패 감지 서비스 생성
            from services.websocket_hybrid_service import WebSocketHybridService
            self.websocket_service = WebSocketHybridService(
                devtools=self.devtools,
                server_client=self.server_client,
                logger=self.logger
            )
            
            # 호환성을 위한 변수 설정
            self.websocket_interceptor = self.websocket_service
            
            # 시그널 연결
            self._connect_websocket_signals()
            
            # 웹소켓 연결 시작
            if self.websocket_service.start_websocket_connection(websocket_url):
                self.websocket_intercepting = True
                self.logger.info("✅ 연패 감지 웹소켓 서비스 시작 성공")
                return True
            else:
                self.logger.error("❌ 웹소켓 연결 실패")
                return False
                
        except Exception as e:
            self.logger.error(f"연패 감지 웹소켓 서비스 시작 오류: {e}")
            return False
        
    def _extract_websocket_urls_for_logging(self) -> list:
        """웹소켓 URL 추출"""
        try:
            self.logger.info("⚡ 웹소켓 URL 추출 시작")
            start_time = time.time()
            
            from services.websocket_parser import WebSocketParser
            ws_parser = WebSocketParser(self.devtools, self.logger)
            
            websocket_urls = []
            try:
                websocket_urls = ws_parser.auto_detect_websocket_urls()
            except Exception as e:
                self.logger.warning(f"웹소켓 URL 추출 중 오류: {e}")
                websocket_urls = []
            
            elapsed_time = time.time() - start_time
            
            if websocket_urls:
                first_url = websocket_urls[0]
                self.logger.info(f"📡 WebSocket 연결 감지: {first_url}")
                self.logger.info(f"✅ 웹소켓 URL 추출 완료 ({elapsed_time:.1f}초, {len(websocket_urls)}개 발견)")
            else:
                self.logger.warning(f"❌ 웹소켓 URL 추출 실패 ({elapsed_time:.1f}초)")
            
            if hasattr(ws_parser, 'shutdown'):
                ws_parser.shutdown()
            
            return websocket_urls
            
        except Exception as e:
            self.logger.error(f"웹소켓 URL 추출 오류: {e}")
            return []

    def _connect_websocket_signals(self):
        """웹소켓 서비스 시그널 연결"""
        try:
            if not self.websocket_service:
                return
                
            # 게임 데이터 수신 시그널
            self.websocket_service.game_data_received.connect(
                self._on_game_data_received
            )
            
            # 연결 상태 변경 시그널
            self.websocket_service.connection_status_changed.connect(
                self._on_connection_status_changed
            )
            
            # 오류 발생 시그널
            self.websocket_service.error_occurred.connect(
                self._on_websocket_error
            )
            
            # 연패 방 발견 시그널
            self.websocket_service.streak_room_found.connect(
                self._on_streak_room_found
            )
            
            # 방 입장 요청 시그널
            self.websocket_service.room_entry_requested.connect(
                self._on_room_entry_requested
            )
            
            self.logger.info("연패 감지 웹소켓 시그널 연결 완료")
            
        except Exception as e:
            self.logger.error(f"웹소켓 시그널 연결 오류: {e}")

    def _on_streak_room_found(self, streak_data: dict):
        """연패 방 발견 시 처리"""
        try:
            room_id = streak_data.get('room_id', '')
            room_name = streak_data.get('room_name', '')
            streak_count = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🚨 연패 방 발견! {room_name} - {streak_count}연패")
            
            # 타겟 연패 방 리스트에 추가 (중복 체크)
            existing_room = next((room for room in self.target_streak_rooms if room['room_id'] == room_id), None)
            
            if existing_room:
                existing_room.update(streak_data)
                self.logger.info(f"📝 연패 방 정보 업데이트: {room_name}")
            else:
                self.target_streak_rooms.append(streak_data)
                self.logger.info(f"➕ 새 연패 방 추가: {room_name}")
            
            # 연패 수가 높은 순으로 정렬
            self.target_streak_rooms.sort(key=lambda x: x.get('streak_count', 0), reverse=True)
            
            # UI 업데이트
            self._update_streak_room_display()
                
        except Exception as e:
            self.logger.error(f"연패 방 발견 처리 오류: {e}")

    def _on_room_entry_requested(self, streak_data: dict):
        """방 입장 요청 처리"""
        try:
            if self.room_entry_in_progress or self.is_entering_room:
                self.logger.info(f"방 입장이 이미 진행 중입니다. 요청 무시: {streak_data.get('room_name', '')}")
                return
            
            room_name = streak_data.get('room_name', '')
            streak_count = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🚪 방 입장 요청 처리: {room_name} ({streak_count}연패)")
            
            # 방 입장 플래그 설정
            self.room_entry_in_progress = True
            self.is_entering_room = True
            self.current_target_room = streak_data
            
            # UI 업데이트
            self.main_window.update_betting_status(
                room_name=f"입장 중: {room_name}",
                status=f"{streak_count}연패 방 입장 시도"
            )
            
            # 실제 방 입장 실행
            self._execute_room_entry(streak_data)
                
        except Exception as e:
            self.logger.error(f"방 입장 요청 처리 오류: {e}")
            self.room_entry_in_progress = False
            self.is_entering_room = False

    def _execute_room_entry(self, streak_data: dict):
        """실제 방 입장 실행"""
        try:
            room_name = streak_data.get('room_name', '')
            room_id = streak_data.get('room_id', '')
            streak_count = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🚪 방 입장 실행: {room_name} ({room_id})")
            
            # 기존 방 입장 서비스 활용
            if hasattr(self.room_entry_service, 'enter_room_by_name'):
                success = self.room_entry_service.enter_room_by_name(room_name)
            else:
                success = self._fallback_room_entry(room_name)
            
            if success:
                self.logger.info(f"✅ 방 입장 성공: {room_name}")
                
                # 현재 방 정보 업데이트
                self.current_room_name = room_name
                
                # 게임 모니터링 시작
                self._start_game_monitoring_in_room(streak_data)
                
                # UI 업데이트
                self.main_window.update_betting_status(
                    room_name=room_name,
                    status=f"{streak_count}연패 방 입장 완료",
                    streak_info=f"{streak_count}연패"
                )
                
            else:
                self.logger.warning(f"❌ 방 입장 실패: {room_name}")
                
                # 실패한 방을 타겟 목록에서 제거
                self.target_streak_rooms = [room for room in self.target_streak_rooms if room['room_id'] != room_id]
                
                # 다른 방이 있으면 재시도
                if self.target_streak_rooms:
                    self.logger.info("다른 연패 방으로 재시도...")
                    next_room = self.target_streak_rooms[0]
                    self._execute_room_entry(next_room)
                    return
            
            # 방 입장 플래그 해제
            self.room_entry_in_progress = False
            self.is_entering_room = False
                
        except Exception as e:
            self.logger.error(f"방 입장 실행 오류: {e}")
            self.room_entry_in_progress = False
            self.is_entering_room = False

    def _fallback_room_entry(self, room_name: str) -> bool:
        """폴백 방 입장 로직"""
        try:
            self.logger.info(f"폴백 방 입장 시도: {room_name}")
            
            # 간단한 방 입장 로직 (실제로는 DOM 조작 필요)
            # 여기서는 성공으로 가정
            time.sleep(2)  # 입장 시뮬레이션
            
            return True
            
        except Exception as e:
            self.logger.error(f"폴백 방 입장 오류: {e}")
            return False

    def _start_game_monitoring_in_room(self, streak_data: dict):
        """방 입장 후 게임 모니터링 시작"""
        try:
            room_name = streak_data.get('room_name', '')
            streak_count = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🎮 게임 모니터링 시작: {room_name} ({streak_count}연패)")
            
            # 게임 상태 초기화
            self.game_count = 0
            self.result_count = 0
            self.wait_first_result = True
            self.processed_rounds = set()
            
            # 현재 타겟 방 설정
            self.current_target_room = streak_data
            
        except Exception as e:
            self.logger.error(f"게임 모니터링 시작 오류: {e}")

    def _start_streak_monitoring(self):
        """연패 모니터링 시작"""
        try:
            self.logger.info("🏠 연패 모니터링 시작")
            
            # UI 업데이트
            self.main_window.update_betting_status(room_name="연패 방 감지 중...")
            
            self.logger.info("✅ 연패 모니터링 활성화")
                
        except Exception as e:
            self.logger.error(f"연패 모니터링 시작 오류: {e}")

    # utils/trading_manager.py의 _update_streak_room_display 메소드 수정

    def _update_streak_room_display(self):
        """연패 방 목록 UI 업데이트"""
        try:
            if self.target_streak_rooms:
                top_room = self.target_streak_rooms[0]
                room_name = top_room.get('room_name', '')
                streak_count = top_room.get('streak_count', 0)
                
                if not self.room_entry_in_progress and not self.current_target_room:
                    # status 매개변수 제거하고 로그로 대체
                    self.main_window.update_betting_status(
                        room_name=f"발견: {room_name}"
                    )
                    self.logger.info(f"연패 방 대기 중: {room_name} ({streak_count}연패)")
            else:
                if not self.room_entry_in_progress and not self.current_target_room:
                    self.main_window.update_betting_status(room_name="연패 방 감지 중...")
                    
        except Exception as e:
            self.logger.error(f"연패 방 표시 업데이트 오류: {e}")
            
    def _on_connection_status_changed(self, connected: bool):
        """웹소켓 연결 상태 변경 처리"""
        try:
            status_text = "연결됨" if connected else "연결 끊김"
            self.logger.info(f"🔌 연패 감지 웹소켓 상태 변경: {status_text}")
            
            if connected:
                self.logger.info("✅ 실시간 연패 감지 시작")
            else:
                if self.is_trading_active:
                    self.logger.warning("⚠️ 자동 매매 중 연결 끊김")
                    
        except Exception as e:
            self.logger.error(f"연결 상태 변경 처리 오류: {e}")

    def _on_game_data_received(self, game_data: dict):
        """게임 데이터 수신 처리"""
        try:
            self.last_game_data = game_data
            self.message_count += 1
            
            # 현재 방과 일치하는 데이터인지 확인
            room_name = game_data.get('room_name', '')
            if self.current_target_room and room_name:
                target_room_name = self.current_target_room.get('room_name', '')
                if target_room_name in room_name:
                    # 현재 방의 게임 데이터 처리
                    self._process_current_room_game_data(game_data)
                
        except Exception as e:
            self.logger.error(f"게임 데이터 수신 처리 오류: {e}")

    def _process_current_room_game_data(self, game_data: dict):
        """현재 방의 게임 데이터 처리"""
        try:
            round_number = game_data.get('round_number', 0)
            latest_result = game_data.get('latest_result', '')
            
            # 게임 카운트 업데이트
            if round_number > self.game_count:
                self.game_count = round_number
            
            # 새로운 결과가 있는 경우 처리
            if latest_result and latest_result in ['P', 'B', 'T']:
                self._handle_game_result(game_data)
            
            # 베팅 타이밍 확인
            if self.current_target_room and not self.room_entry_in_progress:
                self._check_betting_opportunity(game_data)
            
        except Exception as e:
            self.logger.error(f"현재 방 게임 데이터 처리 오류: {e}")

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
            if (hasattr(self.betting_service, 'has_bet_current_round') and 
                self.betting_service.has_bet_current_round):
                
                last_bet = self.betting_service.get_last_bet()
                
                if last_bet and last_bet['type'] in ['P', 'B']:
                    result_status = self.bet_helper.process_bet_result(
                        last_bet['type'], 
                        latest_result, 
                        round_number
                    )
                    
                    self.logger.info(f"베팅 결과 처리: {result_status}")
                    
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
            
            # 연패 방에서만 베팅 실행
            if not self.current_target_room:
                return
            
            # 픽 생성
            next_pick = self._generate_pick_for_streak_room()
            
            if next_pick in ['P', 'B']:
                round_number = game_data.get('round_number', self.game_count + 1)
                self._execute_betting(next_pick, round_number)
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")

    def _generate_pick_for_streak_room(self) -> str:
        """연패 방을 위한 픽 생성"""
        try:
            if not self.current_target_room:
                return 'P'
            
            # 연패 정보 기반 픽 생성 (연패 반대로 베팅)
            streak_type = self.current_target_room.get('streak_type', '')
            
            # ExcelTradingService의 ChoicePickSystem 사용
            if hasattr(self.excel_trading_service, 'choice_pick_system'):
                pick = self.excel_trading_service.choice_pick_system.generate_choice_pick()
                if pick in ['P', 'B']:
                    return pick
            
            return 'P'  # 기본값
            
        except Exception as e:
            self.logger.error(f"픽 생성 오류: {e}")
            return 'P'

    def _execute_betting(self, pick: str, round_number: int):
        """베팅 실행"""
        try:
            streak_info = ""
            if self.current_target_room:
                streak_count = self.current_target_room.get('streak_count', 0)
                streak_info = f" (연패: {streak_count})"
            
            self.logger.info(f"🎯 베팅 실행: {pick} (라운드 {round_number}){streak_info}")
            
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
                self.logger.info(f"✅ 베팅 성공: {pick}, 금액: {bet_amount:,}원{streak_info}")
                self.main_window.update_betting_status(
                    pick=pick, 
                    bet_amount=bet_amount,
                    streak_info=streak_info
                )
            else:
                self.logger.warning(f"❌ 베팅 실패: {pick}")
                
        except Exception as e:
            self.logger.error(f"베팅 실행 오류: {e}")

    def _handle_win_result(self):
        """승리 결과 처리"""
        try:
            self.logger.info("🎉 승리 처리 - 새로운 연패 방 검색")
            
            # 위젯 초기화
            if hasattr(self.main_window, 'betting_widget'):
                self.main_window.betting_widget.room_position_counter = 0
                self.main_window.betting_widget.reset_step_markers()
            
            # 마틴 서비스 초기화
            if hasattr(self, 'martin_service'):
                self.martin_service.reset()
            
            # 현재 방 정보 초기화
            self.current_target_room = None
            self.target_streak_rooms = []
            
            # 새로운 연패 방 검색 모드로 전환
            self._return_to_streak_monitoring()
            
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
                self.logger.info("연패 조건 달성 - 새로운 방 검색")
                self._return_to_streak_monitoring()
                
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
            if hasattr(self, 'excel_trading_service'):
                return self.excel_trading_service.should_change_room()
            
            return False
            
        except Exception as e:
            self.logger.error(f"연패 확인 오류: {e}")
            return False

    def _return_to_streak_monitoring(self):
        """연패 모니터링 모드로 복귀"""
        try:
            self.logger.info("🔄 연패 모니터링 모드로 복귀")
            
            # 현재 방 정보 초기화
            self.current_target_room = None
            self.current_room_name = ""
            self.target_streak_rooms = []
            
            # 상태 초기화
            self.room_entry_in_progress = False
            self.is_entering_room = False
            self.wait_first_result = False
            
            # UI 업데이트
            self.main_window.update_betting_status(room_name="연패 방 감지 중...")
            
            # 현재 방에서 나가기 (선택사항)
            try:
                if hasattr(self, 'game_monitoring_service'):
                    self.game_monitoring_service.close_current_room()
            except:
                pass
            
        except Exception as e:
            self.logger.error(f"연패 모니터링 복귀 오류: {e}")

    def _on_websocket_error(self, error_message: str):
        """웹소켓 오류 발생 시 처리"""
        try:
            self.logger.error(f"🚨 연패 감지 웹소켓 오류: {error_message}")
            
            if "connection" in error_message.lower() or "timeout" in error_message.lower():
                self.logger.warning("심각한 웹소켓 오류로 인한 자동 매매 중지")
                self.stop_trading()
                
        except Exception as e:
            self.logger.error(f"웹소켓 오류 처리 중 오류: {e}")

    def stop_trading(self):
        """연패 감지 자동 매매 중지"""
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 이미 중지된 상태입니다.")
                return
                
            self.logger.info("🛑 연패 감지 자동 매매 중지 중...")
            
            # 웹소켓 서비스 중지
            if self.websocket_service:
                self.websocket_service.stop_websocket_connection()
                self.websocket_service = None
            
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
            
            # 연패 방 관련 상태 초기화
            self.target_streak_rooms = []
            self.current_target_room = None
            self.room_entry_in_progress = False
            self.is_entering_room = False
            
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
            
            self.logger.info("✅ 연패 감지 자동 매매 중지 완료")
            
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
            
            # 웹소켓 서비스에 연패 기준 업데이트
            if self.websocket_service:
                streak_threshold = getattr(self.settings_manager, 'streak_threshold', 3)
                self.websocket_service.update_streak_threshold(streak_threshold)
                    
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
        """웹소켓 서비스 상태 정보 반환"""
        try:
            if self.websocket_service:
                js_status = self.websocket_service.get_connection_status()
                
                return {
                    'is_intercepting': js_status.get('active', False),
                    'performance_logs_enabled': True,
                    'cdp_session_active': js_status.get('connected', False),
                    'websocket_connections': 1 if js_status.get('connected') else 0,
                    'active_connections': 1 if js_status.get('connected') else 0,
                    'message_buffer_size': js_status.get('total_messages', 0),
                    'processed_messages': js_status.get('total_messages', 0),
                    'server_sent_count': js_status.get('sent_to_server', 0),
                    'filtered_room_count': js_status.get('filtered_room_messages', 0),
                    'target_streak_rooms': len(self.target_streak_rooms),
                    'current_target_room': self.current_target_room,
                    'room_entry_in_progress': self.room_entry_in_progress
                }
            else:
                return {
                    'is_intercepting': False,
                    'performance_logs_enabled': False,
                    'cdp_session_active': False,
                    'websocket_connections': 0,
                    'active_connections': 0,
                    'message_buffer_size': 0,
                    'processed_messages': 0,
                    'server_sent_count': 0,
                    'filtered_room_count': 0,
                    'target_streak_rooms': 0,
                    'current_target_room': None,
                    'room_entry_in_progress': False
                }
        except Exception as e:
            self.logger.error(f"웹소켓 상태 확인 오류: {e}")
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
            'last_game_data': self.last_game_data,
            'target_streak_rooms': len(self.target_streak_rooms),
            'current_target_room': self.current_target_room,
            'room_entry_in_progress': self.room_entry_in_progress,
            'server_connected': bool(self.server_client and self.server_client.get_server_status())
        }

    def force_collect_data(self):
        """수동 데이터 수집 트리거"""
        try:
            if self.websocket_service and self.websocket_intercepting:
                status = self.websocket_service.get_connection_status()
                self.logger.info(f"🔍 수동 데이터 수집: {status}")
                
                return status.get('connected', False)
            else:
                self.logger.warning("웹소켓 서비스가 활성화되지 않음")
                return False
                
        except Exception as e:
            self.logger.error(f"수동 데이터 수집 오류: {e}")
            return False

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

    def get_streak_room_info(self):
        """연패 방 정보 반환"""
        try:
            return {
                'target_streak_rooms': self.target_streak_rooms,
                'current_target_room': self.current_target_room,
                'room_entry_in_progress': self.room_entry_in_progress,
                'is_entering_room': self.is_entering_room,
                'room_count': len(self.target_streak_rooms)
            }
        except Exception as e:
            self.logger.error(f"연패 방 정보 확인 오류: {e}")
            return {'error': str(e)}

    def debug_service_status(self):
        """디버그용 서비스 상태 출력"""
        try:
            if self.websocket_service:
                self.logger.info("🔍 연패 감지 서비스 디버그 상태:")
                
                status = self.websocket_service.get_connection_status()
                for key, value in status.items():
                    self.logger.info(f"  - {key}: {value}")
                
                self.logger.info(f"🏠 연패 방 관리 상태:")
                self.logger.info(f"  - 타겟 연패 방: {len(self.target_streak_rooms)}개")
                self.logger.info(f"  - 현재 타겟 방: {self.current_target_room}")
                self.logger.info(f"  - 방 입장 진행 중: {self.room_entry_in_progress}")
                
                server_connected = bool(self.server_client and self.server_client.get_server_status())
                self.logger.info(f"📡 서버 연결 상태: {server_connected}")
                    
            else:
                self.logger.info("  - 웹소켓 서비스 인스턴스 없음")
                
        except Exception as e:
            self.logger.error(f"디버그 상태 출력 오류: {e}")

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
            
            # 연패 방 상태 초기화
            self.target_streak_rooms = []
            self.current_target_room = None
            self.room_entry_in_progress = False
            self.is_entering_room = False
            
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
        """기존 호환성을 위한 메서드"""
        return []

    def debug_interceptor_status(self):
        """기존 호환성을 위한 메서드"""
        return self.debug_service_status()

    def __del__(self):
        """소멸자 - 리소스 정리"""
        try:
            if hasattr(self, 'websocket_service') and self.websocket_service:
                self.websocket_service.stop_websocket_connection()
        except:
            pass