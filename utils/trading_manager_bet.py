# utils/trading_manager_bet.py - 역배팅 기능 추가
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
        """베팅 실행"""
        try:
            # 현재 방에서 이미 배팅한 경우 즉시 방 이동
            if self.tm.martin_service.has_bet_in_current_room:
                self.logger.info("현재 방에서 이미 배팅했으므로 방 이동 필요")
                self.tm.should_move_to_next_room = True
                return False
            
            # 최신 설정 가져오기 - 매 베팅마다 설정 파일 다시 읽기
            self.tm.refresh_settings()
            
            # 잔액 확인 및 목표 금액 체크
            balance = self.tm.balance_service.get_iframe_balance()
            if balance:
                # 현재 잔액 업데이트
                self.tm.main_window.update_user_data(current_amount=balance)
                
                # 마틴 배팅을 위한 잔고 확인
                if not self.tm.helpers.check_martin_balance(balance):
                    self.tm.stop_trading()
                    return False
                
                # 목표 금액 체크
                if self.tm.balance_service.check_target_amount(balance):
                    self.logger.info("목표 금액 도달로 베팅을 중단합니다.")
                    return False
            
            # 역배팅 모드 확인 및 PICK 값 조정
            original_pick = pick_value
            
            # 역배팅 모드 상태 출력
            is_reverse_mode = self.tm.martin_service.reverse_betting
            self.logger.info(f"[역배팅] 현재 모드: {'역배팅' if is_reverse_mode else '정배팅'}")
            
            # 역배팅 모드에 따라 PICK 값 조정
            pick_value = self.tm.martin_service.get_reverse_bet_pick(pick_value)
            
            # 원래 PICK과 실제 베팅 PICK이 다른 경우 로그 출력
            if original_pick != pick_value:
                self.logger.info(f"[역배팅] 원래 베팅: {original_pick} → 실제 베팅: {pick_value}")
                
                # UI에 역배팅 모드 표시 (있다면)
                if hasattr(self.tm.main_window.betting_widget, 'update_reverse_mode'):
                    self.tm.main_window.betting_widget.update_reverse_mode(True)
            
            # Double & Half 설정 가져오기 - 최신 설정 적용
            double_half_start, double_half_stop = self.tm.settings_manager.get_double_half_settings()

            # 활성화 상태 확인 - start 값이 1 이상인 경우만 기능 활성화
            use_double_half = double_half_start > 0
            self.logger.info(f"Double & Half 기능: {'활성화' if use_double_half else '비활성화'} (시작값: {double_half_start}, 중지값: {double_half_stop})")

            # 현재 승패 통계 가져오기
            win_count = self.tm.martin_service.win_count
            lose_count = self.tm.martin_service.lose_count
            win_lose_diff = win_count - lose_count  # 승-패 차이
            lose_win_diff = lose_count - win_count  # 패-승 차이

            # 기본 마틴 베팅 금액 가져오기
            base_bet_amount = self.tm.martin_service.get_current_bet_amount()
            final_bet_amount = base_bet_amount  # 기본값으로 시작

            # 모드 확인 (없으면 초기화)
            if not hasattr(self.tm.martin_service, 'double_mode'):
                self.tm.martin_service.double_mode = False
            if not hasattr(self.tm.martin_service, 'half_mode'):
                self.tm.martin_service.half_mode = False

            # Double & Half 로직 적용 (활성화된 경우만)
            if use_double_half:
                self.logger.info(f"현재 승패 상황: {win_count}승 {lose_count}패 (승-패: {win_lose_diff}, 패-승: {lose_win_diff})")
                self.logger.info(f"현재 모드: {'Double 모드' if self.tm.martin_service.double_mode else ''}{'Half 모드' if self.tm.martin_service.half_mode else ''}{'기본 모드' if not (self.tm.martin_service.double_mode or self.tm.martin_service.half_mode) else ''}")
                
                # 모드 전환 로직
                if self.tm.martin_service.double_mode:
                    # Double 모드 중 중지값 확인 (중지값에 도달하면 모드 해제)
                    if lose_win_diff <= double_half_stop:
                        self.tm.martin_service.double_mode = False
                        self.logger.info(f"Double 모드 해제: 패-승({lose_win_diff}) <= {double_half_stop}, 기본 마틴 금액으로 복귀")
                        # UI 업데이트 - 모드 해제 반영
                        self.tm.main_window.betting_widget.update_mode("normal")
                    else:
                        # Double 모드 유지 - 마틴 베팅 금액의 2배 적용
                        final_bet_amount = base_bet_amount * 2
                        self.logger.info(f"Double 모드 유지: 패-승({lose_win_diff}), 베팅 금액 2배 적용 ({base_bet_amount:,}원 → {final_bet_amount:,}원)")
                        # UI 업데이트 - Double 모드 유지 반영
                        self.tm.main_window.betting_widget.update_mode("double")
                
                elif self.tm.martin_service.half_mode:
                    # Half 모드 중 중지값 확인 (중지값에 도달하면 모드 해제)
                    if win_lose_diff <= double_half_stop:
                        self.tm.martin_service.half_mode = False
                        self.logger.info(f"Half 모드 해제: 승-패({win_lose_diff}) <= {double_half_stop}, 기본 마틴 금액으로 복귀")
                        # UI 업데이트 - 모드 해제 반영
                        self.tm.main_window.betting_widget.update_mode("normal")
                    else:
                        # Half 모드 유지 - 마틴 베팅 금액의 1/2 적용 (최소 1000원, 천원 단위 올림)
                        half_amount = max(1000, base_bet_amount // 2)
                        if half_amount % 1000 != 0:
                            # 천원 단위 올림
                            half_amount = ((half_amount // 1000) + 1) * 1000
                        
                        final_bet_amount = half_amount
                        self.logger.info(f"Half 모드 유지: 승-패({win_lose_diff}), 베팅 금액 1/2 적용 ({base_bet_amount:,}원 → {final_bet_amount:,}원)")
                        # UI 업데이트 - Half 모드 유지 반영
                        self.tm.main_window.betting_widget.update_mode("half")
                
                else:
                    # 기본 모드 - 모드 진입 여부 확인
                    
                    # 승-패 차이가 시작 값 이상인 경우 Half 모드 진입
                    if win_lose_diff >= double_half_start:
                        self.tm.martin_service.half_mode = True
                        
                        # 마틴 베팅 금액의 1/2 (최소 1000원, 천원 단위 올림)
                        half_amount = max(1000, base_bet_amount // 2)
                        if half_amount % 1000 != 0:
                            # 천원 단위 올림
                            half_amount = ((half_amount // 1000) + 1) * 1000
                        
                        final_bet_amount = half_amount
                        self.logger.info(f"Half 모드 진입: 승-패({win_lose_diff}) ≥ {double_half_start}, 베팅 금액 1/2로 감소 ({base_bet_amount:,}원 → {final_bet_amount:,}원)")
                        # UI 업데이트 - Half 모드 진입 반영
                        self.tm.main_window.betting_widget.update_mode("half")
                    
                    # 패-승 차이가 시작 값 이상인 경우 Double 모드 진입
                    elif lose_win_diff >= double_half_start:
                        self.tm.martin_service.double_mode = True
                        
                        # 마틴 베팅 금액의 2배
                        double_amount = base_bet_amount * 2
                        
                        final_bet_amount = double_amount
                        self.logger.info(f"Double 모드 진입: 패-승({lose_win_diff}) ≥ {double_half_start}, 베팅 금액 2배로 증가 ({base_bet_amount:,}원 → {final_bet_amount:,}원)")
                        # UI 업데이트 - Double 모드 진입 반영
                        self.tm.main_window.betting_widget.update_mode("double")
                    
                    else:
                        # 기본 모드 유지
                        self.logger.info(f"기본 모드 유지: 기본 마틴 금액 사용 ({base_bet_amount:,}원)")
                        # UI 업데이트 - 기본 모드 유지 반영
                        self.tm.main_window.betting_widget.update_mode("normal")
            else:
                # Double & Half 기능이 비활성화된 경우
                self.logger.info(f"Double & Half 기능 비활성화 상태, 기본 마틴 금액 사용: {base_bet_amount:,}원")
                # UI 업데이트 - 기본 모드 표시
                self.tm.main_window.betting_widget.update_mode("normal")
                
                # 모드 초기화 (Double & Half가 비활성화되었으므로)
                self.tm.martin_service.double_mode = False
                self.tm.martin_service.half_mode = False

            # UI에 현재 배팅 금액 업데이트
            self.tm.main_window.betting_widget.update_bet_amount(final_bet_amount)
            
            # UI 업데이트 - 여기서 원래 PICK 값을 표시 (사용자에게는 원래 의도한 선택 표시)
            self.tm.main_window.update_betting_status(
                pick=original_pick, 
                bet_amount=final_bet_amount
            )
            
            # 베팅 전 버튼 활성화
            self.tm.main_window.stop_button.setEnabled(True)
            self.tm.main_window.update_button_styles()
            QApplication.processEvents()  # 이벤트 처리 강제
            self.logger.info("베팅 전: 중지 버튼 활성화")
            
            if hasattr(self.tm.main_window, 'update_button_styles'):
                self.tm.main_window.update_button_styles()

            # 베팅 실행 - 변경된 pick_value 사용 (역배팅 모드에 따라 반전됨)
            bet_success = self.tm.betting_service.place_bet(
                pick_value, 
                self.tm.current_room_name, 
                game_count, 
                self.tm.is_trading_active,
                final_bet_amount
            )
            
            # 현재 베팅 타입 저장 - 원래 PICK 값 저장
            self.tm.current_pick = original_pick
            
            # 베팅 성공 시 처리
            if bet_success:
                self.process_successful_bet(final_bet_amount)
            else:
                # 베팅 실패 시에도 PICK 값은 UI에 표시 (원래 PICK 값 표시)
                self.logger.warning(f"베팅 실패했지만 PICK 값은 유지: {original_pick}")
                self.tm.main_window.update_betting_status(pick=original_pick)
                
                # 베팅 실패 시 중지 버튼 다시 활성화 - 추가된 부분
                self.tm.main_window.stop_button.setEnabled(True)
                self.tm.main_window.update_button_styles()
                QApplication.processEvents()  # 이벤트 처리 강제
                self.logger.info("베팅 실패: 중지 버튼 다시 활성화")
            
            return bet_success
        
        except Exception as e:
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            
            # 오류 발생 시 중지 버튼 다시 활성화 - 추가된 부분
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