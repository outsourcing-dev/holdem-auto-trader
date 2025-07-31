# utils/trading_manager_modules/game_processor.py (무한루프 방지 수정)
import logging
import time
from PyQt6.QtCore import QTimer


class GameProcessor:
    """게임 데이터 처리 전담 클래스 - 베팅 중복 방지 개선"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger
        
        # 🔥 베팅 상태 추적 강화
        self.current_betting_round = 0  # 현재 베팅한 라운드
        self.waiting_for_result = False  # 베팅 결과 대기 중
        self.last_processed_result_round = 0  # 마지막으로 처리한 결과 라운드
        
        # 기존 변수들
        self.is_processing_result = False
        self.last_processed_time = 0
        self.min_process_interval = 2.0
        self.betting_cooldown = False

    def on_game_data_received(self, game_data: dict):
        """게임 데이터 수신 처리 - 베팅 결과 우선 처리"""
        try:
            current_time = time.time()
            
            # 너무 빠른 연속 처리 방지
            if current_time - self.last_processed_time < self.min_process_interval:
                return
            
            if self.is_processing_result:
                return
            
            self.is_processing_result = True
            self.last_processed_time = current_time
            
            try:
                self.tm.last_game_data = game_data
                self.tm.message_count += 1
                
                room_name = game_data.get('room_name', '')
                if self.tm.current_target_room and room_name:
                    target_room_name = self.tm.current_target_room.get('room_name', '')
                    if target_room_name in room_name:
                        # 🔥 베팅 결과부터 우선 처리
                        if self._process_betting_result_first(game_data):
                            # 베팅 결과 처리 완료 후에만 새로운 베팅 고려
                            self._consider_new_betting(game_data)
                        else:
                            # 베팅 결과 처리 중이면 새로운 베팅 금지
                            self.logger.debug("베팅 결과 대기 중 - 새로운 베팅 금지")
                        
            finally:
                self.is_processing_result = False
                
        except Exception as e:
            self.logger.error(f"게임 데이터 수신 처리 오류: {e}")
            self.is_processing_result = False

    def _process_betting_result_first(self, game_data: dict) -> bool:
        """베팅 결과 우선 처리 - True 반환 시 새로운 베팅 가능"""
        try:
            round_number = game_data.get('round_number', 0)
            latest_result = game_data.get('latest_result', '')
            
            # 🔥 베팅 결과 대기 중인지 확인
            if self.waiting_for_result and self.current_betting_round > 0:
                # 베팅한 라운드 이후의 결과인지 확인
                if round_number > self.current_betting_round and latest_result in ['P', 'B', 'T']:
                    self.logger.info(f"🎯 베팅 결과 확인: 라운드 {round_number}, 결과 {latest_result}")
                    
                    # 베팅 서비스에서 결과 확인
                    if hasattr(self.tm.betting_service, 'check_pending_bet_result'):
                        bet_result = self.tm.betting_service.check_pending_bet_result(round_number, latest_result)
                        
                        if bet_result:
                            self._handle_betting_result(bet_result)
                            
                            # 베팅 결과 처리 완료
                            self.waiting_for_result = False
                            self.current_betting_round = 0
                            self.last_processed_result_round = round_number
                            
                            return True  # 새로운 베팅 가능
                
                # 아직 베팅 결과가 나오지 않음
                return False
            
            # 베팅 결과 대기 중이 아니면 새로운 베팅 가능
            return True
            
        except Exception as e:
            self.logger.error(f"베팅 결과 처리 오류: {e}")
            return False

    def _handle_betting_result(self, bet_result: dict):
        """베팅 결과 처리"""
        try:
            result_status = bet_result['status']
            bet_type = bet_result['bet_type']
            game_result = bet_result['game_result']
            
            self.logger.info(f"🎲 베팅 결과 처리: {bet_type} vs {game_result} = {result_status}")
            
            # 결과에 따른 처리
            if result_status == "win":
                self._handle_win_result_tracked()
            elif result_status == "lose":
                self._handle_lose_result_tracked()
            elif result_status == "tie":
                self._handle_tie_result_tracked()
                
        except Exception as e:
            self.logger.error(f"베팅 결과 처리 오류: {e}")

    def _consider_new_betting(self, game_data: dict):
        """새로운 베팅 고려 - 베팅 결과 처리 완료 후에만 실행"""
        try:
            # 🔥 베팅 대기 중이면 새로운 베팅 금지
            if self.waiting_for_result:
                self.logger.debug("베팅 결과 대기 중 - 새로운 베팅 금지")
                return
            
            # 베팅 쿨다운 중이면 대기
            if self.betting_cooldown:
                return
            
            # 현재 방과 일치하는지 확인
            if not self.tm.current_target_room or self.tm.room_entry_in_progress:
                return
            
            # 첫 결과 대기 중 처리
            if self.tm.wait_first_result:
                self._handle_first_result_mode(game_data)
                return
            
            # 새로운 베팅 기회 확인
            self._check_new_betting_opportunity(game_data)
                
        except Exception as e:
            self.logger.error(f"새로운 베팅 고려 오류: {e}")

    def _check_new_betting_opportunity(self, game_data: dict):
        """새로운 베팅 기회 확인"""
        try:
            # 🔥 베팅 쿨다운 시작
            self.betting_cooldown = True
            
            # 지연된 베팅 실행
            QTimer.singleShot(3000, lambda: self._execute_delayed_betting(game_data))
            
            # 쿨다운 해제
            QTimer.singleShot(10000, self._reset_betting_cooldown)
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")
            self.betting_cooldown = False

    def _execute_delayed_betting(self, game_data: dict):
        """지연된 베팅 실행 - 상태 재확인"""
        try:
            # 🔥 베팅 가능 상태 재확인
            if self.waiting_for_result:
                self.logger.info("베팅 결과 대기 중 - 지연 베팅 취소")
                return
                
            if not self.tm.current_target_room:
                self.logger.info("타겟 방 없음 - 지연 베팅 취소")
                return
            
            # 최신 데이터로 베팅 실행
            self._request_betting_with_latest_data()
            
        except Exception as e:
            self.logger.error(f"지연 베팅 실행 오류: {e}")

    def _request_betting_with_latest_data(self):
        """최신 데이터로 베팅 요청"""
        try:
            # 🔥 베팅 상태 재확인
            if self.waiting_for_result:
                self.logger.debug("베팅 결과 대기 중 - 베팅 요청 취소")
                return
                
            room_id = self.tm.current_target_room.get('room_id', '')
            room_name = self.tm.current_target_room.get('room_name', '')
            
            self.logger.info(f"🔍 최신 데이터로 베팅 요청: {room_name}")
            
            # 최신 게임 상태 가져오기
            latest_game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=room_name,
                log_always=True,
                desired_pb_count=15
            )
            
            if not latest_game_state:
                self.logger.warning("최신 게임 상태를 가져올 수 없습니다")
                return
            
            current_results = latest_game_state.get('filtered_results', [])
            
            if len(current_results) < 5:
                self.logger.info(f"데이터 부족 - 베팅 보류 (현재 {len(current_results)}개)")
                return
            
            # 서버에서 예측값 요청
            next_pick = self.tm.server_client.get_next_prediction(room_id, current_results)
            self.logger.info(f"🎯 서버 예측 결과: {next_pick}")
            
            if next_pick in ['P', 'B']:
                round_number = latest_game_state.get('round', self.tm.game_count + 1)
                
                # 🔥 베팅 상태 설정
                self.current_betting_round = round_number
                self.waiting_for_result = True
                
                self.logger.info(f"🎯 베팅 실행: {next_pick} (라운드 {round_number})")
                self.tm.betting_executor.execute_betting(next_pick, round_number)
            else:
                self.logger.info(f"베팅 안함: {next_pick}")
                
        except Exception as e:
            self.logger.error(f"베팅 요청 오류: {e}")

    def _handle_win_result_tracked(self):
        """승리 결과 처리 - 추적 시스템용"""
        try:
            self.logger.info("🎉 승리 처리")
            
            # 위젯 초기화
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "O")
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.tm.main_window.betting_widget.reset_step_markers()
            
            # 상태 초기화
            self._reset_betting_state()
            
            # 새로운 연패 방 검색
            self.tm.streak_handler.return_to_streak_monitoring()
            
        except Exception as e:
            self.logger.error(f"승리 처리 오류: {e}")

    def _handle_lose_result_tracked(self):
        """패배 결과 처리 - 추적 시스템용"""
        try:
            self.logger.info("❌ 패배 처리")
            
            # 위젯 업데이트
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "X")
                self.tm.main_window.betting_widget.room_position_counter = current_pos + 1
            
            # 연패 확인
            if self._check_consecutive_losses():
                self.logger.info("연패 조건 달성 - 새로운 방 검색")
                self._reset_betting_state()
                self.tm.streak_handler.return_to_streak_monitoring()
                
        except Exception as e:
            self.logger.error(f"패배 처리 오류: {e}")

    def _handle_tie_result_tracked(self):
        """무승부 결과 처리 - 추적 시스템용"""
        try:
            self.logger.info("🤝 무승부 처리")
            
            # 무승부는 베팅 상태 유지하고 바로 다시 베팅 가능
            self.waiting_for_result = False
            self.current_betting_round = 0
            self.tm.had_tie_last_round = True
            
            # 쿨다운 해제 (바로 다시 베팅 가능)
            self.betting_cooldown = False
            
        except Exception as e:
            self.logger.error(f"무승부 처리 오류: {e}")

    def _reset_betting_state(self):
        """베팅 상태 초기화"""
        self.waiting_for_result = False
        self.current_betting_round = 0
        self.betting_cooldown = False

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
            self._reset_betting_state()
        except Exception as e:
            self.logger.error(f"GameProcessor 정리 오류: {e}")
            
    # utils/trading_manager_modules/game_processor.py에 추가할 메서드
    def _handle_game_result(self, game_data: dict):
        """게임 결과 처리 - 베팅 결과 확인 포함"""
        try:
            latest_result = game_data.get('latest_result', '')
            round_number = game_data.get('round_number', 0)
            
            # 게임 카운트 업데이트
            if round_number > self.tm.game_count:
                self.tm.game_count = round_number
            
            # 🔥 새로운 결과가 있는 경우 대기 중인 베팅 결과 확인
            if latest_result and latest_result in ['P', 'B', 'T']:
                # 중복 결과 방지
                result_id = f"{round_number}_{latest_result}"
                if result_id in self.tm.processed_rounds:
                    return
                
                self.tm.processed_rounds.add(result_id)
                self.tm.result_count += 1
                
                self.logger.info(f"🎯 새로운 게임 결과: 라운드 {round_number}, 결과 {latest_result}")
                
                # 🔥 대기 중인 베팅 결과 확인 (핵심!)
                bet_result = self.tm.betting_service.check_pending_bet_result(round_number, latest_result)
                
                if bet_result:
                    self.logger.info(f"🎲 베팅 결과: {bet_result['result_text']} ({bet_result['bet_type']} vs {bet_result['game_result']})")
                    
                    # 결과에 따른 처리
                    if bet_result['status'] == 'win':
                        self._handle_win_result_tracked()
                    elif bet_result['status'] == 'lose':
                        self._handle_lose_result_tracked()
                    elif bet_result['status'] == 'tie':
                        self._handle_tie_result_tracked()
                else:
                    # 대기 중인 베팅이 없거나 아직 결과가 나오지 않음
                    pending_info = self.tm.betting_service.get_pending_bet_status()
                    if pending_info['has_pending']:
                        self.logger.info(f"⏳ 베팅 결과 대기 중: {pending_info['bet_type']} (라운드 {pending_info['bet_round']})")
                    else:
                        self.logger.debug("대기 중인 베팅 없음")
                
                # ExcelTradingService에 결과 추가
                if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                    if latest_result in ['P', 'B']:
                        self.tm.excel_trading_service.choice_pick_system.add_result(latest_result)
                        
        except Exception as e:
            self.logger.error(f"게임 결과 처리 오류: {e}")

    def _handle_win_result_tracked(self):
        """승리 결과 처리 - 베팅 추적 시스템 기반"""
        try:
            self.logger.info("🎉 베팅 승리 처리")
            
            # 위젯 초기화
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "O")
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.tm.main_window.betting_widget.reset_step_markers()
            
            # 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset()
            
            # 승리 플래그 설정
            self.tm.just_won = True
            
            # 상태 초기화
            self.betting_cooldown = False
            self.consecutive_requests = 0
            self.last_bet_round = 0
            
            # 새로운 연패 방 검색 모드로 전환
            self.tm.streak_handler.return_to_streak_monitoring()
            
            self.logger.info("✅ 승리 처리 완료 - 새로운 연패 방 검색")
            
        except Exception as e:
            self.logger.error(f"승리 처리 오류: {e}")

    def _handle_lose_result_tracked(self):
        """패배 결과 처리 - 베팅 추적 시스템 기반"""
        try:
            self.logger.info("❌ 베팅 패배 처리")
            
            # 위젯 카운터 증가
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "X")
                self.tm.main_window.betting_widget.room_position_counter = current_pos + 1
            
            # ExcelTradingService에 패배 기록
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.record_betting_result(False)
            
            # 연패 확인
            if self._check_consecutive_losses():
                self.logger.info("연패 조건 달성 - 새로운 방 검색")
                self.betting_cooldown = False
                self.consecutive_requests = 0
                self.last_bet_round = 0
                self.tm.streak_handler.return_to_streak_monitoring()
            else:
                # 패배했지만 연패 조건 미달성 - 현재 방에서 계속
                self.logger.info("패배했으나 연패 조건 미달성 - 현재 방에서 계속")
                self.betting_cooldown = False  # 다음 베팅 준비
                    
        except Exception as e:
            self.logger.error(f"패배 처리 오류: {e}")

    def _handle_tie_result_tracked(self):
        """무승부 결과 처리 - 베팅 추적 시스템 기반"""
        try:
            self.logger.info("🤝 베팅 무승부 처리")
            
            # 무승부 시에는 베팅 상태를 유지하고 다시 베팅 가능
            self.tm.betting_service.has_bet_current_round = False
            self.tm.had_tie_last_round = True
            
            # 타이 후에는 쿨다운 해제 (바로 다시 베팅 가능)
            self.betting_cooldown = False
            
            self.logger.info("무승부 - 동일 조건으로 재베팅 준비")
            
        except Exception as e:
            self.logger.error(f"무승부 처리 오류: {e}")

    # 🔥 베팅 결과 확인을 위한 추가 메서드
    def debug_betting_tracker_status(self):
        """베팅 추적 상태 디버그"""
        try:
            self.logger.info("🔍 베팅 추적 시스템 상태:")
            
            pending_status = self.tm.betting_service.get_pending_bet_status()
            self.logger.info(f"  - 대기 중인 베팅: {pending_status['has_pending']}")
            
            if pending_status['has_pending']:
                self.logger.info(f"    * 베팅 타입: {pending_status['bet_type']}")
                self.logger.info(f"    * 베팅 라운드: {pending_status['bet_round']}")
                self.logger.info(f"    * 베팅 금액: {pending_status['bet_amount']:,}원")
                self.logger.info(f"    * 대기 시간: {pending_status['waiting_time']:.1f}초")
                self.logger.info(f"    * 결과 확정: {pending_status['result_confirmed']}")
            
            self.logger.info(f"  - 현재 게임 라운드: {self.tm.game_count}")
            self.logger.info(f"  - 결과 처리 중: {self.is_processing_result}")
            self.logger.info(f"  - 베팅 쿨다운: {self.betting_cooldown}")
            
        except Exception as e:
            self.logger.error(f"베팅 추적 상태 디버그 오류: {e}")

    def get_betting_statistics(self):
        """베팅 통계 반환"""
        try:
            pending_status = self.tm.betting_service.get_pending_bet_status()
            
            return {
                'has_pending_bet': pending_status['has_pending'],
                'pending_bet_type': pending_status['bet_type'],
                'pending_bet_round': pending_status['bet_round'],
                'waiting_time': pending_status['waiting_time'],
                'current_game_round': self.tm.game_count,
                'result_count': self.tm.result_count,
                'is_processing': self.is_processing_result,
                'betting_cooldown': self.betting_cooldown
            }
            
        except Exception as e:
            self.logger.error(f"베팅 통계 조회 오류: {e}")
            return {'error': str(e)}