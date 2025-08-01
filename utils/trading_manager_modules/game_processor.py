# utils/trading_manager_modules/game_processor.py
import logging
import time
from PyQt6.QtCore import QTimer
from utils.betting_result_tracker import BettingResultTracker, BettingResult


class GameProcessor:
    """게임 데이터 처리 전담 클래스 - 베팅 결과 추적 통합"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger
        
        # 베팅 결과 추적기 초기화
        self.betting_tracker = BettingResultTracker(logger=self.logger)
        
        # 무한루프 방지를 위한 상태 변수들
        self.is_processing_result = False
        self.last_processed_time = 0
        self.min_process_interval = 2.0  # 최소 처리 간격 (초)
        self.last_request_time = 0
        self.min_request_interval = 5.0  # 최소 요청 간격 (초)
        self.consecutive_requests = 0
        self.max_consecutive_requests = 3  # 최대 연속 요청 수
        
        # 베팅 관련 상태 추적
        self.last_bet_round = 0
        self.betting_cooldown = False
        
        # 타이머를 통한 비동기 처리
        self.betting_timer = None

    def on_game_data_received(self, game_data: dict):
        """게임 데이터 수신 처리 - 연패 모니터링 모드에서만 작동"""
        try:
            # 현재 방에 있으면 웹소켓 데이터 무시
            if self.tm.current_target_room or self.tm.room_entry_in_progress:
                return
                
            current_time = time.time()
            
            # 너무 빠른 연속 처리 방지
            if current_time - self.last_processed_time < self.min_process_interval:
                return
            
            # 이미 처리 중인 경우 방지
            if self.is_processing_result:
                return
            
            self.is_processing_result = True
            self.last_processed_time = current_time
            
            try:
                self.tm.last_game_data = game_data
                self.tm.message_count += 1
                
            finally:
                self.is_processing_result = False
                
        except Exception as e:
            self.logger.error(f"게임 데이터 수신 처리 오류: {e}")
            self.is_processing_result = False

    def _process_current_room_game_data(self, game_data: dict):
        """현재 방의 게임 데이터 처리 - 무한루프 방지"""
        try:
            round_number = game_data.get('round_number', 0)
            latest_result = game_data.get('latest_result', '')
            
            # 게임 카운트 업데이트
            if round_number > self.tm.game_count:
                self.tm.game_count = round_number
            
            # 새로운 결과가 있는 경우 처리
            if latest_result and latest_result in ['P', 'B', 'T']:
                self._handle_game_result(game_data)
            
            # 베팅 타이밍 확인 - 쿨다운 적용
            if not self.betting_cooldown and self.tm.current_target_room and not self.tm.room_entry_in_progress:
                self._check_betting_opportunity_with_cooldown(game_data)
            
        except Exception as e:
            self.logger.error(f"현재 방 게임 데이터 처리 오류: {e}")

    def _handle_game_result(self, game_data: dict):
        """게임 결과 처리 - 베팅 결과 추적 통합"""
        try:
            latest_result = game_data.get('latest_result', '')
            round_number = game_data.get('round_number', 0)
            
            # 중복 결과 방지
            result_id = f"{round_number}_{latest_result}"
            if result_id in self.tm.processed_rounds:
                return
            
            self.tm.processed_rounds.add(result_id)
            self.tm.result_count += 1
            
            self.logger.info(f"🎯 새로운 게임 결과: 라운드 {round_number}, 결과 {latest_result}")
            
            # 베팅 결과 추적기로 결과 확인
            if self.betting_tracker.is_waiting_for_result():
                # 베팅한 라운드 확인
                bet_round = self.betting_tracker.get_bet_round()
                
                # 디버깅 로그 추가 - INFO 레벨로 변경
                self.logger.info(f"🔍 베팅 추적: 베팅 라운드={bet_round}, 현재 라운드={round_number}")
                
                # 베팅한 라운드의 결과인지 확인
                if round_number == bet_round:
                    betting_result = self.betting_tracker.check_result(round_number, latest_result)
                    
                    if betting_result:
                        self.logger.info(f"🎲 베팅 결과 확정: {betting_result.value}")
                        
                        # 결과에 따른 처리
                        if betting_result == BettingResult.WIN:
                            self._handle_win_result_tracked()
                        elif betting_result == BettingResult.LOSE:
                            self._handle_lose_result_tracked()
                        elif betting_result == BettingResult.TIE:
                            self._handle_tie_result_tracked()
                        
                        # 베팅 서비스 상태 초기화
                        if hasattr(self.tm.betting_service, 'has_bet_current_round'):
                            self.tm.betting_service.has_bet_current_round = False
                    else:
                        self.logger.info(f"라운드 {round_number}의 결과를 처리하지 않음")
                else:
                    self.logger.info(f"베팅 라운드({bet_round})를 대기 중 - 현재 라운드({round_number})")
            else:
                self.logger.debug("베팅 결과 추적기가 대기 상태가 아님")
            
            # ExcelTradingService에 결과 추가
            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                if latest_result in ['P', 'B']:
                    self.tm.excel_trading_service.choice_pick_system.add_result(latest_result)
                    
        except Exception as e:
            self.logger.error(f"게임 결과 처리 오류: {e}")

    def _check_betting_opportunity_with_cooldown(self, game_data: dict):
        """베팅 기회 확인 - 쿨다운 적용으로 무한루프 방지"""
        try:
            current_time = time.time()
            
            # 요청 간격 체크
            if current_time - self.last_request_time < self.min_request_interval:
                return
            
            # 연속 요청 수 체크
            if self.consecutive_requests >= self.max_consecutive_requests:
                self.logger.info(f"최대 연속 요청 수 도달 - 대기")
                QTimer.singleShot(5000, self._reset_request_counter)
                return
            
            # 이미 베팅했으면 베팅 안함
            if hasattr(self.tm.betting_service, 'has_bet_current_round') and self.tm.betting_service.has_bet_current_round:
                return
            
            # 베팅 추적기가 결과 대기 중이면 베팅 안함
            if self.betting_tracker.is_waiting_for_result():
                return
            
            # 첫 결과 대기 중 처리
            if self.tm.wait_first_result:
                latest_result = game_data.get('latest_result')
                if latest_result and latest_result in ['P', 'B', 'T']:
                    self.tm.wait_first_result = False
                    self.logger.info(f"첫 결과 수신 - 대기 모드 해제: {latest_result}")
                    
                    # 타이가 아닌 경우에만 다음 베팅 진행
                    if latest_result in ['P', 'B']:
                        # 베팅 쿨다운 적용
                        self.betting_cooldown = True
                        QTimer.singleShot(3000, self._reset_betting_cooldown)  # 3초 쿨다운
                        self._schedule_delayed_betting(game_data)
                return
            
            # 현재 타겟 방이 없으면 베팅 안함
            if not self.tm.current_target_room:
                return
            
            # 베팅 쿨다운 시작
            self.betting_cooldown = True
            self.last_request_time = current_time
            self.consecutive_requests += 1
            
            # 베팅 처리를 타이머로 지연 실행
            self._schedule_delayed_betting(game_data)
            
            # 쿨다운 해제 타이머
            QTimer.singleShot(8000, self._reset_betting_cooldown)  # 8초 쿨다운
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")
            self.betting_cooldown = False

    def _schedule_delayed_betting(self, game_data: dict):
        """지연된 베팅 스케줄링"""
        try:
            if self.betting_timer:
                self.betting_timer.stop()
                self.betting_timer = None
            
            self.betting_timer = QTimer()
            self.betting_timer.setSingleShot(True)
            self.betting_timer.timeout.connect(lambda: self._execute_delayed_betting(game_data))
            self.betting_timer.start(2000)  # 2초 후 실행
            
        except Exception as e:
            self.logger.error(f"지연 베팅 스케줄링 오류: {e}")

    def _execute_delayed_betting(self, game_data: dict):
        """지연된 베팅 실행"""
        try:
            # 상태 재확인
            if (hasattr(self.tm.betting_service, 'has_bet_current_round') and 
                self.tm.betting_service.has_bet_current_round):
                return
            
            # 베팅 추적기가 결과 대기 중이면 베팅 취소
            if self.betting_tracker.is_waiting_for_result():
                return
                
            if not self.tm.current_target_room:
                return
            
            # 베팅 가능 시점 최신 데이터로 예측값 요청
            self._request_betting_with_latest_data()
            
        except Exception as e:
            self.logger.error(f"지연 베팅 실행 오류: {e}")
        finally:
            if self.betting_timer:
                self.betting_timer = None

    def _reset_betting_cooldown(self):
        """베팅 쿨다운 해제"""
        self.betting_cooldown = False

    def _reset_request_counter(self):
        """요청 카운터 초기화"""
        self.consecutive_requests = 0

    def _request_betting_with_latest_data(self):
        """베팅 가능 상태에서 실시간 최신 데이터로 예측값 요청"""
        try:
            # 중복 요청 방지
            if hasattr(self, '_is_requesting') and self._is_requesting:
                return
                
            self._is_requesting = True
            
            try:
                room_id = self.tm.current_target_room.get('room_id', '')
                room_name = self.tm.current_target_room.get('room_name', '')
                
                self.logger.info(f"🔍 베팅 예측값 요청: {room_name}")
                
                # iframe에서 최신 게임 상태 가져오기
                latest_game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                    room_id=room_id,
                    room_name=room_name,
                    log_always=True,
                    desired_pb_count=15
                )
                
                if not latest_game_state:
                    self.logger.warning("최신 게임 상태를 가져올 수 없습니다")
                    return
                
                # 최신 결과 리스트
                current_results = latest_game_state.get('filtered_results', [])
                
                if len(current_results) < 5:
                    self.logger.info(f"데이터 부족 ({len(current_results)}개) - 베팅 보류")
                    return
                
                # 서버에 예측값 요청
                next_pick = self.tm.server_client.get_next_prediction(room_id, current_results)
                self.logger.info(f"🎯 서버 예측 결과: {next_pick}")
                
                # 유효한 예측값이면 베팅 실행
                if next_pick in ['P', 'B']:
                    # 베팅 라운드 중복 확인
                    round_number = latest_game_state.get('round', self.tm.game_count + 1)
                    
                    if round_number <= self.last_bet_round:
                        return
                    
                    self.last_bet_round = round_number
                    
                    # 잠시 대기 후 베팅
                    time.sleep(1)
                    
                    # 베팅 실행
                    self.tm.betting_executor.execute_betting(next_pick, round_number)
                else:
                    self.logger.info(f"베팅 안함: {next_pick}")
                    
            finally:
                self._is_requesting = False
                
        except Exception as e:
            self.logger.error(f"베팅 예측값 요청 오류: {e}")
            self._is_requesting = False

    def _handle_win_result_tracked(self):
        """승리 결과 처리"""
        try:
            self.logger.info("🎉 베팅 승리!")
            
            # 추적 상태 초기화
            self.betting_tracker.reset_tracking()
            
            # 상태 초기화
            self.betting_cooldown = False
            self.consecutive_requests = 0
            self.last_bet_round = 0
            
            # 위젯 초기화
            if hasattr(self.tm.main_window, 'betting_widget'):
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.tm.main_window.betting_widget.reset_step_markers()
                self.tm.main_window.betting_widget.set_step_marker(0, "O")  # 승리 마커
            
            # 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset()
            
            # Excel Trading Service에 승리 기록
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.record_betting_result(True)
            
            # 현재 방 정보 초기화
            self.tm.current_target_room = None
            self.tm.target_streak_rooms = []
            self.tm.just_won = True
            
            # 새로운 연패 방 검색 모드로 전환
            self.tm.streak_handler.return_to_streak_monitoring()
            
        except Exception as e:
            self.logger.error(f"승리 처리 오류: {e}")

    def _handle_lose_result_tracked(self):
        """패배 결과 처리"""
        try:
            self.logger.info("❌ 베팅 패배")
            
            # 추적 상태 초기화
            self.betting_tracker.reset_tracking()
            
            # 위젯 카운터 증가
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "X")  # 패배 마커
                self.tm.main_window.betting_widget.room_position_counter = current_pos + 1
            
            # Excel Trading Service에 패배 기록
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.record_betting_result(False)
            
            # 연패 확인
            if self.betting_tracker.should_change_room():
                self.logger.info("3연패 감지 - 방 이동")
                # 상태 초기화
                self.betting_cooldown = False
                self.consecutive_requests = 0
                self.last_bet_round = 0
                # 새로운 방 검색
                self.tm.streak_handler.return_to_streak_monitoring()
                
        except Exception as e:
            self.logger.error(f"패배 처리 오류: {e}")

    def _handle_tie_result_tracked(self):
        """무승부 결과 처리"""
        try:
            self.logger.info("🤝 무승부")
            
            # 추적 상태 초기화
            self.betting_tracker.reset_tracking()
            
            # 베팅 상태 초기화
            self.tm.betting_service.has_bet_current_round = False
            self.tm.had_tie_last_round = True
            
            # 타이 후에는 쿨다운 해제
            self.betting_cooldown = False
            
            # 위젯에 타이 마커 표시
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "T")
            
        except Exception as e:
            self.logger.error(f"무승부 처리 오류: {e}")

    # 기존 호환성 메서드들
    def _handle_win_result(self):
        self._handle_win_result_tracked()

    def _handle_lose_result(self):
        self._handle_lose_result_tracked()

    def _handle_tie_result(self):
        self._handle_tie_result_tracked()

    def _check_consecutive_losses(self) -> bool:
        """연패 확인"""
        try:
            if hasattr(self.tm, 'excel_trading_service'):
                return self.tm.excel_trading_service.should_change_room()
            return False
        except Exception as e:
            self.logger.error(f"연패 확인 오류: {e}")
            return False

    def get_betting_statistics(self) -> dict:
        """베팅 통계 정보 반환"""
        try:
            return {
                'total_games': len(self.betting_tracker.betting_history),
                'win_rate_10': self.betting_tracker.get_win_rate(10),
                'win_rate_5': self.betting_tracker.get_win_rate(5),
                'consecutive_results': self.betting_tracker.get_consecutive_results(),
                'total_profit_loss_10': self.betting_tracker.get_total_profit_loss(10),
                'total_profit_loss_5': self.betting_tracker.get_total_profit_loss(5),
                'current_bet_info': self.betting_tracker.get_current_bet_info(),
                'is_waiting_result': self.betting_tracker.is_waiting_for_result()
            }
        except Exception as e:
            self.logger.error(f"베팅 통계 조회 오류: {e}")
            return {}

    def debug_betting_tracker_status(self):
        """베팅 추적기 상태 디버그"""
        try:
            self.betting_tracker.debug_status()
        except Exception as e:
            self.logger.error(f"베팅 추적기 디버그 오류: {e}")

    def cleanup(self):
        """리소스 정리"""
        try:
            if self.betting_timer:
                self.betting_timer.stop()
                self.betting_timer = None
            
            self.is_processing_result = False
            self.betting_cooldown = False
            self.consecutive_requests = 0
            
            # 베팅 추적기 초기화
            self.betting_tracker.reset_tracking()
            
        except Exception as e:
            self.logger.error(f"GameProcessor 정리 오류: {e}")