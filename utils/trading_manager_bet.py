# utils/trading_manager_bet.py (서버 기반으로 단순화)
import time
import logging
from PyQt6.QtWidgets import QApplication
from utils.settings_manager import SettingsManager

class TradingManagerBet:
    """TradingManager의 베팅 관련 기능 클래스 - 서버 기반으로 단순화"""

    def __init__(self, trading_manager):
        self.tm = trading_manager  # trading_manager 참조
        self.just_won = False
        self.logger = trading_manager.logger or logging.getLogger(__name__)
        self.logger.info("단순화된 TradingManagerBet 초기화")
        
    def place_bet(self, pick_value, game_count):
        """베팅 실행 - 단순화"""
        try:
            # 기본 유효성 검사
            if not self._validate_bet_conditions(pick_value):
                return False

            # 잔액 확인
            if not self._check_balance_before_bet():
                return False

            # 베팅 금액 계산
            bet_amount = self._calculate_bet_amount()
            if bet_amount <= 0:
                self.logger.error("베팅 금액 계산 실패")
                return False

            # UI 업데이트
            self._update_ui_before_bet(pick_value, bet_amount)

            # 실제 베팅 수행 (서버 기반에서는 정배팅만 사용)
            bet_success = self.tm.betting_service.place_bet(
                pick_value,  # 서버에서 이미 분석된 픽 그대로 사용
                self.tm.current_room_name,
                game_count,
                self.tm.is_trading_active,
                bet_amount
            )

            # 결과 처리
            if bet_success:
                self._handle_successful_bet(pick_value, bet_amount)
            else:
                self._handle_failed_bet(pick_value)

            return bet_success

        except Exception as e:
            self.logger.error(f"베팅 중 오류: {e}")
            self._restore_ui_after_error()
            return False

    def _validate_bet_conditions(self, pick_value):
        """베팅 조건 검증 - 단순화"""
        try:
            # 픽 값 유효성 확인
            if pick_value not in ['P', 'B']:
                self.logger.warning(f"유효하지 않은 픽 값: {pick_value}")
                return False

            # 첫 결과 대기 모드 확인
            if getattr(self.tm, 'wait_first_result', False):
                self.logger.info("첫 결과 대기 중 - 베팅 보류")
                return False

            # 트레이딩 활성 상태 확인
            if not self.tm.is_trading_active:
                self.logger.warning("트레이딩이 비활성 상태")
                return False

            return True

        except Exception as e:
            self.logger.error(f"베팅 조건 검증 중 오류: {e}")
            return False

    def _check_balance_before_bet(self):
        """베팅 전 잔액 확인 - 단순화"""
        try:
            # iframe에서 잔액 확인
            balance = self.tm.balance_service.get_iframe_balance()
            
            if balance is None:
                self.logger.warning("잔액 확인 실패")
                return True  # 잔액 확인 실패 시에도 베팅 진행 (개발 환경 고려)

            # UI 잔액 업데이트
            self.tm.main_window.update_user_data(current_amount=balance)
            
            # 마틴 잔액 확인
            if not self.tm.helpers.check_martin_balance(balance):
                self.tm.stop_trading()
                return False

            # 목표 금액 달성 확인
            if self.tm.balance_service.check_target_amount(balance):
                self.logger.info("목표 금액 달성 - 트레이딩 중단")
                self.tm.stop_trading()
                return False

            return True

        except Exception as e:
            self.logger.error(f"잔액 확인 중 오류: {e}")
            return True  # 오류 시에도 베팅 진행

    def _calculate_bet_amount(self):
        """베팅 금액 계산 - 단순화"""
        try:
            # 현재 위젯 포지션 확인
            widget_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
            
            # ExcelTradingService를 통해 베팅 금액 계산
            bet_amount = self.tm.excel_trading_service.get_current_bet_amount(widget_position=widget_pos)
            
            self.logger.info(f"베팅 금액 계산: 위젯 위치 {widget_pos+1}, 금액 {bet_amount:,}원")
            
            return bet_amount

        except Exception as e:
            self.logger.error(f"베팅 금액 계산 중 오류: {e}")
            return 1000  # 기본 금액

    def _update_ui_before_bet(self, pick_value, bet_amount):
        """베팅 전 UI 업데이트 - 단순화"""
        try:
            # 베팅 금액 UI 업데이트
            if hasattr(self.tm.main_window, 'betting_widget'):
                self.tm.main_window.betting_widget.update_bet_amount(bet_amount)

            # 베팅 상태 UI 업데이트
            self.tm.main_window.update_betting_status(pick=pick_value, bet_amount=bet_amount)

            # 중지 버튼 활성화
            if hasattr(self.tm.main_window, 'stop_button'):
                self.tm.main_window.stop_button.setEnabled(True)
                self.tm.main_window.update_button_styles()

            # UI 이벤트 처리
            QApplication.processEvents()

        except Exception as e:
            self.logger.error(f"베팅 전 UI 업데이트 중 오류: {e}")

    def _handle_successful_bet(self, pick_value, bet_amount):
        """성공적인 베팅 처리 - 단순화"""
        try:
            # 현재 픽 저장
            self.tm.current_pick = pick_value
            
            # 누적 배팅 금액 업데이트
            self._update_total_bet_amount(bet_amount)
            
            self.logger.info(f"베팅 성공: {pick_value}, 금액: {bet_amount:,}원")

        except Exception as e:
            self.logger.error(f"성공적인 베팅 처리 중 오류: {e}")

    def _handle_failed_bet(self, pick_value):
        """실패한 베팅 처리 - 단순화"""
        try:
            self.logger.warning(f"베팅 실패: {pick_value}")
            
            # UI 상태 복원
            self.tm.main_window.update_betting_status(pick=pick_value)
            
            if hasattr(self.tm.main_window, 'stop_button'):
                self.tm.main_window.stop_button.setEnabled(True)
                self.tm.main_window.update_button_styles()

            QApplication.processEvents()

        except Exception as e:
            self.logger.error(f"실패한 베팅 처리 중 오류: {e}")

    def _update_total_bet_amount(self, bet_amount):
        """누적 베팅 금액 업데이트"""
        try:
            if hasattr(self.tm.main_window, 'total_bet_amount'):
                self.tm.main_window.total_bet_amount += bet_amount
            else:
                self.tm.main_window.total_bet_amount = bet_amount
            
            # UI 업데이트
            self.tm.main_window.update_user_data(total_bet=self.tm.main_window.total_bet_amount)
            
            self.logger.info(f"누적 배팅 금액: {self.tm.main_window.total_bet_amount:,}원")

        except Exception as e:
            self.logger.error(f"누적 배팅 금액 업데이트 중 오류: {e}")

    def _restore_ui_after_error(self):
        """오류 후 UI 상태 복원"""
        try:
            if hasattr(self.tm.main_window, 'stop_button'):
                self.tm.main_window.stop_button.setEnabled(True)
                self.tm.main_window.update_button_styles()

        except Exception as e:
            self.logger.error(f"UI 복원 중 오류: {e}")

    def process_bet_result(self, bet_type, latest_result, new_game_count):
        """베팅 결과 처리 - 단순화"""
        try:
            self.logger.info(f"베팅 결과 처리: 베팅={bet_type}, 결과={latest_result}")

            # 결과 상태 판단
            result_status = self._determine_result_status(bet_type, latest_result)
            
            # 결과에 따른 처리
            if result_status == "tie":
                self._handle_tie_result(new_game_count)
            elif result_status == "win":
                self._handle_win_result(new_game_count)
            elif result_status == "lose":
                self._handle_lose_result(new_game_count)

            # 공통 후처리
            self._post_process_result(result_status, new_game_count)

            return result_status

        except Exception as e:
            self.logger.error(f"베팅 결과 처리 오류: {e}")
            return "error"

    def _determine_result_status(self, bet_type, latest_result):
        """결과 상태 판단 - 단순화"""
        try:
            if latest_result == 'T':
                return "tie"
            elif bet_type == latest_result:
                return "win"
            else:
                return "lose"
        except Exception as e:
            self.logger.error(f"결과 상태 판단 중 오류: {e}")
            return "error"

    def _handle_tie_result(self, new_game_count):
        """무승부 결과 처리 - 단순화"""
        try:
            self.logger.info("무승부 처리")
            
            # 베팅 상태 초기화
            self.tm.betting_service.has_bet_current_round = False
            self.tm.betting_service.reset_betting_state(new_round=new_game_count)
            
            # 무승부 후 상태 설정
            self.tm.had_tie_last_round = True

        except Exception as e:
            self.logger.error(f"무승부 처리 중 오류: {e}")

    def _handle_win_result(self, new_game_count):
        """승리 결과 처리 - 단순화"""
        try:
            self.logger.info("승리 처리")
            
            # 위젯 마커 및 카운터 초기화
            self._reset_widget_after_win()
            
            # 시스템 상태 초기화
            self._reset_systems_after_win()
            
            # UI 업데이트
            self._update_ui_after_win()
            
            # 승리 플래그 설정
            self.tm.just_won = True
            
            # 방 이동 조건 확인
            if self.tm.game_count >= 55:
                self.logger.info("승리 후 55게임 도달 - 방 이동 필요")
                self.tm.should_move_to_next_room = True

        except Exception as e:
            self.logger.error(f"승리 처리 중 오류: {e}")

    def _handle_lose_result(self, new_game_count):
        """패배 결과 처리 - 단순화"""
        try:
            self.logger.info("패배 처리")
            
            # 위젯 마커 및 카운터 업데이트
            self._update_widget_after_lose()
            
            # 시스템에 패배 기록
            self._record_lose_in_systems()
            
            # 연패 확인 및 방 이동 조건 확인
            if self._check_consecutive_losses():
                self.logger.info("연패 조건 달성 - 방 이동 필요")
                self.tm.should_move_to_next_room = True

        except Exception as e:
            self.logger.error(f"패배 처리 중 오류: {e}")

    def _reset_widget_after_win(self):
        """승리 후 위젯 초기화"""
        try:
            if hasattr(self.tm.main_window, 'betting_widget'):
                widget = self.tm.main_window.betting_widget
                
                # 승리 마커 표시
                current_pos = getattr(widget, 'room_position_counter', 0)
                widget.set_step_marker(current_pos, "O")
                
                # 위젯 초기화
                widget.reset_step_markers()
                widget.room_position_counter = 0
                
                self.logger.info("승리 후 위젯 초기화 완료")

        except Exception as e:
            self.logger.error(f"승리 후 위젯 초기화 중 오류: {e}")

    def _reset_systems_after_win(self):
        """승리 후 시스템 상태 초기화"""
        try:
            # ExcelTradingService에 승리 기록
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.record_betting_result(True)
            
            # 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset_after_win()
            
            # 상태 플래그 초기화
            self.tm.had_tie_last_round = False
            if hasattr(self.tm, 'wait_first_result'):
                self.tm.wait_first_result = False

            self.logger.info("승리 후 시스템 상태 초기화 완료")

        except Exception as e:
            self.logger.error(f"승리 후 시스템 초기화 중 오류: {e}")

    def _update_ui_after_win(self):
        """승리 후 UI 업데이트"""
        try:
            # 베팅 상태 UI 업데이트 (카운터 리셋)
            self.tm.main_window.update_betting_status(
                room_name=self.tm.current_room_name,
                reset_counter=True,
                pick=None
            )

        except Exception as e:
            self.logger.error(f"승리 후 UI 업데이트 중 오류: {e}")

    def _update_widget_after_lose(self):
        """패배 후 위젯 업데이트"""
        try:
            if hasattr(self.tm.main_window, 'betting_widget'):
                widget = self.tm.main_window.betting_widget
                
                # 현재 위치에 패배 마커 표시
                current_pos = getattr(widget, 'room_position_counter', 0)
                widget.set_step_marker(current_pos, "X")
                
                # 다음 마틴 단계로 카운터 증가
                widget.room_position_counter = current_pos + 1
                
                self.logger.info(f"패배 마커 표시 및 카운터 증가: {current_pos} → {current_pos + 1}")

        except Exception as e:
            self.logger.error(f"패배 후 위젯 업데이트 중 오류: {e}")

    def _record_lose_in_systems(self):
        """시스템에 패배 기록"""
        try:
            # ExcelTradingService에 패배 기록
            if hasattr(self.tm, 'excel_trading_service'):
                self.tm.excel_trading_service.record_betting_result(False)
            
            # 마틴 서비스에 패배 기록
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.record_loss()
            
            # 상태 플래그 초기화
            self.tm.had_tie_last_round = False

            self.logger.info("시스템에 패배 기록 완료")

        except Exception as e:
            self.logger.error(f"패배 기록 중 오류: {e}")

    def _check_consecutive_losses(self):
        """연패 확인 - 단순화"""
        try:
            # ExcelTradingService를 통한 방 이동 조건 확인
            if hasattr(self.tm, 'excel_trading_service'):
                return self.tm.excel_trading_service.should_change_room()
            
            return False

        except Exception as e:
            self.logger.error(f"연패 확인 중 오류: {e}")
            return False

    def _post_process_result(self, result_status, new_game_count):
        """결과 처리 후 공통 작업"""
        try:
            # 결과 카운터 증가
            self.tm.result_count += 1
            
            # 베팅 상태 초기화 (타이가 아닌 경우)
            if result_status != "tie":
                self.tm.betting_service.has_bet_current_round = False
            
            # 방 로그 업데이트
            self._update_room_log(result_status)

        except Exception as e:
            self.logger.error(f"결과 후처리 중 오류: {e}")

    def _update_room_log(self, result_status):
        """방 로그 업데이트 - 단순화"""
        try:
            if hasattr(self.tm.main_window, 'room_log_widget'):
                # 현재 방 설정
                self.tm.main_window.room_log_widget.set_current_room(
                    self.tm.current_room_name,
                    is_new_visit=False
                )
                
                # 결과 추가
                is_win = (result_status == "win")
                is_tie = (result_status == "tie")
                
                self.tm.main_window.room_log_widget.add_bet_result(
                    room_name=self.tm.current_room_name,
                    is_win=is_win,
                    is_tie=is_tie
                )
                
                self.logger.debug(f"방 로그 업데이트: 승리={is_win}, 무승부={is_tie}")

        except Exception as e:
            self.logger.error(f"방 로그 업데이트 중 오류: {e}")

    def update_balance_after_result(self, is_win):
        """베팅 결과 후 잔액 업데이트 - 단순화"""
        try:
            # 방 이동 후 잔액 확인 플래그 설정
            self.tm.check_balance_after_room_change = True
            
            self.logger.info("방 이동 후 잔액 확인 예약")

        except Exception as e:
            self.logger.error(f"잔액 업데이트 플래그 설정 오류: {e}")