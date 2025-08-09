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
        self.min_request_interval = 1.0  # 최소 요청 간격 단축 (2초→1초)
        self.consecutive_requests = 0
        self.max_consecutive_requests = 5  # 최대 연속 요청 증가 (3→5)
        
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
            current_game = game_data.get('current_game', 0)  # 🔥 현재 진행 중인 게임 번호
            
            self.logger.info(f"🎲 [GameProcessor] 게임 결과 처리 시작:")
            self.logger.info(f"  - 완료된 라운드: {round_number}")
            self.logger.info(f"  - 진행 중인 게임: {current_game}")
            self.logger.info(f"  - 결과: {latest_result}")
            
            # 중복 결과 방지
            result_id = f"{round_number}_{latest_result}"
            if result_id in self.tm.processed_rounds:
                self.logger.debug(f"  - 이미 처리된 결과, 건너뜀: {result_id}")
                return
            
            self.tm.processed_rounds.add(result_id)
            self.tm.result_count += 1
            
            self.logger.info(f"🎯 새로운 게임 결과 등록: #{self.tm.result_count}")
            
            # 베팅 결과 추적기로 결과 확인
            if self.betting_tracker.is_waiting_for_result():
                self.logger.info("📊 베팅 결과 대기 중 - 결과 체크 시작")
                # 베팅한 라운드 확인
                bet_round = self.betting_tracker.get_bet_round()
                bet_type = self.betting_tracker.get_bet_type()
                self.logger.info(f"  - 베팅 라운드: {bet_round}")
                self.logger.info(f"  - 베팅 타입: {bet_type}")
                
                # 🔥 베팅 직후 즉시 결과 비교 방지 - 라운드 진행 확인
                current_time = time.time()
                bet_time = self.betting_tracker.bet_info.get('bet_time', 0)
                time_since_bet = current_time - bet_time
                
                # 베팅 후 최소 3초 대기로 단축 (빠른 반응)
                if time_since_bet < 3.0:  # 3초 미만이면 대기
                    self.logger.info(f"⏳ 베팅 직후 대기 중: {time_since_bet:.1f}초 경과 (최소 3초 대기)")
                    return
                
                # 🔥 추가: 대기 시간이 길어지면 더 적극적으로 결과 매칭
                urgent_processing = time_since_bet > 30.0
                if urgent_processing:
                    self.logger.info(f"⚡ 긴급 처리 모드: {time_since_bet:.1f}초 대기 - 더 유연한 매칭 적용")
                    
                # 🔥 단순화: 베팅한 라운드보다 2 이상 작은 경우만 무시 (타이 등으로 인한 지연 고려)
                if round_number < bet_round - 1 and not urgent_processing:
                    self.logger.info(f"📋 과거 라운드 결과 무시: 완료된 라운드={round_number}, 베팅 대상={bet_round}")
                    return
                
                # 🔥 개선: 라운드 진행 상황에 따른 유연한 처리
                should_wait = False
                
                if current_game > 0 and not urgent_processing:
                    # 베팅한 라운드가 현재 진행 중인 게임인 경우
                    if bet_round == current_game:
                        # 완료된 라운드가 베팅 라운드보다 하나 작으면 아직 진행 중
                        if round_number < current_game:
                            should_wait = True
                            self.logger.info(f"⏳ 베팅한 게임({bet_round})이 아직 진행 중 (current_game={current_game}) - 다음 결과 대기")
                    # 베팅한 라운드가 이미 완료되어야 하는 경우 - 더 유연한 처리
                    elif bet_round < current_game:
                        # 완료된 라운드가 베팅 라운드보다 작으면 대기
                        if round_number < bet_round:
                            should_wait = True
                            self.logger.info(f"⏳ 베팅 라운드({bet_round}) 결과 아직 미완료 - 대기 중")
                    # 베팅한 라운드가 현재 게임보다 크면 미래 베팅 - 일단 대기
                    elif bet_round > current_game:
                        should_wait = True
                        self.logger.info(f"🔮 미래 라운드 베팅({bet_round}) 대기 중 (current_game={current_game})")
                
                if should_wait:
                    return
                
                # 디버깅 로그 추가 - INFO 레벨로 변경
                self.logger.info(f"🔍 베팅 추적: 베팅 라운드={bet_round}, 완료된 라운드={round_number}, 진행 중인 라운드={current_game}")
                
                # 🔥 베팅한 라운드의 결과인지 확인 - 더 유연한 매칭
                is_bet_result = False
                
                # 정확한 라운드 매칭
                if round_number == bet_round:
                    is_bet_result = True
                    self.logger.info(f"✅ 정확한 라운드 매칭: {round_number} == {bet_round}")
                # 라운드 차이가 1 이내이고 시간이 충분히 지났으면 허용
                elif abs(round_number - bet_round) == 1 and time_since_bet > 10.0:
                    is_bet_result = True
                    self.logger.info(f"⚡ 유연한 라운드 매칭: {round_number} ≈ {bet_round} (시간: {time_since_bet:.1f}s)")
                
                if is_bet_result:
                    betting_result = self.betting_tracker.check_result(bet_round, latest_result)
                    
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
                    # 타임아웃 체크 추가
                    if time_since_bet > 60.0:  # 60초 이상 대기 시 타임아웃
                        self.logger.warning(f"⚠️ 베팅 결과 타임아웃 ({time_since_bet:.1f}s) - 추적 초기화")
                        self.betting_tracker.reset_tracking()
                        if hasattr(self.tm.betting_service, 'has_bet_current_round'):
                            self.tm.betting_service.has_bet_current_round = False
                        
                        # 게임 모니터링 워커의 베팅 플래그도 리셋
                        if (hasattr(self.tm, 'room_entry_handler') and 
                            hasattr(self.tm.room_entry_handler, 'game_monitoring_worker')):
                            self.tm.room_entry_handler.game_monitoring_worker.reset_betting_flag()
                            self.logger.info("✅ 타임아웃으로 게임 모니터링 워커 베팅 플래그 리셋")
                        
                        # 타임아웃 발생 시 패배로 처리하여 Martin 진행
                        self.logger.info("⚠️ 타임아웃 발생 - 패배로 처리하여 다음 마틴 단계 진행")
                        self._handle_lose_result_tracked()
                    else:
                        self.logger.info(f"베팅 라운드({bet_round})를 대기 중 - 현재 라운드({round_number}) (대기시간: {time_since_bet:.1f}s)")
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
                self.logger.debug("🎯 이미 현재 라운드 베팅함 - 건너뜀")
                return
            
            # 베팅 추적기가 결과 대기 중이면 베팅 안함
            if self.betting_tracker.is_waiting_for_result():
                self.logger.debug("⏳ 베팅 결과 대기 중 - 건너뜀")
                return
            
            # 첫 결과 대기 중 처리
            if self.tm.wait_first_result:
                latest_result = game_data.get('latest_result')
                if latest_result and latest_result in ['P', 'B', 'T']:
                    self.tm.wait_first_result = False
                    self.logger.info(f"첫 결과 수신 - 대기 모드 해제: {latest_result}")
                    
                    # 🔥 입장 직후는 추가 대기 (first_bet_after_entry 플래그가 처리함)
                    self.logger.info("🕐 입장 직후 - 다음 라운드까지 대기")
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
            QTimer.singleShot(2000, self._reset_betting_cooldown)  # 3초→2초로 더 단축 (빠른 재베팅)
                
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
            self.betting_timer.start(200)  # 0.5초→0.2초로 더 단축 (빠른 베팅)
            
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
            # 🔥 로비 상태에서는 베팅 로직 실행 안함
            if not self.tm.current_target_room:
                self.logger.debug("로비 상태 - 베팅 로직 실행 안함")
                return
                
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
                
                # 🔥 연패 검증 + 예측값 요청 (verify_and_predict 사용)
                expected_streak = self.tm.current_target_room.get('streak_count', 3)
                
                self.logger.info(f"🔮 연패 검증 및 예측값 요청:")
                self.logger.info(f"  - 방 ID: {room_id}")
                self.logger.info(f"  - 예상 연패: {expected_streak}")
                self.logger.info(f"  - 결과 개수: {len(current_results)}개")
                self.logger.info(f"  - 현재 결과: {current_results[-10:] if len(current_results) >= 10 else current_results}")
                
                # verify_and_predict API 호출 (연패 검증 + 예측값 동시)
                response = self.tm.server_client.verify_and_predict(
                    room_id=room_id,
                    current_results=current_results,
                    expected_streak=expected_streak
                )
                
                if not response:
                    self.logger.error("❌ 서버 응답 없음")
                    return
                
                # 연패 상태 확인
                status = response.get('status')
                current_streak = response.get('current_streak', 0)
                next_pick = response.get('next_prediction')
                
                self.logger.info(f"📊 서버 응답:")
                self.logger.info(f"  - 상태: {status}")
                self.logger.info(f"  - 현재 연패: {current_streak}")
                self.logger.info(f"  - 예측값: {next_pick}")
                
                # 연패 검증 실패 시 방 나가기
                if status != 'streak_valid':
                    self.logger.warning(f"❌ 연패 검증 실패!")
                    self.logger.warning(f"  - 현재 연패: {current_streak}")
                    self.logger.warning(f"  - 예상 연패: {expected_streak}")
                    self.logger.warning(f"  - 메시지: {response.get('message', '연패가 깨졌습니다')}")
                    
                    # 베팅 추적기 초기화
                    self.betting_tracker.reset_tracking()
                    
                    # Worker 중지 (있으면)
                    if hasattr(self.tm, 'game_monitoring_worker'):
                        try:
                            self.tm.game_monitoring_worker.stop()
                        except:
                            pass
                    
                    # 방 나가기
                    self.tm.streak_handler.return_to_streak_monitoring()
                    return
                
                # 연패 유지 확인 - 베팅 진행
                self.logger.info(f"✅ 연패 유지 확인: {current_streak}연패 >= {expected_streak}연패")
                
                # 유효한 예측값이면 베팅 실행
                if next_pick in ['P', 'B']:
                    # 베팅 라운드 중복 확인
                    round_number = latest_game_state.get('round', self.tm.game_count + 1)
                    current_game = latest_game_state.get('current_game', 0)
                    
                    # 실제 베팅 대상 라운드 계산
                    target_betting_round = current_game if current_game > 0 else round_number + 1
                    
                    if target_betting_round <= self.last_bet_round:
                        self.logger.info(f"이미 베팅한 라운드: {target_betting_round} <= {self.last_bet_round}")
                        return
                    
                    self.last_bet_round = target_betting_round
                    
                    # ⚡ 즉시 베팅 실행 (current_game 전달)
                    self.logger.info(f"💰 베팅 실행: {next_pick} (라운드 {target_betting_round})")
                    self.tm.betting_executor.execute_betting(next_pick, round_number, current_game)
                else:
                    self.logger.warning(f"⚠️ 유효하지 않은 예측값: {next_pick}")
                    
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
            
            # Martin 서비스에 승리 결과 처리
            if hasattr(self.tm, 'martin_service'):
                current_round = self.tm.game_count
                self.tm.martin_service.process_bet_result("win", current_round)
                self.logger.info(f"✅ Martin 서비스에 승리 결과 처리 완료 (라운드: {current_round})")
            
            # 상태 초기화
            self.betting_cooldown = False
            self.consecutive_requests = 0
            self.last_bet_round = 0
            
            # 마틴 서비스 승리 후 초기화 (위젯 초기화 포함)
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset_after_win()
            
            # 위젯에 승리 마커 설정 (이미 위에서 초기화됨)
            if hasattr(self.tm.main_window, 'betting_widget'):
                self.tm.main_window.betting_widget.set_step_marker(0, "O")  # 승리 마커
            
            # Excel Trading Service에 승리 기록
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.record_betting_result(True)
            
            # 방 로그에 승리 기록 (오류가 있어도 방 나가기는 계속 진행)
            try:
                if hasattr(self.tm.main_window, 'room_log_widget') and self.tm.current_room_name:
                    self.tm.main_window.room_log_widget.add_bet_result(self.tm.current_room_name, True, False)
                    self.logger.info(f"📝 방 로그에 승리 기록: {self.tm.current_room_name}")
            except Exception as log_error:
                self.logger.error(f"방 로그 기록 중 오류 (계속 진행): {log_error}")
            
            # 🔥 승리 시에만 방 나가기 (TIE는 방을 나가지 않음)
            self.logger.info("✅ 승리로 인한 방 나가기 - 새로운 연패방 검색")
            
            # 게임 모니터링 워커 베팅 플래그 리셋
            if (hasattr(self.tm, 'room_entry_handler') and 
                hasattr(self.tm.room_entry_handler, 'game_monitoring_worker')):
                self.tm.room_entry_handler.game_monitoring_worker.betting_in_progress = False
                self.logger.info("✅ 승리 후 게임 모니터링 워커 베팅 플래그 리셋")
            
            # 베팅 서비스 상태 초기화
            if hasattr(self.tm.betting_service, 'has_bet_current_round'):
                self.tm.betting_service.has_bet_current_round = False
            
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
            
            # Martin 서비스에 패배 결과 처리
            if hasattr(self.tm, 'martin_service'):
                current_round = self.tm.game_count
                self.tm.martin_service.process_bet_result("lose", current_round)
                self.logger.info(f"✅ Martin 서비스에 패배 결과 처리 완료 (라운드: {current_round})")
            
            # 위젯 카운터 증가 (Martin service process_bet_result에서도 처리하지만 중복 방지 체크)
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "X")  # 패배 마커
                # Martin service에서 이미 증가시켰을 수 있으므로 확인
                if self.tm.main_window.betting_widget.room_position_counter == current_pos:
                    self.tm.main_window.betting_widget.room_position_counter = current_pos + 1
            
            # Excel Trading Service에 패배 기록
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.record_betting_result(False)
            
            # 🔥 마틴 한계 도달 확인 (마지막 단계 베팅 후 실패)
            if hasattr(self.tm.main_window, 'betting_widget') and hasattr(self.tm, 'martin_service'):
                current_pos = self.tm.main_window.betting_widget.room_position_counter
                martin_stages = len(self.tm.martin_service.martin_amounts)
                
                # 현재 위치가 마틴 단계 수에 도달했다면 (마지막 단계 베팅 실패)
                if current_pos >= martin_stages:
                    self.logger.info(f"🚨 마틴게일 한계 도달! ({current_pos}/{martin_stages}단계)")
                    self.logger.info("💸 마지막 마틴 베팅 실패 - 1단계로 초기화하고 방 나가기")
                    
                    # 방 로그에 패배 기록 (마틴 한계 도달)
                    try:
                        if hasattr(self.tm.main_window, 'room_log_widget') and self.tm.current_room_name:
                            self.tm.main_window.room_log_widget.add_bet_result(self.tm.current_room_name, False, False)
                            self.logger.info(f"📝 방 로그에 마틴 한계 패배 기록: {self.tm.current_room_name}")
                    except Exception as log_error:
                        self.logger.error(f"방 로그 기록 중 오류 (계속 진행): {log_error}")
                    
                    # 🔥 마틴 서비스 완전 초기화 (다음 방에서 1단계부터 시작)
                    if hasattr(self.tm, 'martin_service'):
                        self.tm.martin_service.reset()
                        self.logger.info("✅ 마틴 한계 도달로 마틴 상태 완전 초기화")
                    
                    # 베팅 추적기 초기화
                    self.betting_tracker.reset_tracking()
                    
                    # 상태 초기화
                    self.betting_cooldown = False
                    self.consecutive_requests = 0
                    self.last_bet_round = 0
                    
                    # 방 나가고 새로운 방 검색
                    self.tm.streak_handler.return_to_streak_monitoring()
                    return
            
            # 🔥 마틴 한계 미도달 시 - 다음 마틴 단계로 베팅 계속
            else:
                self.logger.info(f"📈 마틴 단계 진행: {current_pos}/{martin_stages} - 다음 베팅 대기")
                
                # 베팅 상태 초기화 (다음 베팅을 위해)
                self.betting_cooldown = False
                self.consecutive_requests = 0
                self.last_bet_round = 0
                
                # 게임 모니터링 워커의 베팅 플래그도 리셋
                if (hasattr(self.tm, 'room_entry_handler') and 
                    hasattr(self.tm.room_entry_handler, 'game_monitoring_worker')):
                    self.tm.room_entry_handler.game_monitoring_worker.betting_in_progress = False
                    self.logger.info("✅ 게임 모니터링 워커의 betting_in_progress 플래그 리셋")
                
                # 베팅 서비스 상태 초기화
                if hasattr(self.tm.betting_service, 'has_bet_current_round'):
                    self.tm.betting_service.has_bet_current_round = False
                
                self.logger.info("🔄 다음 마틴 단계 베팅 준비 완료 - 모니터링 재개")
                
                # 즉시 다음 베팅 기회를 찾기 위해 짧은 딜레이 후 베팅 시도
                from PyQt6.QtCore import QTimer
                def trigger_next_betting():
                    if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, '_request_betting_with_latest_data'):
                        self.logger.info("⚡ 패배 후 즉시 다음 베팅 기회 탐색")
                        self.tm.game_processor._request_betting_with_latest_data()
                
                QTimer.singleShot(2000, trigger_next_betting)  # 2초 후 다음 베팅 시도
                
        except Exception as e:
            self.logger.error(f"패배 처리 오류: {e}")

    def _handle_tie_result_tracked(self):
        """무승부 결과 처리 - 마틴 단계 유지하고 재베팅"""
        try:
            self.logger.info("🤝 TIE 무승부 - 같은 방에서 같은 단계로 재베팅")
            
            # 🔥 이전 베팅 정보 저장 (TIE 재베팅용)
            last_bet_pick = self.betting_tracker.get_bet_type()
            self.last_tie_bet_pick = last_bet_pick  # TIE 시 마지막 베팅값 저장
            self.logger.info(f"📝 TIE 발생 - 이전 베팅값 저장: {last_bet_pick}")
            
            # 현재 마틴 단계 확인
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.logger.info(f"🎯 TIE - 마틴 {current_pos + 1}단계 유지, 방 나가지 않음")
            
            # Martin 서비스에 무승부 결과 처리
            if hasattr(self.tm, 'martin_service'):
                current_round = self.tm.game_count
                self.tm.martin_service.process_bet_result("tie", current_round)
                self.logger.info(f"✅ Martin 서비스에 무승부 결과 처리 완료 (라운드: {current_round})")
            
            # 추적 상태 초기화 (새로운 베팅을 위해)
            self.betting_tracker.reset_tracking()
            
            # 베팅 상태 초기화 (재베팅 가능하도록)
            self.tm.betting_service.has_bet_current_round = False
            self.tm.had_tie_last_round = True
            
            # 타이 후에는 쿨다운 해제 (즉시 재베팅 가능)
            self.betting_cooldown = False
            
            # 🔥 중요: 게임 모니터링 워커의 betting_in_progress 플래그도 리셋
            if (hasattr(self.tm, 'room_entry_handler') and 
                hasattr(self.tm.room_entry_handler, 'game_monitoring_worker')):
                self.tm.room_entry_handler.game_monitoring_worker.betting_in_progress = False
                self.logger.info("✅ 게임 모니터링 워커의 betting_in_progress 플래그 리셋")
            
            # 🔥 중요: 방을 나가지 않고 마틴 단계 유지
            # 🔥 current_target_room과 target_streak_rooms는 그대로 유지
            self.logger.info("🏠 TIE - 현재 방 유지, 방 나가지 않음")
            self.logger.info(f"🔄 다음 라운드에서 같은 금액, 같은 값({last_bet_pick})으로 재베팅 준비")
            
            # 마틴 서비스에 TIE 알림 (단계 유지)
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.tie_count += 1
                self.tm.martin_service.need_room_change = False  # 같은 방에서 계속
                self.logger.info(f"📈 누적 TIE 횟수: {self.tm.martin_service.tie_count}")
            
            # TIE 후 빠른 재베팅을 위한 트리거
            from PyQt6.QtCore import QTimer
            def trigger_tie_rebetting():
                if hasattr(self, 'last_tie_bet_pick') and self.last_tie_bet_pick:
                    self.logger.info(f"⚡ TIE 후 즉시 같은 값({self.last_tie_bet_pick})으로 재베팅")
                    # 서버 요청 없이 바로 베팅
                    if hasattr(self.tm, 'betting_executor'):
                        # 현재 게임 상태 확인 후 베팅
                        room_id = self.tm.current_target_room.get('room_id', '') if self.tm.current_target_room else ''
                        room_name = self.tm.current_target_room.get('room_name', '') if self.tm.current_target_room else ''
                        
                        if room_id and room_name:
                            # iframe에서 현재 상태 확인
                            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                                room_id=room_id,
                                room_name=room_name,
                                log_always=False,
                                desired_pb_count=5
                            )
                            if game_state:
                                current_round = game_state.get('round', 0)
                                current_game = game_state.get('current_game', 0)
                                betting_round = current_game if current_game > 0 else current_round + 1
                                self.tm.betting_executor.execute_betting(self.last_tie_bet_pick, current_round, betting_round)
                                self.last_tie_bet_pick = None  # 사용 후 초기화
            
            QTimer.singleShot(3000, trigger_tie_rebetting)  # 3초 후 재베팅 시도
            
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
        """연패 확인 - 마틴게일 전략에서는 사용하지 않음"""
        # 🔥 마틴게일 전략에서는 연패로 방 이동하지 않음
        # 마지막 마틴 단계 실패 시에만 방 이동
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