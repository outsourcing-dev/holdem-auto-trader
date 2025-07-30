# utils/trading_manager_modules/game_processor.py (무한루프 방지 수정)
import logging
import time
from PyQt6.QtCore import QTimer


class GameProcessor:
    """게임 데이터 처리 전담 클래스 - 무한루프 방지 개선"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger
        
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
        """게임 데이터 수신 처리 - 무한루프 방지"""
        try:
            current_time = time.time()
            
            # 너무 빠른 연속 처리 방지
            if current_time - self.last_processed_time < self.min_process_interval:
                self.logger.debug(f"처리 간격 부족 - 무시 ({current_time - self.last_processed_time:.1f}초)")
                return
            
            # 이미 처리 중인 경우 방지
            if self.is_processing_result:
                self.logger.debug("이미 결과 처리 중 - 무시")
                return
            
            self.is_processing_result = True
            self.last_processed_time = current_time
            
            try:
                self.tm.last_game_data = game_data
                self.tm.message_count += 1
                
                # 현재 방과 일치하는 데이터인지 확인
                room_name = game_data.get('room_name', '')
                if self.tm.current_target_room and room_name:
                    target_room_name = self.tm.current_target_room.get('room_name', '')
                    if target_room_name in room_name:
                        # 현재 방의 게임 데이터 처리
                        self._process_current_room_game_data(game_data)
                        
            finally:
                # 처리 완료 후 상태 초기화
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
        """게임 결과 처리 - 중복 방지"""
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
            
            # 베팅 결과 확인
            if (hasattr(self.tm.betting_service, 'has_bet_current_round') and 
                self.tm.betting_service.has_bet_current_round):
                
                last_bet = self.tm.betting_service.get_last_bet()
                
                if last_bet and last_bet['type'] in ['P', 'B']:
                    result_status = self.tm.bet_helper.process_bet_result(
                        last_bet['type'], 
                        latest_result, 
                        round_number
                    )
                    
                    self.logger.info(f"베팅 결과 처리: {result_status}")
                    
                    if result_status == 'win':
                        self.tm.just_won = True
                        self._handle_win_result()
                    elif result_status == 'lose':
                        self._handle_lose_result()
                    elif result_status == 'tie':
                        self._handle_tie_result()
            
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
            
            # 요청 간격 체크 - 너무 자주 요청하지 않도록
            if current_time - self.last_request_time < self.min_request_interval:
                return
            
            # 연속 요청 수 체크
            if self.consecutive_requests >= self.max_consecutive_requests:
                self.logger.info(f"최대 연속 요청 수 도달 - 대기 ({self.consecutive_requests}회)")
                # 5초 후 초기화
                QTimer.singleShot(5000, self._reset_request_counter)
                return
            
            # 이미 베팅했으면 베팅 안함
            if hasattr(self.tm.betting_service, 'has_bet_current_round') and self.tm.betting_service.has_bet_current_round:
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
            
            # 베팅 처리를 타이머로 지연 실행 (무한루프 방지)
            self._schedule_delayed_betting(game_data)
            
            # 쿨다운 해제 타이머
            QTimer.singleShot(8000, self._reset_betting_cooldown)  # 8초 쿨다운
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")
            self.betting_cooldown = False

    def _schedule_delayed_betting(self, game_data: dict):
        """지연된 베팅 스케줄링 - 타이머 사용으로 무한루프 방지"""
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
                self.logger.info("이미 베팅 완료 - 지연 베팅 취소")
                return
                
            if not self.tm.current_target_room:
                self.logger.info("타겟 방 없음 - 지연 베팅 취소")
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
        self.logger.debug("베팅 쿨다운 해제")

    def _reset_request_counter(self):
        """요청 카운터 초기화"""
        self.consecutive_requests = 0
        self.logger.debug("연속 요청 카운터 초기화")

    def _request_betting_with_latest_data(self):
        """베팅 가능 상태에서 실시간 최신 데이터로 예측값 요청 - 개선된 버전"""
        try:
            # 중복 요청 방지
            if hasattr(self, '_is_requesting') and self._is_requesting:
                self.logger.debug("이미 예측값 요청 중 - 무시")
                return
                
            self._is_requesting = True
            
            try:
                room_id = self.tm.current_target_room.get('room_id', '')
                room_name = self.tm.current_target_room.get('room_name', '')
                
                self.logger.info(f"🔍 베팅 가능 상태 - 최신 데이터로 예측값 요청: {room_name}")
                
                # iframe에서 최신 게임 상태 가져오기
                latest_game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                    room_id=room_id,
                    room_name=room_name,
                    log_always=True,
                    desired_pb_count=15
                )
                
                if not latest_game_state:
                    self.logger.warning("❌ 최신 게임 상태를 가져올 수 없습니다")
                    return
                
                # 최신 결과 리스트 (P, B만)
                current_results = latest_game_state.get('filtered_results', [])
                
                if len(current_results) < 5:
                    self.logger.info(f"⏳ 데이터 부족 (현재 {len(current_results)}개) - 베팅 보류")
                    return
                
                self.logger.info(f"📊 베팅 가능 시점 최신 {len(current_results)}개 P,B 결과로 예측 요청: {current_results}")
                
                # 서버에 최신 데이터로 예측값 요청
                next_pick = self.tm.server_client.get_next_prediction(room_id, current_results)
                self.logger.info(f"🎯 [베팅 가능 시점 예측] 서버 예측 결과: {next_pick}")
                
                # 유효한 예측값이면 베팅 실행
                if next_pick in ['P', 'B']:
                    # 베팅 라운드 중복 확인
                    round_number = latest_game_state.get('round', self.tm.game_count + 1)
                    
                    if round_number <= self.last_bet_round:
                        self.logger.info(f"이미 처리된 라운드 - 베팅 생략: {round_number}")
                        return
                    
                    self.last_bet_round = round_number
                    
                    # 잠시 대기 후 베팅 (게임 전환 시간 고려)
                    time.sleep(1)
                    
                    self.logger.info(f"🎯 [베팅 가능 시점 예측] 베팅 실행: {next_pick} (라운드 {round_number}) - 최신 데이터 기반")
                    self.tm.betting_executor.execute_betting(next_pick, round_number)
                else:
                    self.logger.info(f"🎯 [베팅 가능 시점 예측] 베팅 안함: {next_pick}")
                    
            finally:
                self._is_requesting = False
                
        except Exception as e:
            self.logger.error(f"베팅 가능 시점 최신 데이터 요청 오류: {e}")
            self._is_requesting = False

    def _process_game_result_and_bet(self, game_data: dict):
        """게임 결과 처리 후 다음 베팅 실행 - 쿨다운 적용"""
        try:
            latest_result = game_data.get('latest_result')
            
            self.logger.info(f"🎮 게임 결과 처리: {latest_result}")
            
            # 1. 이전 베팅 결과 확인 및 처리
            if hasattr(self.tm.betting_service, 'has_bet_current_round') and self.tm.betting_service.has_bet_current_round:
                last_bet = self.tm.betting_service.get_last_bet()
                if last_bet and last_bet['type'] in ['P', 'B']:
                    # 베팅 결과 처리
                    result_status = self.tm.bet_helper.process_bet_result(
                        last_bet['type'], 
                        latest_result, 
                        game_data.get('round_number', self.tm.game_count)
                    )
                    self.logger.info(f"이전 베팅 결과: {result_status}")
                    
                    # 베팅 상태 초기화
                    self.tm.betting_service.has_bet_current_round = False
            
            # 2. 베팅 쿨다운 적용 후 예측값 요청
            if not self.betting_cooldown:
                self.betting_cooldown = True
                QTimer.singleShot(3000, lambda: self._request_betting_with_latest_data())  # 3초 후 실행
                QTimer.singleShot(8000, self._reset_betting_cooldown)  # 8초 후 쿨다운 해제
                
        except Exception as e:
            self.logger.error(f"게임 결과 처리 및 베팅 오류: {e}")

    def _handle_win_result(self):
        """승리 결과 처리"""
        try:
            self.logger.info("🎉 승리 처리 - 새로운 연패 방 검색")
            
            # 상태 초기화
            self.betting_cooldown = False
            self.consecutive_requests = 0
            self.last_bet_round = 0
            
            # 위젯 초기화
            if hasattr(self.tm.main_window, 'betting_widget'):
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.tm.main_window.betting_widget.reset_step_markers()
            
            # 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset()
            
            # 현재 방 정보 초기화
            self.tm.current_target_room = None
            self.tm.target_streak_rooms = []
            
            # 새로운 연패 방 검색 모드로 전환
            self.tm.streak_handler.return_to_streak_monitoring()
            
        except Exception as e:
            self.logger.error(f"승리 처리 오류: {e}")

    def _handle_lose_result(self):
        """패배 결과 처리"""
        try:
            self.logger.info("❌ 패배 처리")
            
            # 위젯 카운터 증가
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.tm.main_window.betting_widget.room_position_counter = current_pos + 1
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "X")
            
            # 연패 확인
            if self._check_consecutive_losses():
                self.logger.info("연패 조건 달성 - 새로운 방 검색")
                # 상태 초기화
                self.betting_cooldown = False
                self.consecutive_requests = 0
                self.last_bet_round = 0
                # 새로운 방 검색
                self.tm.streak_handler.return_to_streak_monitoring()
                
        except Exception as e:
            self.logger.error(f"패배 처리 오류: {e}")

    def _handle_tie_result(self):
        """무승부 결과 처리"""
        try:
            self.logger.info("🤝 무승부 처리")
            
            # 베팅 상태 초기화
            self.tm.betting_service.has_bet_current_round = False
            self.tm.had_tie_last_round = True
            
            # 타이 후에는 쿨다운 해제 (바로 다시 베팅 가능)
            self.betting_cooldown = False
            
        except Exception as e:
            self.logger.error(f"무승부 처리 오류: {e}")

    def _check_consecutive_losses(self) -> bool:
        """연패 확인"""
        try:
            if hasattr(self.tm, 'excel_trading_service'):
                return self.tm.excel_trading_service.should_change_room()
            return False
        except Exception as e:
            self.logger.error(f"연패 확인 오류: {e}")
            return False

    def cleanup(self):
        """리소스 정리"""
        try:
            if self.betting_timer:
                self.betting_timer.stop()
                self.betting_timer = None
            
            self.is_processing_result = False
            self.betting_cooldown = False
            self.consecutive_requests = 0
            
        except Exception as e:
            self.logger.error(f"GameProcessor 정리 오류: {e}")