# utils/trading_manager_modules/game_processor.py (베팅 결과 추적기 통합 버전)
import logging
import time
from utils.betting_result_tracker import BettingResultTracker, BettingResult

# utils/trading_manager_modules/game_processor.py 수정 (무한루프 방지)

class GameProcessor:
    """무한루프 방지가 추가된 GameProcessor"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger
        
        # 베팅 결과 추적기 초기화
        from utils.betting_result_tracker import BettingResultTracker
        self.betting_tracker = BettingResultTracker(logger=self.logger)
        
        # 무한루프 방지 변수들
        self.last_betting_request_time = 0  # 마지막 베팅 요청 시간
        self.betting_request_cooldown = 3   # 베팅 요청 쿨다운 (초)

    def _process_current_room_game_data(self, game_data: dict):
        """현재 방의 게임 데이터 처리 - 무한루프 방지 추가"""
        try:
            round_number = game_data.get('round_number', 0)
            latest_result = game_data.get('latest_result', '')
            
            # 게임 카운트 업데이트
            if round_number > self.tm.game_count:
                self.tm.game_count = round_number
            
            # 새로운 결과가 있는 경우 처리
            if latest_result and latest_result in ['P', 'B', 'T']:
                self._handle_game_result(game_data)
            
            # 🔥 핵심 수정: 베팅 결과 추적기로 결과 확인 (우선순위 1)
            if self.betting_tracker.is_waiting_for_result():
                self.logger.info(f"⏳ 베팅 결과 대기 중... (라운드 {self.betting_tracker.get_bet_round()} 결과 기다림)")
                self._check_betting_result_with_tracker(game_data)
                return  # 베팅 결과 대기 중이면 새로운 베팅 시도하지 않음
            
            # 🔥 베팅 기회 확인 (베팅 결과 대기 중이 아닐 때만)
            if self.tm.current_target_room and not self.tm.room_entry_in_progress:
                # 쿨다운 체크
                current_time = time.time()
                if current_time - self.last_betting_request_time >= self.betting_request_cooldown:
                    self._check_betting_opportunity(game_data)
                else:
                    remaining_cooldown = self.betting_request_cooldown - (current_time - self.last_betting_request_time)
                    self.logger.debug(f"⏳ 베팅 요청 쿨다운 중... (남은 시간: {remaining_cooldown:.1f}초)")
            
        except Exception as e:
            self.logger.error(f"현재 방 게임 데이터 처리 오류: {e}")

    def _check_betting_result_with_tracker(self, game_data: dict):
        """베팅 결과 추적기를 통한 결과 확인"""
        try:
            round_number = game_data.get('round_number', 0)
            latest_result = game_data.get('latest_result', '')
            
            # 베팅한 라운드보다 큰 라운드의 결과가 와야 함
            bet_round = self.betting_tracker.get_bet_round()
            if not bet_round or round_number <= bet_round:
                self.logger.debug(f"⏳ 베팅 라운드({bet_round}) 결과 대기 중... 현재 라운드: {round_number}")
                return
            
            # 결과가 있는 경우에만 확인
            if not latest_result or latest_result not in ['P', 'B', 'T']:
                self.logger.debug(f"⏳ 유효한 게임 결과 대기 중... 현재 결과: {latest_result}")
                return
            
            # 베팅 결과 확인
            betting_result = self.betting_tracker.check_result(round_number, latest_result)
            
            if betting_result:
                self.logger.info(f"🎲 베팅 결과 확정: {betting_result.value}")
                
                # 결과에 따른 처리
                if betting_result.value == 'tie':
                    self._handle_tie_result_tracked()
                elif betting_result.value == 'win':
                    self._handle_win_result_tracked()
                elif betting_result.value == 'lose':
                    self._handle_lose_result_tracked()
                
        except Exception as e:
            self.logger.error(f"베팅 결과 추적 확인 오류: {e}")

    def _check_betting_opportunity(self, game_data: dict):
        """베팅 기회 확인 - 중복 체크 강화"""
        try:
            # 🔥 중복 베팅 방지: 베팅 추적기 상태 재확인
            if self.betting_tracker.is_waiting_for_result():
                self.logger.info("⏳ 베팅 추적기가 결과 대기 중 - 새 베팅 차단")
                return
            
            # 기존 베팅 서비스 상태 확인
            if hasattr(self.tm.betting_service, 'has_bet_current_round') and self.tm.betting_service.has_bet_current_round:
                self.logger.info("⏳ 베팅 서비스가 이미 베팅 상태 - 새 베팅 차단")
                return
            
            # 첫 결과 대기 중이면서 새로운 결과가 왔을 때만 대기 해제
            if self.tm.wait_first_result:
                latest_result = game_data.get('latest_result')
                if latest_result and latest_result in ['P', 'B', 'T']:
                    self.tm.wait_first_result = False
                    self.logger.info(f"첫 결과 수신 - 대기 모드 해제: {latest_result}")
                    
                    # 타이가 아닌 경우에만 다음 베팅 진행 (쿨다운 적용)
                    if latest_result in ['P', 'B']:
                        self.last_betting_request_time = time.time()
                        self._process_game_result_and_bet(game_data)
                return
            
            # 현재 타겟 방이 없으면 베팅 안함
            if not self.tm.current_target_room:
                return
            
            # 🔥 베팅 요청 시간 기록 (무한루프 방지)
            self.last_betting_request_time = time.time()
            
            # 베팅 가능한 상태에서 최신 데이터로 예측값 요청
            self._request_betting_with_latest_data()
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")

    def _execute_betting_with_tracking(self, pick: str, round_number: int):
        """베팅 실행 및 추적기 연동 - 중복 방지 강화"""
        try:
            # 🔥 베팅 실행 전 최종 상태 확인
            if self.betting_tracker.is_waiting_for_result():
                self.logger.warning("⚠️ 이미 베팅 결과 대기 중 - 베팅 실행 중단")
                return
            
            if hasattr(self.tm.betting_service, 'has_bet_current_round') and self.tm.betting_service.has_bet_current_round:
                self.logger.warning("⚠️ 베팅 서비스가 이미 베팅 상태 - 베팅 실행 중단")
                return
            
            # 베팅 금액 계산
            from utils.trading_manager_helpers import get_widget_position
            widget_pos = get_widget_position(self.tm.main_window)
            bet_amount = self.tm.excel_trading_service.get_current_bet_amount(widget_position=widget_pos)
            
            # 🔥 베팅 추적 시작 (베팅 실행 전에 먼저 시작)
            if not self.betting_tracker.start_betting_tracking(
                bet_type=pick,
                round_number=round_number,
                bet_amount=bet_amount,
                room_name=self.tm.current_room_name
            ):
                self.logger.error("❌ 베팅 추적 시작 실패 - 베팅 중단")
                return
            
            # 베팅 실행
            bet_success = self.tm.betting_service.place_bet(
                pick,
                self.tm.current_room_name,
                round_number,
                self.tm.is_trading_active,
                bet_amount
            )
            
            if bet_success:
                self.logger.info(f"✅ 베팅 성공: {pick}, 금액: {bet_amount:,}원, 라운드: {round_number}")
                self.logger.info(f"⏳ 베팅 결과 대기 시작... (라운드 {round_number} → 다음 라운드 결과 기다림)")
                
                # UI 업데이트
                self.tm.main_window.update_betting_status(
                    pick=pick, 
                    bet_amount=bet_amount,
                    status=f"베팅 완료 - 결과 대기 중"
                )
            else:
                self.logger.warning(f"❌ 베팅 실패: {pick}")
                # 베팅 실패 시 추적 초기화
                self.betting_tracker.reset_tracking()
                
        except Exception as e:
            self.logger.error(f"베팅 실행 오류: {e}")
            # 오류 발생 시 추적 초기화
            self.betting_tracker.reset_tracking()

    def _handle_tie_result_tracked(self):
        """무승부 결과 처리 - 추적기 기반"""
        try:
            self.logger.info("🤝 무승부 - 동일한 픽으로 재베팅")
            
            # 베팅 상태 초기화
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.has_bet_current_round = False
            self.tm.had_tie_last_round = True
            
            # 🔥 베팅 추적기 초기화 (재베팅을 위해)
            previous_bet_type = self.betting_tracker.get_bet_type()
            self.betting_tracker.reset_tracking()
            
            # 잠시 대기 후 동일한 픽으로 재베팅
            time.sleep(2)
            if previous_bet_type:
                next_round = self.tm.game_count + 1
                self.logger.info(f"🔄 무승부 후 재베팅: {previous_bet_type} (라운드 {next_round})")
                self._execute_betting_with_tracking(previous_bet_type, next_round)
            
        except Exception as e:
            self.logger.error(f"무승부 처리 오류: {e}")

    def _handle_win_result_tracked(self):
        """승리 결과 처리 - 추적기 기반"""
        try:
            self.logger.info("🎉 베팅 승리! 방 나가기 및 새로운 방 검색")
            
            # 승률 및 수익 정보 로깅
            win_rate = self.betting_tracker.get_win_rate(10)
            total_profit = self.betting_tracker.get_total_profit_loss(10)
            self.logger.info(f"📊 성과: 최근 10게임 승률 {win_rate}%, 수익 {total_profit:,}원")
            
            # 위젯 승리 마커 표시
            if hasattr(self.tm.main_window, 'betting_widget'):
                from utils.trading_manager_helpers import get_widget_position
                current_pos = get_widget_position(self.tm.main_window)
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "O")
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.tm.main_window.betting_widget.reset_step_markers()
            
            # 마틴 서비스 및 시스템 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset()
            
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.record_betting_result(True)
            
            # 🔥 베팅 추적기 초기화
            self.betting_tracker.reset_tracking()
            
            # 베팅 서비스 상태 초기화
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.has_bet_current_round = False
                self.tm.betting_service.reset_betting_state()
            
            # 현재 방에서 나가기
            self._exit_current_room()
            
            # 새로운 연패 방 검색 모드로 전환
            self.tm.streak_handler.return_to_streak_monitoring()
            
        except Exception as e:
            self.logger.error(f"승리 처리 오류: {e}")

    def _handle_lose_result_tracked(self):
        """패배 결과 처리 - 추적기 기반"""
        try:
            self.logger.info("❌ 베팅 패배 - 마틴 베팅 또는 방 이동 결정")
            
            # 연속 패배 정보 로깅
            consecutive_info = self.betting_tracker.get_consecutive_results()
            consecutive_losses = consecutive_info['consecutive_losses']
            self.logger.info(f"📉 연속 패배: {consecutive_losses}회")
            
            # 위젯 패배 마커 표시 및 카운터 증가
            if hasattr(self.tm.main_window, 'betting_widget'):
                from utils.trading_manager_helpers import get_widget_position
                current_pos = get_widget_position(self.tm.main_window)
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "X")
                self.tm.main_window.betting_widget.room_position_counter = current_pos + 1
            
            # 시스템에 패배 기록
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.record_betting_result(False)
            
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.record_loss()
            
            # 🔥 베팅 추적기 초기화 (다음 베팅을 위해)
            self.betting_tracker.reset_tracking()
            
            # 베팅 서비스 상태 초기화
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.has_bet_current_round = False
            
            # 방 이동 여부 결정
            if self.betting_tracker.should_change_room(max_consecutive_losses=3):
                self.logger.info("🔄 연패 한계 도달 - 새로운 방 검색")
                self._exit_current_room()
                self.tm.streak_handler.return_to_streak_monitoring()
            else:
                # 마틴 베팅 진행
                self.logger.info("📈 마틴 베팅 진행")
                time.sleep(2)  # 잠시 대기 후 마틴 베팅
                self._execute_martin_betting()
            
        except Exception as e:
            self.logger.error(f"패배 처리 오류: {e}")

    def _execute_martin_betting(self):
        """마틴 베팅 실행"""
        try:
            # 🔥 마틴 베팅 실행 전 상태 확인
            if self.betting_tracker.is_waiting_for_result():
                self.logger.warning("⚠️ 이미 베팅 결과 대기 중 - 마틴 베팅 중단")
                return
            
            # 현재 라운드 + 1로 마틴 베팅
            next_round = self.tm.game_count + 1
            
            # 서버에서 새로운 예측값 요청 (마틴 베팅도 최신 데이터 기반)
            room_id = self.tm.current_target_room.get('room_id', '')
            
            # 최신 게임 상태 가져오기
            latest_game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=self.tm.current_room_name,
                log_always=True,
                desired_pb_count=15
            )
            
            if latest_game_state:
                current_results = latest_game_state.get('filtered_results', [])
                if len(current_results) >= 5:
                    # 서버에서 마틴 베팅용 예측값 요청
                    martin_pick = self.tm.server_client.get_next_prediction(room_id, current_results)
                    
                    if martin_pick in ['P', 'B']:
                        self.logger.info(f"📈 마틴 베팅: {martin_pick}")
                        self._execute_betting_with_tracking(martin_pick, next_round)
                        return
            
            # 서버 예측 실패 시 기본 픽으로 마틴 베팅
            self.logger.info("📈 마틴 베팅 (기본 픽): P")
            self._execute_betting_with_tracking('P', next_round)
            
        except Exception as e:
            self.logger.error(f"마틴 베팅 실행 오류: {e}")

    def _exit_current_room(self):
        """현재 방에서 나가기"""
        try:
            self.logger.info("🚪 현재 방에서 나가기")
            
            if hasattr(self.tm, 'game_monitoring_service'):
                self.tm.game_monitoring_service.close_current_room()
            
            # 방 관련 상태 초기화
            self.tm.current_room_name = ""
            self.tm.current_target_room = None
            self.tm.game_count = 0
            self.tm.result_count = 0
            
            # 🔥 베팅 추적기 초기화
            self.betting_tracker.reset_tracking()
            
            # 베팅 서비스 상태 초기화
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.has_bet_current_round = False
                self.tm.betting_service.reset_betting_state()
            
            # 쿨다운 초기화
            self.last_betting_request_time = 0
            
        except Exception as e:
            self.logger.error(f"방 나가기 오류: {e}")

    def get_betting_loop_status(self):
        """베팅 루프 상태 디버그 정보"""
        try:
            current_time = time.time()
            cooldown_remaining = max(0, self.betting_request_cooldown - (current_time - self.last_betting_request_time))
            
            return {
                'betting_tracker_waiting': self.betting_tracker.is_waiting_for_result(),
                'betting_service_has_bet': getattr(self.tm.betting_service, 'has_bet_current_round', False) if hasattr(self.tm, 'betting_service') else False,
                'last_betting_request_time': self.last_betting_request_time,
                'cooldown_remaining': cooldown_remaining,
                'wait_first_result': getattr(self.tm, 'wait_first_result', False),
                'current_target_room': self.tm.current_target_room is not None,
                'room_entry_in_progress': getattr(self.tm, 'room_entry_in_progress', False)
            }
        except Exception as e:
            self.logger.error(f"베팅 루프 상태 확인 오류: {e}")
            return {'error': str(e)}

    def debug_betting_loop_prevention(self):
        """베팅 무한루프 방지 상태 디버그"""
        try:
            status = self.get_betting_loop_status()
            self.logger.info("🔍 베팅 무한루프 방지 상태:")
            for key, value in status.items():
                self.logger.info(f"  - {key}: {value}")
        except Exception as e:
            self.logger.error(f"베팅 루프 방지 디버그 오류: {e}")