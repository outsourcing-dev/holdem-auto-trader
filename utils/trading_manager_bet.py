# utils/trading_manager_bet.py
import time
import logging
from PyQt6.QtWidgets import QApplication
from utils.settings_manager import SettingsManager

class TradingManagerBet:
    """TradingManager의 베팅 관련 기능 클래스"""

    def __init__(self, trading_manager):
        self.tm = trading_manager  # trading_manager 참조
        self.just_won = False
        self.logger = trading_manager.logger or logging.getLogger(__name__)
        
    def place_bet(self, pick_value, game_count):
        """
        베팅을 실행합니다. 설명서 기준: 3판 동안 마틴 베팅 진행
        
        Args:
            pick_value (str): 베팅할 타입 ('P' 또는 'B')
            game_count (int): 현재 게임 카운트
            
        Returns:
            bool: 베팅 성공 여부
        """
        try:
            # 설정 새로고침
            self.tm.refresh_settings()

            # 현재 잔액 확인
            balance = self.tm.balance_service.get_iframe_balance()
            if balance:
                # UI 업데이트
                self.tm.main_window.update_user_data(current_amount=balance)
                
                # 마틴 베팅 가능 잔액 확인
                if not self.tm.helpers.check_martin_balance(balance):
                    self.tm.stop_trading()
                    return False
                
                # 목표 금액 도달 확인
                if self.tm.balance_service.check_target_amount(balance):
                    self.logger.info("목표 금액 도달로 베팅을 중단합니다.")
                    return False

            # 원본 픽 값 저장
            original_pick = pick_value
            
            # 베팅 방향 적용하여 실제 베팅할 픽 결정
            actual_pick = self.tm.excel_trading_service.get_reverse_bet_pick(original_pick)
            
            # 베팅 금액 결정 (초이스 픽 시스템 사용)
            widget_pos = self.tm.main_window.betting_widget.room_position_counter
            bet_amount = self.tm.excel_trading_service.get_current_bet_amount(widget_position=widget_pos)
            
            # 베팅 금액 UI 표시
            self.tm.main_window.betting_widget.update_bet_amount(bet_amount)
            self.tm.main_window.update_betting_status(pick=original_pick, bet_amount=bet_amount)
            
            # 중지 버튼 활성화
            self.tm.main_window.stop_button.setEnabled(True)
            self.tm.main_window.update_button_styles()
            QApplication.processEvents()
            self.logger.info("베팅 전: 중지 버튼 활성화")

            # 실제 베팅 실행 (방향이 적용된 픽으로 베팅)
            bet_success = self.tm.betting_service.place_bet(
                actual_pick,  # 방향이 적용된 실제 베팅 픽
                self.tm.current_room_name,
                game_count,
                self.tm.is_trading_active,
                bet_amount
            )

            # UI에는 원본 PICK 값 저장
            self.tm.current_pick = original_pick

            if bet_success:
                # 베팅 성공 처리
                self.process_successful_bet(bet_amount)
            else:
                # 베팅 실패 시 UI 업데이트만
                self.logger.warning(f"베팅 실패했지만 PICK 값은 유지: {original_pick}")
                self.tm.main_window.update_betting_status(pick=original_pick)
                self.tm.main_window.stop_button.setEnabled(True)
                self.tm.main_window.update_button_styles()
                QApplication.processEvents()
                self.logger.info("베팅 실패: 중지 버튼 다시 활성화")

            return bet_success

        except Exception as e:
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            self.tm.main_window.stop_button.setEnabled(True)
            self.tm.main_window.update_button_styles()
            self.logger.info("베팅 오류: 중지 버튼 다시 활성화")
            return False
        
    def process_successful_bet(self, bet_amount):
        """
        성공적인 베팅 처리
        
        Args:
            bet_amount (int): 베팅 금액
        """
        try:
            # 누적 배팅 금액 업데이트
            if hasattr(self.tm.main_window, 'total_bet_amount'):
                self.tm.main_window.total_bet_amount += bet_amount
            else:
                self.tm.main_window.total_bet_amount = bet_amount
            
            # UI 업데이트
            self.tm.main_window.update_user_data(total_bet=self.tm.main_window.total_bet_amount)
            self.logger.info(f"누적 배팅 금액: {self.tm.main_window.total_bet_amount:,}원")
            
            if hasattr(self.tm.main_window, 'update_button_styles'):
                self.tm.main_window.update_button_styles()
            return True
        except Exception as e:
            self.logger.error(f"성공적인 베팅 처리 오류: {e}")
            return False


    def process_bet_result(self, bet_type, latest_result, new_game_count):
        """
        베팅 결과 처리
        
        Args:
            bet_type (str): 베팅 타입 ('P' 또는 'B')
            latest_result (str): 실제 게임 결과
            new_game_count (int): 새 게임 카운트
            
        Returns:
            str: 결과 상태 ('win', 'lose', 'tie', 'error')
        """
        try:
            # 베팅 타입 로깅
            actual_bet_type = bet_type
            self.logger.info(f"베팅 결과 확인: 베팅={actual_bet_type}, 결과={latest_result}")

            # 결과 상태 판단
            is_tie = (latest_result == 'T')
            is_win = (not is_tie and bet_type == latest_result)

            # 결과에 따른 처리
            if is_tie:
                # 무승부 처리
                result_marker = "T"
                result_status = "tie"
                self.tm.betting_service.has_bet_current_round = False
                self.tm.betting_service.reset_betting_state(new_round=new_game_count)
                self.logger.info("무승부 (T) 결과 - 베팅 상태 초기화")

            elif is_win:
                # 승리 처리
                result_marker = "O"
                result_status = "win"
                self.tm.main_window.update_betting_status(room_name=self.tm.current_room_name, reset_counter=True)

                if hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
                    self.tm.main_window.betting_widget.prevent_reset = False

                # 마커 표시 설정
                self.tm.main_window.betting_widget.set_step_marker(
                    self.tm.main_window.betting_widget.room_position_counter,
                    result_marker
                )
                self.tm.just_won = True
                
                # 초이스 픽 시스템에 승리 기록
                self.tm.excel_trading_service.record_betting_result(True)
                self.logger.info("베팅 적중 (O) - 초이스 픽 시스템에 승리 기록")
                
                # 승리 후 60게임 이상인지 확인
                if self.tm.game_count >= 57:
                    self.logger.info(f"승리 후 게임 수 확인: {self.tm.game_count}판 - 57판 이상으로 방 이동 필요")
                    self.tm.should_move_to_next_room = True

            else:
                # 패배 처리
                result_marker = "X"
                result_status = "lose"
                self.tm.main_window.update_betting_status(room_name=self.tm.current_room_name, reset_counter=False)
                
                # 마틴 단계 업데이트 기록 
                if hasattr(self.tm.martin_service, 'current_step'):
                    self.tm.current_martin_step = self.tm.martin_service.current_step
                    self.logger.info(f"[마틴 상태 캐시] 패배 후 현재 마틴 단계: {self.tm.current_martin_step+1}단계")
                    self.tm.excel_trading_service.choice_pick_system.martin_step = self.tm.martin_service.current_step

                if hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
                    self.tm.main_window.betting_widget.prevent_reset = True

                # 실패 마커 표시
                self.tm.main_window.betting_widget.set_step_marker(
                    self.tm.main_window.betting_widget.room_position_counter,
                    result_marker
                )
                
                # 초이스 픽 시스템에 패배 기록
                self.tm.excel_trading_service.record_betting_result(False)
                self.logger.info("베팅 실패 (X) - 초이스 픽 시스템에 패배 기록")

                # 3연패 확인 (여기서 바로 확인)
                if hasattr(self.tm.martin_service, 'recent_results'):
                    recent_results = self.tm.martin_service.recent_results
                    # 3연패 확인
                    if len(recent_results) >= 3 and all(not result for result in recent_results[-3:]):
                        self.logger.info("3연패 감지! 방 이동 플래그 설정")
                        self.tm.should_move_to_next_room = True

            # 결과 카운터 증가
            self.tm.result_count += 1
            
            # 방 이동 필요 여부 확인
            if self.tm.excel_trading_service.should_change_room() or (hasattr(self.tm.martin_service, 'should_change_room') and self.tm.martin_service.should_change_room()):
                self.logger.info("베팅 시스템 기준으로 방 이동 필요")
                self.tm.should_move_to_next_room = True
            
            # 방 로그 위젯 업데이트 (있는 경우)
            if hasattr(self.tm.main_window, 'room_log_widget'):
                self.tm.main_window.room_log_widget.set_current_room(
                    self.tm.current_room_name,
                    is_new_visit=not is_tie
                )
                self.tm.main_window.room_log_widget.add_bet_result(
                    room_name=self.tm.current_room_name,
                    is_win=is_win,
                    is_tie=is_tie
                )
            # 반환 전 TradingManager에 마틴 단계 최신값 저장
            if hasattr(self.tm.martin_service, 'current_step'):
                self.tm.current_martin_step = self.tm.martin_service.current_step

            return result_status

        except Exception as e:
            self.logger.error(f"베팅 결과 처리 오류: {e}", exc_info=True)
            return "error"
        
    def update_balance_after_result(self, is_win):
        """
        베팅 결과 후 잔액 업데이트
        
        Args:
            is_win (bool): 베팅 승리 여부
        """
        try:
            # 방 안에서 잔액 확인 시도 대신 로그만 남김
            self.logger.info("베팅 결과 확인됨. 방 이동 후 로비에서 잔액을 확인할 예정입니다.")
            
            # 목표 금액 확인은 방 이동 후에 진행
            if not hasattr(self.tm, 'check_balance_after_room_change'):
                self.tm.check_balance_after_room_change = True
                
        except Exception as e:
            self.logger.error(f"잔액 업데이트 플래그 설정 오류: {e}")