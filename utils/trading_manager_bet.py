# utils/trading_manager_bet.py
import time
import logging
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
            
            # 마틴 설정 갱신
            self.tm.martin_service.settings_manager = SettingsManager()
            self.tm.martin_service.update_settings()
            
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
            
            
            # Double & Half 설정 가져오기
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
                    if lose_win_diff == double_half_stop:
                        self.tm.martin_service.double_mode = False
                        self.logger.info(f"Double 모드 해제: 패-승({lose_win_diff}) = {double_half_stop}, 기본 마틴 금액으로 복귀")
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
                    if win_lose_diff == double_half_stop:
                        self.tm.martin_service.half_mode = False
                        self.logger.info(f"Half 모드 해제: 승-패({win_lose_diff}) = {double_half_stop}, 기본 마틴 금액으로 복귀")
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

            # UI에 현재 배팅 금액 업데이트
            self.tm.main_window.betting_widget.update_bet_amount(final_bet_amount)
            
            # UI 업데이트
            self.tm.main_window.update_betting_status(
                pick=pick_value, 
                bet_amount=final_bet_amount
            )
            
            # 베팅 실행
            bet_success = self.tm.betting_service.place_bet(
                pick_value, 
                self.tm.current_room_name, 
                game_count, 
                self.tm.is_trading_active,
                final_bet_amount
            )
            
            # 현재 베팅 타입 저장
            self.tm.current_pick = pick_value
            
            # 베팅 성공 시 처리
            if bet_success:
                self.process_successful_bet(final_bet_amount)
            else:
                # 베팅 실패 시에도 PICK 값은 UI에 표시
                self.logger.warning(f"베팅 실패했지만 PICK 값은 유지: {pick_value}")
                self.tm.main_window.update_betting_status(pick=pick_value)
            
            return bet_success
        
        except Exception as e:
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
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
            
            return True
        except Exception as e:
            self.logger.error(f"성공적인 베팅 처리 오류: {e}")
            return False
        
    # trading_manager_bet.py의 process_bet_result 메서드 수정

    def process_bet_result(self, bet_type, latest_result, new_game_count):
        """베팅 결과 처리"""
        try:
            # 결과 판정
            is_tie = (latest_result == 'T')
            is_win = (not is_tie and bet_type == latest_result)
            
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
                # 변경된 부분: prevent_reset 플래그 상태를 아직 유지
                # if hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
                #     self.tm.main_window.betting_widget.prevent_reset = False
                #     self.tm.main_window.betting_widget.reset_step_markers()
                #     self.tm.main_window.betting_widget.reset_room_results()
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
            
            # 잔액 업데이트 및 목표 금액 확인
            self.update_balance_after_result(is_win)
            
            # 중요 변경 부분: 승리 시 지연된 리셋 처리
            if is_win and hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
                # 이제 마커가 표시된 후에 prevent_reset 플래그를 False로 설정
                self.tm.main_window.betting_widget.prevent_reset = False
                self.logger.info("승리 마커 표시 완료: 이제 위젯 초기화 허용")
            
            # 중요: 로그 추가 - 결과와 방 이동 플래그 상태를 기록
            self.logger.info(f"베팅 결과: {result_status}, 방 이동 플래그: {self.tm.should_move_to_next_room}")
            
            return result_status
        except Exception as e:
            self.logger.error(f"베팅 결과 처리 오류: {e}", exc_info=True)
            return "error"
        
    def update_balance_after_result(self, is_win):
        """베팅 결과 후 잔액 업데이트"""
        try:
            current_balance = None
            
            # 잔액 확인 시도 1: balance_service 사용
            current_balance = self.tm.balance_service.update_balance_after_bet_result(is_win=is_win)
            
            # 잔액 확인 시도 2: iframe 직접 확인
            if current_balance is None:
                self.logger.warning("잔액 업데이트 1차 실패, 2차 시도...")
                current_balance = self.tm.balance_service.get_iframe_balance()
                
                if current_balance is not None:
                    self.tm.main_window.update_user_data(current_amount=current_balance)
            
            # 잔액 확인 시도 3: 페이지 소스에서 확인
            if current_balance is None:
                self.logger.warning("잔액 업데이트 2차 실패, 3차 시도...")
                balance, _ = self.tm.balance_service.get_current_balance_and_username()
                if balance is not None:
                    current_balance = balance
                    self.tm.main_window.update_user_data(current_amount=current_balance)
            
            # 목표 금액 확인
            if current_balance is not None:
                self.logger.info(f"베팅 결과 후 잔액: {current_balance:,}원")
                
                if self.tm.balance_service.check_target_amount(current_balance):
                    self.logger.info("목표 금액 도달로 자동 매매를 중지합니다.")
                    self.tm.stop_trading()
            else:
                self.logger.error("베팅 결과 후 잔액을 업데이트할 수 없습니다.")
        except Exception as e:
            self.logger.error(f"잔액 업데이트 오류: {e}")