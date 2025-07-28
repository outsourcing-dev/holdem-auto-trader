# utils/trading_manager_game.py (단순화)
import time
import logging
from PyQt6.QtWidgets import QMessageBox, QApplication

class TradingManagerGame:
    """TradingManager의 게임 처리 관련 기능 클래스 - 서버 기반으로 단순화"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager  # trading_manager 참조
        self.logger = trading_manager.logger or logging.getLogger(__name__)

    def enter_first_room(self):
        """
        첫 방 입장 - 서버 기반으로 단순화
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 서버 기반 방 입장 시도
            if hasattr(self.tm, 'room_entry_service'):
                room_name = self.tm.room_entry_service.enter_room()
                if room_name:
                    self.logger.info(f"서버 추천 방 입장 성공: {room_name}")
                    return self.handle_successful_room_entry(room_name)
                else:
                    self.logger.warning("서버에서 추천할 방이 없습니다.")
                    return self.handle_room_entry_failure()
            else:
                self.logger.error("RoomEntryService가 없습니다.")
                return False
                
        except Exception as e:
            self.logger.error(f"첫 방 입장 중 오류: {e}")
            return self.handle_room_entry_failure()

    def handle_room_entry_failure(self):
        """방 입장 실패 처리 - 단순화"""
        try:
            # UI 상태 업데이트
            if hasattr(self.tm.main_window, 'stop_button'):
                self.tm.main_window.stop_button.setEnabled(False)
                self.tm.main_window.update_button_styles()

            # 트레이딩 중지
            self.tm.stop_trading()
            
            # 사용자에게 알림
            QMessageBox.warning(
                self.tm.main_window, 
                "방 입장 실패", 
                "서버에서 조건에 맞는 방을 찾지 못했습니다.\n잠시 후 다시 시도해주세요."
            )
            return False
            
        except Exception as e:
            self.logger.error(f"방 입장 실패 처리 중 오류: {e}")
            return False

    def handle_successful_room_entry(self, room_name, preserve_martin=False):
        """방 입장 성공 처리 - 단순화"""
        try:
            # UI 상태 업데이트
            if hasattr(self.tm.main_window, 'stop_button'):
                self.tm.main_window.stop_button.setEnabled(True)
                self.tm.main_window.update_button_styles()
            
            # 상태 초기화
            self.tm.current_room_name = room_name
            self.tm.wait_first_result = True  # 첫 결과 대기 모드
            
            self.logger.info(f"방 입장 성공: {room_name}")
            
            # ChoicePickSystem 초기화
            if hasattr(self.tm, 'excel_trading_service') and hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                cps = self.tm.excel_trading_service.choice_pick_system
                cps.wait_first_result = True
                cps.skip_n_count = True
                cps.consecutive_n_count = 0
                self.logger.info("방 입장 후 ChoicePickSystem 초기화 완료")

            # 현재 게임 상태 확인
            try:
                game_state = self.tm.game_monitoring_service.get_current_game_state(log_always=True)
                if game_state:
                    current_round = game_state.get('round', 0)
                    self.tm.game_count = current_round
                    self.tm.entered_round = current_round
                    
                    # ChoicePickSystem에도 라운드 정보 설정
                    if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                        cps = self.tm.excel_trading_service.choice_pick_system
                        cps._entered_round = current_round
                        cps._current_game_round = current_round
                    
                    self.logger.info(f"현재 게임 라운드: {current_round}")
                
            except Exception as e:
                self.logger.warning(f"게임 상태 확인 중 오류: {e}")

            # UI 업데이트
            self.tm.main_window.update_betting_status(room_name=room_name)
            
            # 잔액 확인
            try:
                if hasattr(self.tm, 'balance_service'):
                    balance = self.tm.balance_service.get_lobby_balance()
                    if balance is not None:
                        self.tm.main_window.update_user_data(current_amount=balance)
            except Exception as e:
                self.logger.warning(f"잔액 확인 중 오류: {e}")

            return True
            
        except Exception as e:
            self.logger.error(f"방 입장 성공 처리 중 오류: {e}")
            return False

    def process_excel_result(self, result, game_state, previous_game_count):
        """Excel 결과 처리 - 단순화"""
        try:
            if not result or not game_state:
                return

            last_column, new_game_count, recent_results, next_pick = result
            actual_game_count = game_state.get('round', 0)
            
            # 새로운 결과가 있는 경우만 처리
            if new_game_count > previous_game_count:
                # 첫 결과 대기 모드 해제
                if getattr(self.tm, 'wait_first_result', False):
                    self.logger.info("첫 결과 감지 - 대기 모드 해제")
                    self.tm.wait_first_result = False
                    if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                        self.tm.excel_trading_service.choice_pick_system.wait_first_result = False
                        self.tm.excel_trading_service.choice_pick_system.skip_n_count = False

                # 이전 게임 결과 처리
                self.process_previous_game_result(game_state, new_game_count)
                
                # 방 이동 조건 확인 (단순화)
                if self._should_change_room(actual_game_count, next_pick):
                    self.tm.change_room()
                    return

                # 베팅 처리
                if self._should_place_bet(next_pick, previous_game_count):
                    self._place_bet(next_pick, actual_game_count)

                # 게임 카운트 업데이트
                self.tm.game_count = actual_game_count

        except Exception as e:
            self.logger.error(f"Excel 결과 처리 오류: {e}")

    def _should_change_room(self, actual_game_count, next_pick):
        """방 이동 조건 확인 - 단순화"""
        try:
            # 서버 기반에서는 주로 ChoicePickSystem의 판단을 따름
            if hasattr(self.tm, 'excel_trading_service'):
                if self.tm.excel_trading_service.should_change_room():
                    self.logger.info("ChoicePickSystem에서 방 이동 신호")
                    return True

            # 3연패 확인
            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                cps = self.tm.excel_trading_service.choice_pick_system
                if len(cps.pick_results) >= 3:
                    recent_three = cps.pick_results[-3:]
                    if all(not result for result in recent_three):
                        self.logger.info("3연패 감지 - 방 이동")
                        return True

            # 게임 수 제한 (55게임 이상)
            if actual_game_count >= 55:
                self.logger.info("게임 수 한계 도달 - 방 이동")
                return True

            return False
            
        except Exception as e:
            self.logger.error(f"방 이동 조건 확인 중 오류: {e}")
            return False

    def _should_place_bet(self, next_pick, previous_game_count):
        """베팅 조건 확인 - 단순화"""
        try:
            # 유효한 픽인지 확인
            if next_pick not in ['P', 'B']:
                return False

            # 이미 베팅했는지 확인
            if hasattr(self.tm, 'betting_service'):
                if self.tm.betting_service.has_bet_current_round:
                    return False

            # 첫 게임이 아닌지 확인
            if previous_game_count <= 0:
                return False

            return True
            
        except Exception as e:
            self.logger.error(f"베팅 조건 확인 중 오류: {e}")
            return False

    def _place_bet(self, next_pick, actual_game_count):
        """베팅 실행 - 단순화"""
        try:
            # UI 업데이트
            self.tm.main_window.update_betting_status(pick=next_pick)
            
            # 실제 베팅 수행
            if hasattr(self.tm, 'bet_helper'):
                self.tm.bet_helper.place_bet(next_pick, actual_game_count)
            else:
                self.logger.warning("BetHelper가 없어 베팅을 수행할 수 없습니다.")
                
        except Exception as e:
            self.logger.error(f"베팅 실행 중 오류: {e}")

    def process_previous_game_result(self, game_state, new_game_count):
        """이전 게임 결과 처리 - 단순화"""
        try:
            latest_result = game_state.get('latest_result')
            
            # 베팅 결과 처리
            if hasattr(self.tm, 'betting_service'):
                last_bet = self.tm.betting_service.get_last_bet()
                
                if last_bet and last_bet['type'] in ['P', 'B'] and latest_result:
                    # 베팅 결과 처리
                    if hasattr(self.tm, 'bet_helper'):
                        self.tm.bet_helper.process_bet_result(
                            last_bet['type'], 
                            latest_result, 
                            new_game_count
                        )

            # 베팅 상태 초기화 (타이가 아닌 경우)
            if latest_result != 'T':
                if hasattr(self.tm, 'betting_service'):
                    self.tm.betting_service.reset_betting_state(new_round=new_game_count)

        except Exception as e:
            self.logger.error(f"이전 게임 결과 처리 오류: {e}")

    def exit_current_game_room(self):
        """현재 게임방에서 나가기 - 단순화"""
        try:
            # UI 상태 업데이트
            if hasattr(self.tm.main_window, 'stop_button'):
                self.tm.main_window.stop_button.setEnabled(False)
                self.tm.main_window.update_button_styles()
            
            # 게임 모니터링 서비스를 통해 방 나가기
            if hasattr(self.tm, 'game_monitoring_service'):
                success = self.tm.game_monitoring_service.close_current_room()
                if success:
                    self.logger.info("게임방에서 나가기 완료")
                    return True
                else:
                    self.logger.warning("게임방 나가기 실패")
                    return False
            else:
                self.logger.warning("GameMonitoringService가 없습니다.")
                return False
                
        except Exception as e:
            self.logger.error(f"방 나가기 중 오류: {e}")
            return False

    def reset_room_state(self, preserve_martin=False):
        """방 이동 시 상태 초기화 - 단순화"""
        try:
            # 게임 정보 초기화
            self.tm.game_count = 0
            self.tm.result_count = 0
            
            # 베팅 상태 초기화
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.reset_betting_state()
            
            # 처리된 라운드 기록 초기화
            if hasattr(self.tm, 'processed_rounds'):
                self.tm.processed_rounds = set()
            
            # ChoicePickSystem 초기화
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.reset_after_room_change(preserve_martin)
            
            # 위젯 상태 초기화 (마틴 유지 여부에 따라)
            if not preserve_martin:
                if hasattr(self.tm.main_window, 'betting_widget'):
                    self.tm.main_window.betting_widget.room_position_counter = 0
                    if hasattr(self.tm.main_window.betting_widget, 'reset_step_markers'):
                        self.tm.main_window.betting_widget.reset_step_markers()
                self.logger.info("방 이동: 마틴 상태 초기화")
            else:
                self.logger.info("방 이동: 마틴 상태 유지")
            
            # 공통 상태 초기화
            self.tm.should_move_to_next_room = False
            if not preserve_martin:
                self.tm.current_pick = None
            
            self.logger.info(f"방 이동 시 상태 초기화 완료 (마틴 유지: {preserve_martin})")
            
        except Exception as e:
            self.logger.error(f"방 상태 초기화 중 오류: {e}")

    def handle_tie_result(self, latest_result, game_state):
        """무승부 결과 처리 - 단순화"""
        try:
            if latest_result == 'T' and self.tm.game_count > 0:
                self.logger.info("무승부(T) 감지 - 기존 픽 유지")
                
                # UI 업데이트만 수행
                if hasattr(self.tm.main_window, 'room_log_widget'):
                    self.tm.main_window.room_log_widget.set_current_room(
                        self.tm.current_room_name, 
                        is_new_visit=False
                    )
                
                # 게임 분석 재시작
                if hasattr(self.tm, 'analyze_current_game'):
                    self.tm.analyze_current_game()
                
                # 타이머 설정
                if hasattr(self.tm.main_window, 'set_remaining_time'):
                    self.tm.main_window.set_remaining_time(0, 0, 2)
                
        except Exception as e:
            self.logger.error(f"TIE 결과 처리 오류: {e}")