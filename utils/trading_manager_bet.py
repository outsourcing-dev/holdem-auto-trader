# utils/trading_manager_bet.py - 역배팅 및 Double/Half 동적 모드 개선
import time
import logging
from PyQt6.QtWidgets import QApplication
from utils.settings_manager import SettingsManager

class TradingManagerBet:
    """TradingManager의 베팅 관련 기능 클래스"""

    def __init__(self, trading_manager):
        self.tm = trading_manager  # trading_manager 참조
        self.logger = trading_manager.logger or logging.getLogger(__name__)

    def place_bet(self, pick_value, game_count):
        try:
            if self.tm.martin_service.has_bet_in_current_room:
                self.logger.info("현재 방에서 이미 배팅했으므로 방 이동 필요")
                self.tm.should_move_to_next_room = True
                return False

            self.tm.refresh_settings()

            balance = self.tm.balance_service.get_iframe_balance()
            if balance:
                self.tm.main_window.update_user_data(current_amount=balance)
                if not self.tm.helpers.check_martin_balance(balance):
                    self.tm.stop_trading()
                    return False
                if self.tm.balance_service.check_target_amount(balance):
                    self.logger.info("목표 금액 도달로 베팅을 중단합니다.")
                    return False

            original_pick = pick_value
            is_reverse_mode = self.tm.martin_service.reverse_betting
            self.logger.info(f"[역배팅] 현재 모드: {'역배팅' if is_reverse_mode else '정배팅'}")
            pick_value = self.tm.martin_service.get_reverse_bet_pick(pick_value)

            if original_pick != pick_value:
                self.logger.info(f"[역배팅] 원래 베팅: {original_pick} → 실제 베팅: {pick_value}")
                if hasattr(self.tm.main_window.betting_widget, 'update_reverse_mode'):
                    self.tm.main_window.betting_widget.update_reverse_mode(True)

            win = self.tm.martin_service.win_count
            lose = self.tm.martin_service.lose_count
            diff = abs(win - lose)
            base_bet_amount = self.tm.martin_service.get_current_bet_amount()
            final_bet_amount = base_bet_amount

            ms = self.tm.martin_service
            if not hasattr(ms, 'max_difference'):
                ms.max_difference = 0
                ms.trigger_point = 0
                ms.has_active_double_half = False
                ms.double_mode = False
                ms.half_mode = False

            self.logger.info(f"[Double/Half 상태] win: {win}, lose: {lose}, diff: {diff}, max_diff: {ms.max_difference}, trigger: {ms.trigger_point}, active: {ms.has_active_double_half}, double: {ms.double_mode}, half: {ms.half_mode}")

            # Double & Half 제어 로직
            if not ms.has_active_double_half:
                if diff >= 4:  # 실전에서는 4로 변경
                    if diff > ms.max_difference:
                        ms.max_difference = diff
                        ms.trigger_point = (diff + 1) // 2
                        self.logger.info(f"[Double/Half 갱신] max_difference: {ms.max_difference}, trigger_point: {ms.trigger_point}")

                    if diff == ms.trigger_point:
                        ms.has_active_double_half = True
                        if win > lose:
                            ms.half_mode = True
                            half_amount = max(1000, ((base_bet_amount // 2 + 999) // 1000) * 1000)
                            final_bet_amount = half_amount
                            self.logger.info(f"[Half 모드 시작] win: {win}, lose: {lose}, bet: {final_bet_amount}")
                            self.tm.main_window.betting_widget.update_mode("half")
                        elif lose > win:
                            ms.double_mode = True
                            final_bet_amount = base_bet_amount * 2
                            self.logger.info(f"[Double 모드 시작] win: {win}, lose: {lose}, bet: {final_bet_amount}")
                            self.tm.main_window.betting_widget.update_mode("double")

            else:
                if diff < ms.trigger_point:
                    self.logger.info(f"[모드 종료] diff < trigger_point ({diff} < {ms.trigger_point}), 초기화 진행")
                    ms.max_difference = 0
                    ms.trigger_point = 0
                    ms.has_active_double_half = False
                    ms.double_mode = False
                    ms.half_mode = False
                    final_bet_amount = base_bet_amount
                    self.tm.main_window.betting_widget.update_mode("normal")
                elif ms.double_mode:
                    final_bet_amount = base_bet_amount * 2
                    self.logger.info(f"[Double 모드 유지] bet: {final_bet_amount}")
                    self.tm.main_window.betting_widget.update_mode("double")
                elif ms.half_mode:
                    half_amount = max(1000, ((base_bet_amount // 2 + 999) // 1000) * 1000)
                    final_bet_amount = half_amount
                    self.logger.info(f"[Half 모드 유지] bet: {final_bet_amount}")
                    self.tm.main_window.betting_widget.update_mode("half")
                else:
                    self.logger.info("[모드 활성 상태인데 double/half 둘 다 꺼짐? 이상 상황")
                    self.tm.main_window.betting_widget.update_mode("normal")

            self.tm.main_window.betting_widget.update_bet_amount(final_bet_amount)
            self.tm.main_window.update_betting_status(pick=original_pick, bet_amount=final_bet_amount)
            self.tm.main_window.stop_button.setEnabled(True)
            self.tm.main_window.update_button_styles()
            QApplication.processEvents()
            self.logger.info("베팅 전: 중지 버튼 활성화")

            bet_success = self.tm.betting_service.place_bet(
                pick_value,
                self.tm.current_room_name,
                game_count,
                self.tm.is_trading_active,
                final_bet_amount
            )

            self.tm.current_pick = original_pick

            if bet_success:
                self.process_successful_bet(final_bet_amount)
            else:
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
        """성공적인 베팅 처리"""
        try:
            self.tm.martin_service.has_bet_in_current_room = True
            self.logger.info("베팅 성공: 한 방에서 한 번 배팅 완료 표시")
            
            # 중요: 베팅 성공 후 즉시 방 이동하지 않도록 플래그 초기화
            self.tm.should_move_to_next_room = False
            self.logger.info("베팅 후 결과를 기다리기 위해 방 이동 플래그 초기화")
            
            # 누적 배팅 금액 업데이트
            self.tm.martin_service.total_bet_amount += bet_amount
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
        
    # trading_manager_bet.py의 process_bet_result 메서드 수정 - 역배팅 지원
    def process_bet_result(self, bet_type, latest_result, new_game_count):
        """베팅 결과 처리 - 결과 표시 시 중지 버튼 비활성화 및 일시 정지 추가"""
        try:
            # 베팅한 실제 pick 값 확인
            actual_bet_type = bet_type
            
            # 역배팅 모드가 활성화되었는지 확인하고, 승패 판정 보정
            if self.tm.martin_service.reverse_betting:
                # 원래 PICK(UI에 표시된 PICK)을 가져오기
                original_pick = self.tm.martin_service.original_pick
                if original_pick:
                    self.logger.info(f"[역배팅] 원래 의도한 PICK: {original_pick}, 실제 베팅한 PICK: {bet_type}")
                else:
                    self.logger.info(f"[역배팅] 역배팅 모드로 베팅: {bet_type}")
            
            # 결과 판정
            is_tie = (latest_result == 'T')
            is_win = (not is_tie and bet_type == latest_result)
            
            # 중지 버튼 비활성화 (결과 확인 시작) - 추가된 부분
            self.tm.main_window.stop_button.setEnabled(False)
            self.tm.main_window.update_button_styles()
            self.logger.info("결과 확인 중: 중지 버튼 비활성화됨")
            
            # 역배팅 모드가 활성화된 경우 승패 상태 로그 추가
            if self.tm.martin_service.reverse_betting:
                self.logger.info(f"[역배팅] 결과 판정 - 타이: {is_tie}, 승리: {is_win}, 결과: {latest_result}")
            
            # 결과 설정
            if is_tie:
                result_text = "무승부"
                result_marker = "T"
                result_status = "tie"
                # 타이 결과는 배팅 상태 초기화 및 방 이동 안함
                self.tm.betting_service.has_bet_current_round = False
                self.tm.betting_service.reset_betting_state(new_round=new_game_count)
                self.tm.should_move_to_next_room = False
                self.logger.info("타이(T) 결과: 같은 방에서 재시도")

            elif is_win:
                self.logger.info("승리: 마커 표시 후 초기화 예정")
                result_text = "적중"
                result_marker = "O"
                result_status = "win"
                # 승리 시 방 이동
                self.tm.should_move_to_next_room = True
                self.logger.info("배팅 성공: 방 이동 필요")
                # 성공 시에는 reset_counter=True 전달
                self.tm.main_window.update_betting_status(room_name=self.tm.current_room_name, reset_counter=True)
            else:
                result_text = "실패"
                result_marker = "X"
                result_status = "lose"
                # 실패 시도 방 이동
                self.tm.should_move_to_next_room = True
                self.logger.info("베팅 실패: 방 이동 필요")
                self.tm.main_window.update_betting_status(room_name=self.tm.current_room_name, reset_counter=False)
            
            # 결과 카운트 증가
            self.tm.result_count += 1
            
            # 마틴 베팅 단계 업데이트
            result = self.tm.martin_service.process_bet_result(
                result_status, 
                game_count=self.tm.game_count
            )
            
            current_step, consecutive_losses, result_position = result
            
            # 베팅 위젯에 결과 표시
            self.tm.main_window.betting_widget.set_step_marker(result_position, result_marker)
            
            # 승리 시 마틴 단계를 즉시 초기화 (방 이동 전에)
            if is_win:
                self.logger.info("승리 감지: 마틴 단계 즉시 초기화 (방 이동 전)")
                self.tm.martin_service.current_step = 0
                self.tm.martin_service.consecutive_losses = 0
            
            # 방 로그 위젯에 결과 추가
            if hasattr(self.tm.main_window, 'room_log_widget'):
                # 수정: 승리든 무승부든 상관없이 set_current_room 호출
                # TIE의 경우 is_new_visit=False로 설정하여 방 이동 없음을 표시
                # 승리/실패 시 is_new_visit=True로 설정하여 새 방문 표시
                is_new_visit = not is_tie
                self.tm.main_window.room_log_widget.set_current_room(
                    self.tm.current_room_name, 
                    is_new_visit=is_new_visit
                )
                    
                self.tm.main_window.room_log_widget.add_bet_result(
                    room_name=self.tm.current_room_name,
                    is_win=is_win,
                    is_tie=is_tie
                )
            
            # 결과 확인을 위한 지연 추가 - 추가된 부분
            self.logger.info(f"결과 확인 대기: {result_text} (3초)")
            time.sleep(3)  # 3초 동안 결과 확인을 위해 대기
            
            # 잔액 업데이트 및 목표 금액 확인
            self.update_balance_after_result(is_win)
            
            # 중요 변경 부분: 승리 시 지연된 리셋 처리
            if is_win and hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
                # 이제 마커가 표시된 후에 prevent_reset 플래그를 False로 설정
                self.tm.main_window.betting_widget.prevent_reset = False
                self.logger.info("승리 마커 표시 완료: 이제 위젯 초기화 허용")
            
            # 중요: 로그 추가 - 결과와 방 이동 플래그 상태를 기록
            self.logger.info(f"베팅 결과: {result_status}, 방 이동 플래그: {self.tm.should_move_to_next_room}")
            
            # 결과 확인 후에도 중지 버튼은 비활성화 상태 유지 (방 이동 또는 새 베팅 시 활성화)
            # 중지 버튼은 비활성화 상태 유지
            self.tm.main_window.stop_button.setEnabled(False)
            self.tm.main_window.update_button_styles()
            self.logger.info("결과 확인 후: 중지 버튼 비활성화 상태 유지")
            
            return result_status
        except Exception as e:
            self.logger.error(f"베팅 결과 처리 오류: {e}", exc_info=True)
            return "error"
        
    def update_balance_after_result(self, is_win):
        """베팅 결과 후 잔액 업데이트 - 방 로비에서만 확인하도록 수정"""
        try:
            # 방 안에서 잔액 확인 시도를 제거하고 대신 로그만 남김
            self.logger.info("베팅 결과 확인됨. 방 이동 후 로비에서 잔액을 확인할 예정입니다.")
            
            # 목표 금액 확인은 방 이동 후에 진행되도록 플래그 설정
            if not hasattr(self.tm, 'check_balance_after_room_change'):
                self.tm.check_balance_after_room_change = True
                
        except Exception as e:
            self.logger.error(f"잔액 업데이트 플래그 설정 오류: {e}")