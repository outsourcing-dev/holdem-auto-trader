# utils/trading_manager_modules/room_entry_handler.py
import time
import logging
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from utils.game_monitoring_worker import GameMonitoringWorker
from utils.betting_worker import AsyncBettingManager


class RoomEntryHandler(QObject):
    """방 입장 및 관리 전담 클래스 - 멀티쓰레드 지원"""
    
    # 시그널 정의
    room_entered = pyqtSignal(dict)  # 방 입장 완료
    room_exited = pyqtSignal(str)    # 방 나가기 완료
    
    def __init__(self, trading_manager):
        super().__init__()
        self.tm = trading_manager
        self.logger = trading_manager.logger
        
        # 기존 타이머 제거 - 멀티쓰레드로 대체
        self.iframe_timer = None
        
        # 🧵 멀티쓰레드 워커들 초기화
        self.game_monitoring_worker = GameMonitoringWorker(trading_manager, self.logger)
        self.betting_manager = AsyncBettingManager(trading_manager, self.logger)
        
        # 워커 시그널 연결
        self._connect_worker_signals()

    def _connect_worker_signals(self):
        """워커 시그널 연결"""
        try:
            # 게임 모니터링 워커 시그널
            self.game_monitoring_worker.game_state_updated.connect(self._on_game_state_updated)
            self.game_monitoring_worker.betting_requested.connect(self._on_betting_requested)
            self.game_monitoring_worker.game_result_received.connect(self._on_game_result_received)
            self.game_monitoring_worker.room_exit_requested.connect(self._on_room_exit_requested)
            self.game_monitoring_worker.error_occurred.connect(self._on_worker_error)
            self.game_monitoring_worker.status_updated.connect(self._on_status_updated)
            
            # 베팅 매니저 시그널은 AsyncBettingManager 내부에서 처리됨
            
            self.logger.info("🔗 워커 시그널 연결 완료")
            
        except Exception as e:
            self.logger.error(f"워커 시그널 연결 오류: {e}")

    def execute_room_entry(self, streak_data: dict):
        """방 입장 후 웹소켓 일시정지 및 iframe 기반 베팅 - 재시도 로직 포함"""
        self._execute_room_entry_with_retry(streak_data, max_retries=5)

    def _execute_room_entry_with_retry(self, streak_data: dict, max_retries: int = 5, current_attempt: int = 1):
        """방 입장 재시도 로직"""
        try:
            room_name = streak_data.get('room_name', '')
            room_id = streak_data.get('room_id', '')
            expected_streak = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🚪 방 입장 시도 ({current_attempt}/{max_retries}): {room_name}")
            
            # 1. 웹소켓 일시정지 (첫 시도에만)
            if current_attempt == 1:
                self._pause_websocket_monitoring()
            
            # 2. 방 입장 시도
            if hasattr(self.tm.room_entry_service, 'enter_room_by_name'):
                success = self.tm.room_entry_service.enter_room_by_name(room_name)
            else:
                success = self._fallback_room_entry(room_name)
            
            if success:
                # 3. 방 로딩 대기 (비동기 처리)
                QTimer.singleShot(3000, lambda: self._continue_room_entry_verification(streak_data, current_attempt, max_retries))
                return  # 비동기 처리를 위해 여기서 반환
                
                # 5. 새 방 입장 시 마틴 상태 초기화
                if hasattr(self.tm, 'martin_service'):
                    self.tm.martin_service.reset_room_bet_status()
                
                # 6. 게임 수 조건 확인
                if not self._check_game_count_condition(room_id, room_name):
                    self.logger.warning(f"⚠️ 게임 수 조건 미충족 - 방 나가기")
                    
                    # 조건 미충족 방을 제외 리스트에 추가
                    if room_id:
                        self.tm.excluded_rooms[room_id] = {
                            'timestamp': time.time(),
                            'reason': 'condition_fail'
                        }
                    
                    # 방 나가기 및 연패 모니터링 복귀
                    if hasattr(self.tm, 'game_monitoring_service'):
                        self.tm.game_monitoring_service.close_current_room()
                    self._resume_websocket_monitoring()
                    self.tm.room_entry_in_progress = False
                    self.tm.is_entering_room = False
                    self.tm.streak_handler.return_to_streak_monitoring()
                    return
                
                # 7. 방 입장 성공 - 게임 모니터링 시작
                self.logger.info(f"✅ 방 입장 성공: {room_name}")
                self.tm.current_room_name = room_name
                self.tm.current_target_room = streak_data
                self.tm.room_entry_in_progress = False
                
                # 8. 새 방 입장 시 베팅 추적기 통계 초기화
                if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                    self.tm.game_processor.betting_tracker.reset_room_statistics()
                    self.logger.info("🔄 새 방 입장으로 베팅 통계 초기화")
                
                self._start_multithreaded_game_monitoring(streak_data)
                
            else:
                # 재시도 필요한지 확인
                if current_attempt < max_retries:
                    self.logger.warning(f"❌ 방 입장 실패 - 재시도 {current_attempt + 1}/{max_retries}")
                    time.sleep(2)
                    self._execute_room_entry_with_retry(streak_data, max_retries, current_attempt + 1)
                    return
                else:
                    # 모든 재시도 실패
                    self.logger.error(f"❌ 방 입장 최종 실패: {room_name}")
                    self._handle_room_entry_final_failure(room_id)
                    return
                
        except Exception as e:
            self.logger.error(f"방 입장 오류: {e}")
            
            # 재시도 필요한지 확인 (비동기)
            if current_attempt < max_retries:
                QTimer.singleShot(2000, lambda: self._execute_room_entry_with_retry(streak_data, max_retries, current_attempt + 1))
            else:
                # 모든 재시도 실패
                self.logger.error(f"❌ 방 입장 최종 실패: {room_name}")
                self._handle_room_entry_final_failure(room_id)
    
    def _continue_room_entry_verification(self, streak_data: dict, current_attempt: int, max_retries: int):
        """🧵 비동기 방 입장 검증 계속 (UI 블로킹 방지)"""
        try:
            room_id = streak_data.get('room_id', '')
            room_name = streak_data.get('room_name', '')
            
            # 4. iframe 값 체크로 실제 입장 확인
            if not self._verify_room_entry_success(room_id, room_name, current_attempt):
                self.logger.warning(f"⚠️ iframe 검증 실패 - 재시도 {current_attempt + 1}/{max_retries}")
                
                # 재시도 필요한지 확인
                if current_attempt < max_retries:
                    QTimer.singleShot(2000, lambda: self._execute_room_entry_with_retry(streak_data, max_retries, current_attempt + 1))
                    return
                else:
                    # 모든 재시도 실패
                    self.logger.error(f"❌ 방 입장 최종 실패: {room_name}")
                    self._handle_room_entry_final_failure(room_id)
                    return
            
            # 5. 새 방 입장 시 마틴 상태 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset_room_bet_status()
            
            # 6. 게임 수 조건 확인
            if not self._check_game_count_condition(room_id, room_name):
                self.logger.warning(f"⚠️ 게임 수 조건 미충족 - 방 나가기")
                
                # 조건 미충족 방을 제외 리스트에 추가
                if room_id:
                    self.tm.excluded_rooms[room_id] = {
                        'timestamp': time.time(),
                        'reason': 'condition_fail'
                    }
                
                # 방 나가기 및 연패 모니터링 복귀
                if hasattr(self.tm, 'game_monitoring_service'):
                    self.tm.game_monitoring_service.close_current_room()
                self._resume_websocket_monitoring()
                self.tm.room_entry_in_progress = False
                self.tm.is_entering_room = False
                self.tm.streak_handler.return_to_streak_monitoring()
                return
            
            # 7. 방 입장 성공 - 게임 모니터링 시작
            self.logger.info(f"✅ 방 입장 성공: {room_name}")
            self.tm.current_room_name = room_name
            self.tm.current_target_room = streak_data
            self.tm.room_entry_in_progress = False
            
            # 8. 새 방 입장 시 베팅 추적기 통계 초기화
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                self.tm.game_processor.betting_tracker.reset_room_statistics()
                self.logger.info("🔄 새 방 입장으로 베팅 통계 초기화")
            
            self._start_multithreaded_game_monitoring(streak_data)
            
        except Exception as e:
            self.logger.error(f"방 입장 검증 계속 오류: {e}")

    def _pause_websocket_monitoring(self):
        """웹소켓 모니터링 일시정지"""
        try:
            if hasattr(self.tm, 'websocket_manager') and self.tm.websocket_manager.websocket_service:
                if hasattr(self.tm.websocket_manager.websocket_service, 'message_collection_timer'):
                    self.tm.websocket_manager.websocket_service.message_collection_timer.stop()
        except Exception as e:
            self.logger.error(f"웹소켓 일시정지 오류: {e}")

    def _resume_websocket_monitoring(self):
        """웹소켓 모니터링 재개"""
        try:
            if hasattr(self.tm, 'websocket_manager') and self.tm.websocket_manager.websocket_service:
                self.tm.websocket_manager.websocket_service._start_message_collection()
        except Exception as e:
            self.logger.error(f"웹소켓 재개 오류: {e}")

    def _start_multithreaded_game_monitoring(self, streak_data: dict):
        """🧵 멀티쓰레드 기반 게임 모니터링 시작 - UI 블로킹 방지"""
        try:
            # 게임 상태 초기화
            self.tm.game_count = 0
            self.tm.result_count = 0
            self.tm.processed_rounds = set()
            self.tm.first_bet_after_entry = True
            
            # 🧵 게임 모니터링 워커 시작 (별도 쓰레드)
            self.game_monitoring_worker.start_monitoring(streak_data)
            
            self.logger.info(f"🧵 멀티쓰레드 게임 모니터링 시작: {streak_data.get('room_name')}")
            
            # 방 입장 완료 시그널 발송
            self.room_entered.emit(streak_data)
            
        except Exception as e:
            self.logger.error(f"멀티쓰레드 모니터링 시작 오류: {e}")

    def _start_iframe_game_monitoring(self, streak_data: dict):
        """레거시 iframe 모니터링 (멀티쓰레드로 대체됨)"""
        self.logger.warning("⚠️ 레거시 iframe 모니터링 호출 - 멀티쓰레드 버전 사용")
        self._start_multithreaded_game_monitoring(streak_data)
    
    # 🧵 워커 시그널 처리 메서드들
    def _on_game_state_updated(self, game_state: dict):
        """게임 상태 업데이트 처리 (메인 쓰레드)"""
        try:
            current_round = game_state.get('round', 0)
            
            # 게임 카운트 업데이트
            if current_round > self.tm.game_count:
                self.tm.game_count = current_round
                
            # UI 업데이트 (메인 쓰레드에서 안전)
            if hasattr(self.tm.main_window, 'update_game_status'):
                self.tm.main_window.update_game_status(game_state)
                
        except Exception as e:
            self.logger.error(f"게임 상태 업데이트 처리 오류: {e}")
    
    def _on_betting_requested(self, pick: str, current_round: int, betting_round: int):
        """베팅 요청 처리 (메인 쓰레드)"""
        try:
            self.logger.info(f"🎯 베팅 요청 수신: {pick} (라운드: {current_round} → {betting_round})")
            
            # 비동기 베팅 실행
            success = self.betting_manager.request_betting(pick, current_round, betting_round)
            
            if success:
                self.logger.info(f"✅ 베팅 요청 접수: {pick}")
                # 🔥 중요: 베팅 요청만 접수한 상태, 실제 베팅 성공은 betting_completed 시그널로 처리됨
            else:
                self.logger.warning(f"❌ 베팅 요청 실패: {pick}")
                # 요청 자체가 실패한 경우에만 워커에게 알림
                self.game_monitoring_worker.on_betting_completed(False, f"베팅 요청 실패: {pick}")
                
        except Exception as e:
            self.logger.error(f"베팅 요청 처리 오류: {e}")
    
    def _on_game_result_received(self, result_data: dict):
        """게임 결과 수신 처리 (메인 쓰레드)"""
        try:
            self.logger.info(f"🎲 [RoomEntryHandler] 게임 결과 수신: 라운드 {result_data.get('round_number')}, 결과 {result_data.get('latest_result')}")
            if hasattr(self.tm, 'game_processor'):
                self.tm.game_processor._handle_game_result(result_data)
            else:
                self.logger.error("게임 프로세서가 없음 - 결과 처리 불가")
                
        except Exception as e:
            self.logger.error(f"게임 결과 처리 오류: {e}")
    
    def _on_room_exit_requested(self, reason: str):
        """방 나가기 요청 처리 (메인 쓰레드)"""
        try:
            self.logger.info(f"🚪 방 나가기 요청: {reason}")
            self.handle_room_exit()
            
        except Exception as e:
            self.logger.error(f"방 나가기 처리 오류: {e}")
    
    def _on_worker_error(self, error_message: str):
        """워커 오류 처리 (메인 쓰레드)"""
        self.logger.error(f"🚨 워커 오류: {error_message}")
        
        # UI 오류 표시
        if hasattr(self.tm.main_window, 'show_error'):
            self.tm.main_window.show_error(f"게임 모니터링 오류: {error_message}")
    
    def _on_status_updated(self, status: str):
        """상태 업데이트 처리 (메인 쓰레드)"""
        self.logger.debug(f"📊 상태 업데이트: {status}")
        
        # UI 상태 표시
        if hasattr(self.tm.main_window, 'update_status'):
            self.tm.main_window.update_status(status)

    def _monitor_game_from_iframe(self):
        """iframe에서 게임 상태 모니터링 및 베팅 처리"""
        try:
            if not self.tm.is_trading_active or not self.tm.current_target_room:
                self._stop_iframe_monitoring()
                return
            
            # 🔥 현재 타겟 방 정보에서 가져오기
            streak_data = self.tm.current_target_room
            if not streak_data:
                self.logger.debug("현재 타겟 방 정보 없음 - iframe 모니터링 중지")
                self._stop_iframe_monitoring()
                return
                
            room_id = streak_data.get('room_id', '')
            room_name = streak_data.get('room_name', '')
            
            # ⚡ iframe에서 현재 게임 상태 가져오기 (최소 데이터로 빠르게)
            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=room_name,
                log_always=False,
                desired_pb_count=5  # 15 → 5로 단축하여 속도 향상
            )
            
            if not game_state:
                return
            
            current_round = game_state.get('round', 0)
            current_game = game_state.get('current_game', 0)  # 🔥 현재 진행 중인 게임 번호
            latest_result = game_state.get('latest_result', '')
            filtered_results = game_state.get('filtered_results', [])
            
            # 게임수 0 초기화 감지 및 처리
            if hasattr(self.tm, 'game_count') and self.tm.game_count > 0 and current_round == 0:
                self.logger.warning(f"🚨 게임수 초기화 감지 - 방 나가기")
                
                # 방 로그에 기록
                if hasattr(self.tm.main_window, 'room_log_widget'):
                    self.tm.main_window.room_log_widget.add_bet_result(room_name, False, False)
                
                # 방 나가기 처리
                self.tm.streak_handler.return_to_streak_monitoring()
                return
            
            # 새로운 라운드 감지
            if current_round > self.tm.game_count:
                # 게임 결과 처리
                if latest_result and latest_result in ['P', 'B', 'T']:
                    game_data = {
                        'round_number': current_round,
                        'latest_result': latest_result,
                        'current_game': current_game
                    }
                    
                    if hasattr(self.tm, 'game_processor'):
                        self.tm.game_processor._handle_game_result(game_data)
                
                # 게임 카운트 업데이트
                self.tm.game_count = current_round
                
                # ⚡ 베팅 기회 확인 (게임 상태 캐시 전달로 속도 최적화)
                if not self.tm.betting_service.has_bet_current_round:
                    self._check_betting_opportunity_fast(filtered_results, room_id, current_round, current_game, game_state)
                    
        except Exception as e:
            self.logger.error(f"iframe 모니터링 오류: {e}")

    def _check_betting_opportunity_fast(self, filtered_results: list, room_id: str, current_round: int, current_game: int = None, cached_game_state: dict = None):
        """⚡ 고속 베팅 기회 확인 - 캐시 활용으로 최대 성능 최적화"""
        try:
            # ⚡ 빠른 사전 검증 (디버그 로그 추가)
            if len(filtered_results) < 10:
                self.logger.debug(f"📊⚡ 결과 데이터 부족: {len(filtered_results)}개 (10개 필요)")
                return
            
            if not self.tm.current_target_room or self.tm.current_target_room.get('room_id') != room_id:
                self.logger.debug("🏠⚡ 타겟 방 불일치 또는 없음")
                return
                
            if hasattr(self.tm, 'first_bet_after_entry') and self.tm.first_bet_after_entry:
                self.tm.first_bet_after_entry = False
                self.logger.info("🏠⚡ 방 입장 직후 첫 베팅 - 다음 라운드까지 대기")
                return
            
            # ⚡ 1. 베팅 가능 상태 확인 (캐시 우선 사용)
            if not cached_game_state or cached_game_state.get('current_game', 0) <= 0:
                self.logger.debug("🎮⚡ 베팅 불가능 상태 - 게임 진행 중 아님")
                return
                
            # ⚡ 2. 베팅 서비스 상태 확인
            if hasattr(self.tm.betting_service, 'has_bet_current_round') and self.tm.betting_service.has_bet_current_round:
                self.logger.debug("🎯⚡ 이미 현재 라운드에 베팅함")
                return
                
            # ⚡ 3. 서버 예측값 요청 (병렬 처리 가능하도록 타이밍 최적화)
            start_time = time.time()
            self.logger.info(f"🔮⚡ 고속 서버 예측값 요청 시작:")
            self.logger.info(f"  - 방 ID: {room_id}")
            self.logger.info(f"  - 결과 개수: {len(filtered_results)}개")
            self.logger.info(f"  - 최근 결과: {filtered_results[-10:] if len(filtered_results) >= 10 else filtered_results}")
            
            next_pick = self.tm.server_client.get_next_prediction(room_id, filtered_results)
            request_time = time.time() - start_time
            
            self.logger.info(f"🔮⚡ 고속 서버 예측값 응답: {next_pick} ({request_time:.2f}초)")
            
            if next_pick in ['P', 'B']:
                betting_round = current_game if current_game else current_round
                
                # ⚡ 4. 즉시 베팅 실행 (대기 시간 제거)
                self.logger.info(f"🎯⚡ 베팅 실행: {next_pick} (라운드: {current_round} → {betting_round})")
                self.tm.betting_executor.execute_betting(next_pick, current_round, betting_round)
                
                total_time = time.time() - start_time
                self.logger.info(f"⚡ 고속 베팅 완료: {total_time:.2f}초 (서버요청: {request_time:.2f}초)")
            else:
                self.logger.info(f"🚫⚡ 베팅 안함: 예측값={next_pick}")
                
        except Exception as e:
            self.logger.error(f"고속 베팅 기회 확인 오류: {e}")

    def _check_betting_opportunity(self, filtered_results: list, room_id: str, current_round: int, current_game: int = None, cached_game_state: dict = None):
        """베팅 기회 확인 및 실행 - 속도 최적화"""
        try:
            # ⚡ 빠른 사전 검증
            if len(filtered_results) < 10:
                return
            
            if not self.tm.current_target_room or self.tm.current_target_room.get('room_id') != room_id:
                return
                
            if hasattr(self.tm, 'first_bet_after_entry') and self.tm.first_bet_after_entry:
                self.tm.first_bet_after_entry = False
                return
            
            # ⚡ 1. 베팅 가능 상태 확인 (캐시 활용)
            if not self._check_betting_available_state(room_id, cached_game_state):
                return
                
            # ⚡ 2. 결과값 확인 (캐시 우선 사용)
            updated_results = self._get_latest_iframe_results(room_id, cached_game_state)
            if not updated_results or len(updated_results) < 10:
                return
                
            # ⚡ 3. 서버 예측값 요청 (병렬 처리 가능하도록 타이밍 최적화)
            start_time = time.time()
            next_pick = self.tm.server_client.get_next_prediction(room_id, updated_results)
            request_time = time.time() - start_time
            
            if next_pick in ['P', 'B']:
                betting_round = current_game if current_game else current_round
                
                # ⚡ 4. 즉시 베팅 실행
                self.tm.betting_executor.execute_betting(next_pick, current_round, betting_round)
                
                total_time = time.time() - start_time
                self.logger.info(f"⚡ 베팅 프로세스 완료: {total_time:.2f}초 (서버요청: {request_time:.2f}초)")
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")

    def _check_betting_available_state(self, room_id: str, cached_game_state: dict = None) -> bool:
        """베팅 가능 상태 확인 - 캐시된 게임 상태 활용으로 속도 최적화"""
        try:
            # 캐시된 상태가 있으면 사용 (iframe 재호출 방지)
            if cached_game_state:
                current_game = cached_game_state.get('current_game', 0)
                if current_game > 0:
                    return True
                else:
                    return False
            
            # 캐시가 없는 경우에만 iframe 호출 (최소 데이터로 빠르게)
            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=self.tm.current_room_name,
                log_always=False,
                desired_pb_count=3  # 최소한으로 줄임
            )
            
            if not game_state:
                return False
            
            current_game = game_state.get('current_game', 0)
            return current_game > 0
                
        except Exception as e:
            self.logger.error(f"베팅 가능 상태 확인 오류: {e}")
            return False

    def _get_latest_iframe_results(self, room_id: str, cached_game_state: dict = None) -> list:
        """최신 iframe 결과값 가져오기 - 캐시 활용으로 속도 최적화"""
        try:
            # 캐시된 상태가 있으면 사용 (중복 iframe 호출 방지)
            if cached_game_state:
                filtered_results = cached_game_state.get('filtered_results', [])
                if len(filtered_results) >= 10:  # 충분한 데이터가 있으면 바로 사용
                    return filtered_results
            
            # 캐시가 불충분한 경우에만 iframe 재호출
            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=self.tm.current_room_name,
                log_always=False,
                desired_pb_count=15
            )
            
            if game_state:
                filtered_results = game_state.get('filtered_results', [])
                return filtered_results
            
            return []
            
        except Exception as e:
            self.logger.error(f"최신 결과값 가져오기 오류: {e}")
            return []

    def _handle_martin_limit_reached(self):
        """마틴 한계 도달 처리"""
        try:
            # iframe 모니터링 중지
            self._stop_iframe_monitoring()
            
            # 방 나가기
            self.tm.game_monitoring_service.close_current_room()
            
            # 상태 초기화
            self.tm.current_target_room = None
            self.tm.current_room_name = ""
            
            # 웹소켓 모니터링 재개
            self._resume_websocket_monitoring()
            
            # 연패 모니터링 모드로 복귀
            self.tm.streak_handler.return_to_streak_monitoring()
            
        except Exception as e:
            self.logger.error(f"마틴 한계 처리 오류: {e}")

    def _stop_iframe_monitoring(self):
        """iframe 모니터링 중지"""
        try:
            if hasattr(self, 'iframe_timer') and self.iframe_timer:
                self.iframe_timer.stop()
                self.iframe_timer.deleteLater()
                self.iframe_timer = None
                
            # 추가 안전장치 - 현재 타겟 방 정보도 클리어
            if hasattr(self.tm, 'current_target_room'):
                self.tm.current_target_room = None
                
        except Exception as e:
            self.logger.error(f"iframe 모니터링 중지 오류: {e}")

    def _check_game_count_condition(self, room_id: str, room_name: str) -> bool:
        """게임 수 조건 확인 (15게임 이상 65게임 미만)"""
        try:
            # iframe에서 현재 게임 상태 가져오기
            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=room_name,
                log_always=False,
                desired_pb_count=15
            )
            
            if not game_state:
                return False
            
            # 게임 수 확인
            total_results = game_state.get('total_results', 0)
            current_round = game_state.get('round', 0)
            game_count = current_round if current_round > 0 else total_results
            
            # 조건 체크: 15게임 이상 65게임 미만
            if game_count < 15 or game_count >= 65:
                self.logger.info(f"📊 게임 수 조건 미충족: {game_count}회")
                return False
            else:
                self.logger.info(f"📊 게임 수 조건 충족: {game_count}회")
                return True
                
        except Exception as e:
            self.logger.error(f"게임 수 조건 확인 오류: {e}")
            return False
    
    def _verify_room_entry_success(self, room_id: str, room_name: str, attempt: int) -> bool:
        """iframe 값 체크로 실제 방 입장 성공 여부 확인"""
        try:
            # iframe에서 현재 게임 상태 가져오기 (3번 시도)
            for verification_attempt in range(1, 4):
                game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                    room_id=room_id,
                    room_name=room_name,
                    log_always=False,
                    desired_pb_count=5
                )
                
                if game_state:
                    return True
                
                # 다음 시도 전 잠시 대기 (비동기)
                if verification_attempt < 3:
                    # 동기적 대기 유지 (검증 로직의 단순성을 위해)
                    time.sleep(1)
            
            return False
            
        except Exception as e:
            self.logger.error(f"방 입장 검증 오류: {e}")
            return False
    
    def _handle_room_entry_final_failure(self, room_id: str):
        """모든 재시도 실패 후 웹소켓 데이터 재체크 로직"""
        try:
            self.logger.info("🔄 웹소켓 모니터링으로 복귀")
            
            # 1. 실패한 방을 제외 리스트에 추가 (10분간)
            if room_id:
                self.tm.excluded_rooms[room_id] = {
                    'timestamp': time.time(),
                    'reason': 'entry_fail'
                }
            
            # 2. 웹소켓 연결 상태 체크 및 복구
            self._ensure_websocket_connection()
            
            # 3. 상태 초기화 및 웹소켓 재개
            self._resume_websocket_monitoring()
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False
            self.tm.current_target_room = None
            self.tm.current_room_name = ""
            
            # 4. 연패 모니터링 재시작
            self.tm.streak_handler.return_to_streak_monitoring()
            
        except Exception as e:
            self.logger.error(f"방 입장 실패 처리 오류: {e}")
            try:
                self.tm.streak_handler.start_streak_monitoring()
            except Exception as recovery_error:
                self.logger.error(f"복구 처리 실패: {recovery_error}")

    def _ensure_websocket_connection(self):
        """웹소켓 연결 상태 확인 및 복구"""
        try:
            if hasattr(self.tm, 'websocket_manager') and self.tm.websocket_manager:
                ws_status = self.tm.websocket_manager.get_interceptor_status()
                
                if not ws_status.get('is_intercepting', False) or not ws_status.get('cdp_session_active', False):
                    self.logger.warning("⚠️ 웹소켓 재연결 시도")
                    success = self.tm.websocket_manager.force_reconnect_websocket()
                    
                    if success:
                        self.logger.info("✅ 웹소켓 재연결 성공")
                    else:
                        self.logger.error("❌ 웹소켓 재연결 실패")
                
        except Exception as e:
            self.logger.error(f"웹소켓 연결 확인 오류: {e}")

    def _fallback_room_entry(self, room_name: str) -> bool:
        """폴백 방 입장 로직 (비동기 대기)"""
        try:
            self.logger.info(f"폴백 방 입장 시도: {room_name}")
            # 폴백은 단순하므로 즉시 성공 반환
            return True
        except Exception as e:
            self.logger.error(f"폴백 방 입장 오류: {e}")
            return False

    def start_game_monitoring_in_room(self, streak_data: dict):
        """방 입장 후 게임 모니터링 시작 (기존 호환성)"""
        try:
            room_name = streak_data.get('room_name', '')
            self.logger.info(f"🎮 게임 모니터링 시작: {room_name}")
            
            # 게임 상태 초기화
            self.tm.game_count = 0
            self.tm.result_count = 0
            self.tm.wait_first_result = True
            self.tm.processed_rounds = set()
            
            # 현재 타겟 방 설정
            self.tm.current_target_room = streak_data
            
            self.logger.info(f"✅ 게임 모니터링 준비 완료: {room_name}")
            
        except Exception as e:
            self.logger.error(f"게임 모니터링 시작 오류: {e}")

    def handle_room_exit(self):
        """🧵 멀티쓰레드 방 나가기 처리"""
        try:
            self.logger.info("🚪 방 나가기 처리 시작")
            
            # 🧵 게임 모니터링 워커 중지
            self.game_monitoring_worker.stop_monitoring()
            
            # 🧵 베팅 매니저 정리
            self.betting_manager.cleanup()
            
            # 기존 iframe 모니터링 중지 (호환성)
            self._stop_iframe_monitoring()
            
            # 현재 방에서 나가기
            if hasattr(self.tm, 'game_monitoring_service'):
                self.tm.game_monitoring_service.close_current_room()
            
            # 상태 초기화
            self.tm.current_target_room = None
            self.tm.current_room_name = ""
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False
            
            # 웹소켓 모니터링 재개
            self._resume_websocket_monitoring()
            
            # 방 나가기 완료 시그널 발송
            self.room_exited.emit("정상 종료")
            
            self.logger.info("✅ 멀티쓰레드 방 나가기 완료")
            
        except Exception as e:
            self.logger.error(f"방 나가기 처리 오류: {e}")
            self.room_exited.emit(f"오류: {e}")

    def debug_current_room_status(self):
        """현재 방 상태 디버그"""
        try:
            self.logger.info("=" * 50)
            self.logger.info("현재 방 상태")
            self.logger.info(f"현재 방: {self.tm.current_room_name}")
            self.logger.info(f"게임 카운트: {self.tm.game_count}")
            self.logger.info(f"iframe 모니터링: {'활성' if self.iframe_timer else '비활성'}")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"방 상태 디버그 오류: {e}")