# utils/trading_manager_game.py
import time
import logging
from PyQt6.QtWidgets import QMessageBox

class TradingManagerGame:
    """TradingManager의 게임 처리 관련 기능 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager  # trading_manager 참조
        self.logger = trading_manager.logger or logging.getLogger(__name__)
    
    def enter_first_room(self):
        """첫 방 입장 및 모니터링 시작"""
        try:
            # 방문 순서 초기화
            self.tm.room_manager.generate_visit_order()
            
            # 방 선택 및 입장
            self.tm.current_room_name = self.tm.room_entry_service.enter_room()
            
            # 방 입장에 실패한 경우
            if not self.tm.current_room_name:
                self.tm.stop_trading()
                return False
            
            # 모니터링 타이머 설정
            self.tm.main_window.set_remaining_time(0, 0, 2)

            # 게임 정보 초기 분석
            self.tm.analyze_current_game()

            # 자동 매매 루프 시작
            self.tm.run_auto_trading()
            
            return True
        except Exception as e:
            self.logger.error(f"첫 방 입장 오류: {e}")
            self.tm.stop_trading()
            return False
    
    def process_excel_result(self, result, game_state, previous_game_count):
        """엑셀 처리 결과 활용"""
        try:
            last_column, new_game_count, recent_results, next_pick = result
            
            # 중요 변경: 실제 게임 카운트 사용 - 게임 카운트 강제 변환 방지
            actual_game_count = game_state.get('round', 0)
            
            # 게임 카운트 변화 검증 - 조건 수정
            if new_game_count > previous_game_count:
                # 이전 게임 결과 처리
                self.process_previous_game_result(game_state, actual_game_count)
                
                # 타이(T) 결과 확인
                if game_state.get('latest_result') == 'T':
                    self.tm.should_move_to_next_room = False
                
                # PICK 값에 따른 베팅 실행
                if not self.tm.should_move_to_next_room and next_pick in ['P', 'B'] and not self.tm.betting_service.has_bet_current_round:
                    self.tm.main_window.update_betting_status(pick=next_pick)

                    # 첫 입장 시 바로 베팅하지 않음
                    if previous_game_count > 0:
                        self.tm.bet_helper.place_bet(next_pick, actual_game_count)
                    else:
                        self.logger.info(f"첫 입장 후 게임 상황 파악 중 (PICK: {next_pick})")
                        self.tm.current_pick = next_pick

                # 중요 변경: 실제 게임 카운트 저장
                self.tm.game_count = actual_game_count
                self.tm.recent_results = recent_results
                
                # 베팅 후 바로 결과가 나온 경우 처리 
                if self.tm.betting_service.has_bet_current_round:
                    last_bet = self.tm.betting_service.get_last_bet()
                    if last_bet and last_bet['round'] < actual_game_count:
                        self.logger.info(f"베팅({last_bet['round']})과 현재 게임({actual_game_count})의 불일치 감지")
                        # 이 경우 이전 게임 결과를 먼저 처리해야 함
                        if not self.tm.should_move_to_next_room:
                            self.logger.info("베팅 결과 확인을 위해 다음 분석까지 대기")
            
            # 첫 입장 후 일정 시간 경과 시 베팅 - 수정: 실제 게임 카운트 참조
            elif previous_game_count == 0 and self.tm.game_count > 0 and not self.tm.betting_service.has_bet_current_round:
                if hasattr(self.tm, '_first_entry_time'):
                    elapsed = time.time() - self.tm._first_entry_time
                    if elapsed > 1.0 and next_pick in ['P', 'B']:
                        self.logger.info(f"첫 입장 후 {elapsed:.1f}초 경과, 베팅 실행: {next_pick}")
                        self.tm.current_pick = next_pick
                        self.tm.main_window.update_betting_status(pick=next_pick)
                        self.tm.bet_helper.place_bet(next_pick, self.tm.game_count)
                        delattr(self.tm, '_first_entry_time')
                else:
                    self.tm._first_entry_time = time.time()
        except Exception as e:
            self.logger.error(f"Excel 결과 처리 오류: {e}")

    def handle_tie_result(self, latest_result, game_state):
        """무승부(T) 결과 처리"""
        try:
            # 무승부(T) 결과 시 베팅 시도
            if (latest_result == 'T' and 
                not self.tm.betting_service.has_bet_current_round and 
                self.tm.current_pick in ['P', 'B'] and
                not self.tm.should_move_to_next_room and
                self.tm.game_count > 0):
                
                # 베팅 상태 초기화
                self.tm.betting_service.has_bet_current_round = False
                
                self.logger.info(f"무승부(T) 감지, 이전 PICK 값({self.tm.current_pick})으로 베팅 시도")
                time.sleep(1.5)  # 대기 시간 단축
                
                # 중요: TIE 결과 시에는 방 이동이 아닌 것을 표시 (is_new_visit=False)
                if hasattr(self.tm.main_window, 'room_log_widget'):
                    # 같은 방에 계속 있다는 것을 표시
                    self.tm.main_window.room_log_widget.set_current_room(
                        self.tm.current_room_name, 
                        is_new_visit=False
                    )

                bet_success = self.tm.bet_helper.place_bet(self.tm.current_pick, self.tm.game_count)
                
                if bet_success:
                    self.logger.info(f"TIE 이후 베팅 성공: {self.tm.current_pick}")
                else:
                    self.logger.warning(f"TIE 이후 베팅 실패. 다음 시도 예정")
                    self.tm.main_window.set_remaining_time(0, 0, 1)
        except Exception as e:
            self.logger.error(f"TIE 결과 처리 오류: {e}")
                
    def process_previous_game_result(self, game_state, new_game_count):
        """이전 게임 결과 처리 및 배팅 상태 초기화"""
        try:
            # 이전 베팅 정보 가져오기
            last_bet = self.tm.betting_service.get_last_bet()
            
            # 이전 게임에 베팅했는지 확인 - 조건 완화 (라운드 비교 제거)
            if last_bet and last_bet['type'] in ['P', 'B']:
                bet_type = last_bet['type']
                latest_result = game_state.get('latest_result')
                
                self.logger.info(f"[결과검증] 라운드: {self.tm.game_count}, 베팅: {bet_type}, 결과: {latest_result}")
                
                if latest_result:
                    # 베팅 결과 처리 - 결과에 따라 방 이동 플래그 설정
                    result_status = self.tm.bet_helper.process_bet_result(bet_type, latest_result, new_game_count)
                    
                    # 결과 로깅
                    self.logger.info(f"베팅 결과: {result_status}, 방 이동 플래그: {self.tm.should_move_to_next_room}")
            elif last_bet:
                # 라운드가 달라진 경우도 결과 처리 시도
                self.logger.info(f"라운드 불일치: 이전({last_bet['round']}) vs 현재({self.tm.game_count}), 결과 처리 시도")
                
                latest_result = game_state.get('latest_result')
                if latest_result and last_bet['type'] in ['P', 'B']:
                    result_status = self.tm.bet_helper.process_bet_result(last_bet['type'], latest_result, new_game_count)
                    self.logger.info(f"라운드 불일치 상황에서 결과 처리: {result_status}")
            
            # 타이(T) 결과를 제외하고 베팅 상태 초기화
            if game_state.get('latest_result') != 'T':
                self.tm.betting_service.reset_betting_state(new_round=new_game_count)
            
            # UI 업데이트
            display_room_name = self.tm.current_room_name.split('\n')[0] if '\n' in self.tm.current_room_name else self.tm.current_room_name
            self.tm.main_window.update_betting_status(
                room_name=f"{display_room_name})",
                pick=self.tm.current_pick
            )
        except Exception as e:
            self.logger.error(f"이전 게임 결과 처리 오류: {e}")
    
    def exit_current_game_room(self):
        """현재 게임방에서 나가기"""
        try:
            # 현재 URL 확인
            current_url = self.tm.devtools.driver.current_url
            
            # 게임방에 있는지 확인
            in_game_room = "game" in current_url.lower() or "live" in current_url.lower()
            
            if in_game_room:
                self.logger.info("현재 게임방에서 나가기 시도 중...")
                self.tm.game_monitoring_service.close_current_room()
                self.logger.info("게임방에서 나가고 로비로 이동 완료")
            else:
                self.logger.info("이미 카지노 로비에 있습니다.")
                
            return True
        except Exception as e:
            self.logger.warning(f"방 나가기 중 오류 발생: {e}")
            return False
    
    # trading_manager_game.py의 reset_room_state 메서드 수정

    def reset_room_state(self):
        """방 이동 시 상태 초기화"""
        # 게임 정보 초기화
        self.tm.game_count = 0
        self.tm.result_count = 0
        self.tm.current_pick = None
        self.tm.betting_service.reset_betting_state()
        
        if hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
            self.tm.main_window.betting_widget.prevent_reset = True
        
        # processed_rounds 초기화
        self.tm.processed_rounds = set()
        
        # 마틴 서비스 상태에 따른 선택적 초기화
        should_reset_widgets = False
        
        # 명확한 초기화 조건 확인
        if hasattr(self.tm, 'martin_service'):
            # 1. 승리 후 방 이동인 경우 (승리 후에는 항상 초기화)
            if self.tm.martin_service.win_count > 0 and self.tm.martin_service.consecutive_losses == 0:
                should_reset_widgets = True
                # 수정: 승리 후에는 마틴 단계 초기화
                self.tm.martin_service.current_step = 0
                # 로그 추가
                previous_step = self.tm.martin_service.current_step
                self.logger.info(f"[수정] 승리 후 방 이동: 마틴 단계 명시적으로 0으로 초기화 (이전: {previous_step+1}단계)")
                
            # 2. 마틴 베팅에서 마지막 단계 실패 후 방 이동인 경우
            elif (self.tm.martin_service.current_step == 0 and 
                self.tm.martin_service.consecutive_losses > 0 and 
                self.tm.martin_service.need_room_change):
                should_reset_widgets = True
                
            # 베팅 정보 초기화
            self.tm.martin_service.reset_room_bet_status()
            self.logger.info(f"마틴 단계 상태: {self.tm.martin_service.current_step+1}단계")
                    
        # 조건에 따른 위젯 초기화
        if should_reset_widgets:
            self.logger.info("승리 또는 마틴 완료로 인한 방 이동: 베팅 위젯 초기화")
            self.tm.main_window.betting_widget.reset_step_markers()
            self.tm.main_window.betting_widget.reset_room_results()
        else:
            self.logger.info("TIE 또는 연속 베팅을 위한 방 이동: 베팅 위젯 유지")
                
    def handle_room_entry_failure(self):
        """방 입장 실패 처리"""
        # 방문 큐 리셋
        if self.tm.room_manager.reset_visit_queue():
            self.logger.info("방 입장 실패. 방문 큐를 리셋하고 다시 시도합니다.")
            return self.tm.change_room()  # 재귀적으로 다시 시도
        else:
            self.tm.stop_trading()
            QMessageBox.warning(self.tm.main_window, "오류", "체크된 방이 없거나 모든 방 입장에 실패했습니다.")
            return False

    # utils/trading_manager_game.py에서 handle_successful_room_entry 메서드 수정
    def handle_successful_room_entry(self, new_room_name):
        """방 입장 성공 처리"""
        # 성공적으로 새 방에 입장한 후 처리
        
        # 성공 여부 확인 - martin_service의 win_count로 판단
        was_successful = False
        if hasattr(self.tm, 'martin_service'):
            # 현재 객체에 저장된 값 사용 (최근에 승리했는지 여부)
            was_successful = (self.tm.martin_service.win_count > 0 and 
                            self.tm.martin_service.consecutive_losses == 0)
        
        # 성공한 경우에만 베팅 위젯 초기화 - 중요: 새 방 입장 후에 초기화
        if was_successful:
            self.logger.info("승리 후 새 방 입장 감지: 이제 베팅 위젯 초기화 실행")
            
            # prevent_reset 플래그 비활성화 (초기화 허용)
            if hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
                self.tm.main_window.betting_widget.prevent_reset = False
            
            # 초기화 실행 (명시적으로 마커 초기화 호출)
            self.tm.main_window.betting_widget.reset_step_markers()
            self.tm.main_window.betting_widget.reset_room_results(success=True)
            
            # room_position_counter 명시적으로 초기화
            self.tm.main_window.betting_widget.room_position_counter = 0
            
            self.logger.info("승리 후 새 방 입장 완료: 베팅 위젯 초기화 완료")
        else:
            self.logger.info("베팅 실패 후 새 방 입장: 베팅 위젯 유지")
        
        # UI 업데이트
        self.tm.current_room_name = new_room_name
        # 새로운 방 이름만 업데이트하고 reset_counter는 설정하지 않음
        self.tm.main_window.update_betting_status(
            room_name=self.tm.current_room_name,
            pick=""
        )

        # 방 이동 후 로비에서 잔액 확인 (추가)
        if hasattr(self.tm, 'check_balance_after_room_change') and self.tm.check_balance_after_room_change:
            try:
                self.logger.info("방 이동 후 로비에서 잔액 확인 중...")
                balance = self.tm.balance_service.get_lobby_balance()
                
                if balance is not None:
                    self.logger.info(f"로비에서 확인한 최신 잔액: {balance:,}원")
                    # UI 업데이트
                    self.tm.main_window.update_user_data(current_amount=balance)
                    
                    # 목표 금액 확인
                    if self.tm.balance_service.check_target_amount(balance, source="방 이동 후 확인"):
                        self.logger.info("목표 금액 도달로 자동 매매를 중지합니다.")
                        # 방금 입장한 방에서도 나가기
                        self.exit_current_game_room()
                        self.tm.stop_trading()
                        return True
                
                # 플래그 초기화
                self.tm.check_balance_after_room_change = False
                
            except Exception as e:
                self.logger.error(f"방 이동 후 잔액 확인 오류: {e}")
                self.tm.check_balance_after_room_change = False

        # 게임 상태 확인 및 최근 결과 기록
        try:
            self.logger.info("새 방 입장 후 최근 결과 확인 중...")
            game_state = self.tm.game_monitoring_service.get_current_game_state(log_always=True)
            
            if game_state:
                # 중요: 실제 게임 카운트 저장
                actual_game_count = game_state.get('round', 0)
                self.tm.game_count = actual_game_count
                self.logger.info(f"새 방 게임 카운트: {self.tm.game_count}")
                
                # Excel에 기록
                result = self.tm.excel_trading_service.process_game_results(
                    game_state, 
                    0,
                    self.tm.current_room_name,
                    log_on_change=True
                )
                
                if result[0] is not None:
                    self.logger.info(f"새 방에 최근 결과 기록 완료")
                    
                    if result[3] in ['P', 'B']:  # next_pick
                        self.logger.info(f"새 방 입장 후 첫 배팅 설정: {result[3]}")
                        self.tm.current_pick = result[3]
                        
                        # 즉시 배팅 유도
                        self.tm._first_entry_time = time.time() - 5
                        
                        # UI에 PICK 값 표시
                        self.tm.main_window.update_betting_status(
                            pick=result[3],
                            bet_amount=self.tm.martin_service.get_current_bet_amount()
                        )
        except Exception as e:
            self.logger.error(f"새 방 최근 결과 기록 오류: {e}")

        self.logger.info(f"새 방으로 이동 완료, 게임 카운트: {self.tm.game_count}")
        return True
