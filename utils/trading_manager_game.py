# utils/trading_manager_game.py 수정된 코드
import time
import logging
from PyQt6.QtWidgets import QMessageBox, QApplication

class TradingManagerGame:
    """TradingManager의 게임 처리 관련 기능 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager  # trading_manager 참조
        self.logger = trading_manager.logger or logging.getLogger(__name__)
    
    def enter_first_room(self):
        """첫 방 입장 및 모니터링 시작"""
        try:
            # 상태 초기화
            self.tm.game_count = 0
            self.tm.result_count = 0
            self.tm.current_pick = None
            self.tm.processed_rounds = set()
            
            # 게임 감지기 초기화
            from modules.game_detector import GameDetector
            if hasattr(self.tm, 'game_monitoring_service'):
                self.tm.game_monitoring_service.game_detector = GameDetector()
                if hasattr(self.tm.game_monitoring_service, 'last_detected_count'):
                    self.tm.game_monitoring_service.last_detected_count = 0
            
            # 방문 순서 초기화
            self.tm.room_manager.generate_visit_order()
            
            # 방 선택 및 입장
            self.tm.current_room_name = self.tm.room_entry_service.enter_room()
            
            # 방 입장 실패 시
            if not self.tm.current_room_name:
                self.tm.stop_trading()
                return False
                
            # 중지 버튼 활성화
            self.tm.main_window.stop_button.setEnabled(True)
            
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

    def handle_room_entry_failure(self):
        """방 입장 실패 처리"""
        # 방문 큐 리셋
        if self.tm.room_manager.reset_visit_queue():
            self.logger.info("방 입장 실패. 방문 큐를 리셋하고 다시 시도합니다.")
            return self.tm.change_room()  # 재귀적으로 다시 시도
        else:
            # 중지 버튼 비활성화
            self.tm.main_window.stop_button.setEnabled(False)
            self.tm.main_window.update_button_styles()

            self.tm.stop_trading()
            QMessageBox.warning(self.tm.main_window, "오류", "체크된 방이 없거나 모든 방 입장에 실패했습니다.")
            return False

    def handle_successful_room_entry(self, new_room_name, preserve_martin=False):
        """
        방 입장 성공 처리
        
        Args:
            new_room_name (str): 새 방 이름
            preserve_martin (bool): 마틴 단계 유지 여부
        """
        # 중지 버튼 활성화
        self.tm.main_window.stop_button.setEnabled(True)
        self.tm.main_window.update_button_styles()
        QApplication.processEvents()
        
        self.tm.just_changed_room = True  # 여기에 플래그 추가
        # 방 이동 후 로비에서 잔액 확인
        if hasattr(self.tm, 'check_balance_after_room_change') and self.tm.check_balance_after_room_change:
            try:
                balance = self.tm.balance_service.get_lobby_balance()
                
                if balance is not None:
                    # UI 업데이트
                    self.tm.main_window.update_user_data(current_amount=balance)
                    
                    # 목표 금액 확인
                    if self.tm.balance_service.check_target_amount(balance, source="방 이동 후 확인"):
                        # 목표 금액 도달 시 자동 매매 중지
                        self.exit_current_game_room()
                        self.tm.stop_trading()
                        self.tm.check_balance_after_room_change = False
                        return False
                
                # 플래그 초기화
                self.tm.check_balance_after_room_change = False
                
            except Exception as e:
                self.logger.error(f"방 이동 후 잔액 확인 오류: {e}")
                self.tm.check_balance_after_room_change = False

        # 베팅 위젯 초기화 (새 방 입장 시) - 마틴 유지 여부에 따라 다르게 처리
        if hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
            self.tm.main_window.betting_widget.prevent_reset = preserve_martin
        
        # 마틴 유지가 아닌 경우에만 마커 초기화
        if not preserve_martin:
            # 마커 초기화 및 룸 결과 초기화
            self.tm.main_window.betting_widget.reset_step_markers()
            self.tm.main_window.betting_widget.reset_room_results(success=True)
            
            # room_position_counter 초기화
            self.tm.main_window.betting_widget.room_position_counter = 0
        
        # 마틴 유지 시 현재 베팅 금액 다시 설정
        bet_amount = None
        if preserve_martin and hasattr(self.tm.excel_trading_service, 'get_current_bet_amount'):
            bet_amount = self.tm.excel_trading_service.get_current_bet_amount()
        
        # UI 업데이트
        self.tm.current_room_name = new_room_name
        self.tm.main_window.update_betting_status(
            room_name=self.tm.current_room_name,
            pick=self.tm.current_pick if preserve_martin else "",
            bet_amount=bet_amount
        )

        # 게임 상태 확인 및 15게임 데이터 수집
        try:
            # 목표 금액 도달 여부 확인 후 게임 상태 확인
            if not hasattr(self.tm.balance_service, '_target_amount_reached') or not self.tm.balance_service._target_amount_reached:
                game_state = self.tm.game_monitoring_service.get_current_game_state(log_always=True)
                
                if game_state:
                    # 실제 게임 카운트 저장
                    actual_game_count = game_state.get('round', 0)
                    self.tm.game_count = actual_game_count
                    
                    # 15게임 데이터 추출 (TIE 제외한 P/B 결과)
                    filtered_results = game_state.get('filtered_results', [])
                    
                    # 로그 출력 - 15게임 수집 상태 확인
                    self.logger.info(f"방 입장 후 수집된 결과: {len(filtered_results)}개, 필요: 15개")
                    
                    # Excel 처리 서비스를 통해 게임 결과 기록
                    result = self.tm.excel_trading_service.process_game_results(
                        game_state, 
                        0,  # 첫 진입으로 처리
                        self.tm.current_room_name,
                        log_on_change=True
                    )
                    
                    if result[0] is not None:
                        if result[3] in ['P', 'B']:  # next_pick 값이 있는 경우
                            # 원본 픽 저장
                            self.tm.current_pick = result[3]
                            
                            # 방향 적용된 픽 계산
                            actual_pick = self.tm.excel_trading_service.get_reverse_bet_pick(result[3])
                            
                            # UI에 픽 값과 베팅 금액 표시
                            self.tm.main_window.update_betting_status(
                                pick=result[3],  # UI에는 원본 픽 표시
                                bet_amount=self.tm.excel_trading_service.get_current_bet_amount()
                            )
                            
                            # 로그 출력
                            self.logger.info(f"첫 분석 결과 PICK: {result[3]} (실제 베팅: {actual_pick})")
        except Exception as e:
            self.logger.error(f"새 방 최근 결과 기록 오류: {e}")

        return True

    def process_excel_result(self, result, game_state, previous_game_count):
        """엑셀 처리 결과 활용 - 마틴 단계에 따른 방 이동 로직 수정"""
        try:
            last_column, new_game_count, recent_results, next_pick = result
            
            # 실제 게임 카운트 사용
            actual_game_count = game_state.get('round', 0)
            
            # 현재 마틴 단계 확인
            current_martin_step = 0
            if hasattr(self.tm, 'martin_service'):
                current_martin_step = self.tm.martin_service.current_step
            
            # 게임 카운트 초기화 감지 (갑자기 작은 값으로 변경된 경우)
            if previous_game_count > 10 and actual_game_count <= 5:
                self.logger.info(f"게임 카운트 초기화 감지! {previous_game_count} -> {actual_game_count}")
                # 방 이동
                self.tm.change_room()
                return
            
            # 게임 카운트 변화 확인
            if new_game_count > previous_game_count:
                # 이전 게임 결과 처리
                self.process_previous_game_result(game_state, actual_game_count)
                
                # 타이(T) 결과 확인 - 타이는 무시하고 진행
                if game_state.get('latest_result') == 'T':
                    pass
                
                # 방 이동 필요 조건 확인 (수정된 로직)
                should_move = False
                
                # 1. 초이스 픽 시스템의 방 이동 신호
                if self.tm.excel_trading_service.should_change_room():
                    # N값 감지 확인하여 플래그 설정
                    consecutive_n = False
                    if hasattr(self.tm.excel_trading_service, 'choice_pick_system') and \
                    hasattr(self.tm.excel_trading_service.choice_pick_system, 'consecutive_n_count'):
                        consecutive_n = self.tm.excel_trading_service.choice_pick_system.consecutive_n_count >= 3
                    
                    self.logger.info(f"초이스 픽 시스템에서 방 이동 필요 신호 (N값 연속: {consecutive_n})")
                    should_move = True
                    due_to_consecutive_n = consecutive_n
                
                # 2. 60게임 조건 확인
                # - 마틴 1단계(시작 단계)이거나 승리 후인 경우에만 60게임 조건 적용
                # - 마틴 2단계 이상 진행 중이면 60게임 조건 무시하고 계속 진행
                elif actual_game_count >= 60:
                    # 마틴 단계 확인
                    if current_martin_step <= 0 or getattr(self.tm, 'just_won', False):
                        self.logger.info(f"60 게임 도달 ({actual_game_count}회차) 및 마틴 진행 없음 또는 승리 후 상태. 방 이동 필요")
                        should_move = True
                        due_to_consecutive_n = False
                    else:
                        self.logger.info(f"60 게임 도달 ({actual_game_count}회차)했지만 마틴 {current_martin_step+1}단계 진행 중이므로 계속 베팅")
                
                # 방 이동 필요 시 실행
                if should_move:
                    self.tm.change_room(due_to_consecutive_n=due_to_consecutive_n)
                    return
                
                # PICK 값에 따른 베팅 실행
                if not self.tm.betting_service.has_bet_current_round and next_pick in ['P', 'B']:
                    self.tm.main_window.update_betting_status(pick=next_pick)

                    # 베팅 실행
                    if previous_game_count > 0:  # 첫 입장이 아닌 경우에만 베팅
                        self.tm.bet_helper.place_bet(next_pick, actual_game_count)
                    else:
                        self.tm.current_pick = next_pick

                # 실제 게임 카운트 저장
                self.tm.game_count = actual_game_count
                
            # 베팅 후 결과 확인 중인 경우
            elif self.tm.betting_service.has_bet_current_round:
                last_bet = self.tm.betting_service.get_last_bet()
                if last_bet and last_bet['round'] < actual_game_count:
                    # 결과 확인 대기
                    pass
            
        except Exception as e:
            self.logger.error(f"Excel 결과 처리 오류: {e}")
            
    def handle_tie_result(self, latest_result, game_state):
        """무승부(T) 결과 처리"""
        try:
            # 무승부 시 베팅 시도
            if (latest_result == 'T' and 
                not self.tm.betting_service.has_bet_current_round and 
                self.tm.current_pick in ['P', 'B'] and
                self.tm.game_count > 0):
                
                # 베팅 상태 초기화
                self.tm.betting_service.has_bet_current_round = False
                
                # 대기 시간
                time.sleep(1.5)
                
                # 현재 방에 계속 있음을 표시
                if hasattr(self.tm.main_window, 'room_log_widget'):
                    self.tm.main_window.room_log_widget.set_current_room(
                        self.tm.current_room_name, 
                        is_new_visit=False
                    )

                # 베팅 시도
                bet_success = self.tm.bet_helper.place_bet(self.tm.current_pick, self.tm.game_count)
                
                if bet_success:
                    self.logger.info(f"TIE 이후 베팅 성공: {self.tm.current_pick}")
                else:
                    self.logger.warning(f"TIE 이후 베팅 실패. 다음 시도 예정")
                    self.tm.main_window.set_remaining_time(0, 0, 1)
        except Exception as e:
            self.logger.error(f"TIE 결과 처리 오류: {e}")
                
    def process_previous_game_result(self, game_state, new_game_count):
        """이전 게임 결과 처리"""
        try:
            # 적중 마커 리셋 (적중 후 다음 턴)
            if getattr(self.tm, 'just_won', False):
                self.logger.info("이전 적중 후 마커 전체 초기화")
                self.tm.main_window.betting_widget.reset_step_markers()
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.tm.just_won = False

            # 베팅 결과 처리
            last_bet = self.tm.betting_service.get_last_bet()
            latest_result = game_state.get('latest_result')

            if last_bet and last_bet['type'] in ['P', 'B']:
                # 베팅 결과 처리
                result_status = self.tm.bet_helper.process_bet_result(last_bet['type'], latest_result, new_game_count)
                
                # 승리 후 60게임 이상인지 확인
                actual_game_count = game_state.get('round', 0)
                if result_status == 'win' and actual_game_count >= 60:
                    self.logger.info(f"승리 후 60게임 이상 도달 ({actual_game_count}회차). 방 이동 진행")
                    self.tm.change_room()
                    return
                
                # 방 이동 확인
                if self.tm.excel_trading_service.should_change_room():
                    self.logger.info("베팅 결과 처리 후 방 이동 필요 감지")
                    self.tm.change_room()
                    return

            # 타이가 아닌 경우에만 베팅 상태 초기화
            if latest_result != 'T':
                self.tm.betting_service.reset_betting_state(new_round=new_game_count)

            # UI 상태 업데이트
            display_room_name = self.tm.current_room_name.split('\n')[0] if '\n' in self.tm.current_room_name else self.tm.current_room_name
            self.tm.main_window.update_betting_status(
                room_name=f"{display_room_name}",
                pick=self.tm.current_pick
            )

        except Exception as e:
            self.logger.error(f"이전 게임 결과 처리 오류: {e}")

    def exit_current_game_room(self):
        """현재 게임방에서 나가기"""
        try:
            # 중지 버튼 비활성화
            self.tm.main_window.stop_button.setEnabled(False)
            self.tm.main_window.update_button_styles()
            
            # 현재 URL 확인
            current_url = self.tm.devtools.driver.current_url
            
            # 게임방에 있는지 확인
            in_game_room = "game" in current_url.lower() or "live" in current_url.lower()
            
            if in_game_room:
                self.logger.info("현재 게임방에서 나가기 시도 중...")
                self.tm.game_monitoring_service.close_current_room()
                self.logger.info("게임방에서 나가고 로비로 이동 완료")
                
            return True
        except Exception as e:
            self.logger.warning(f"방 나가기 중 오류 발생: {e}")
            return False
        
    def reset_room_state(self, preserve_martin=False):
        """
        방 이동 시 상태 초기화
        
        Args:
            preserve_martin (bool): True인 경우 마틴 단계 유지
        """
        # 게임 정보 초기화
        self.tm.game_count = 0
        self.tm.result_count = 0
        self.tm.current_pick = None
        self.tm.betting_service.reset_betting_state()
        
        # 처리된 게임 결과 기록 초기화
        self.tm.processed_rounds = set()
        
        # 게임 모니터링 서비스 초기화
        if hasattr(self.tm, 'game_monitoring_service'):
            if hasattr(self.tm.game_monitoring_service, 'last_detected_count'):
                self.tm.game_monitoring_service.last_detected_count = 0
            if hasattr(self.tm.game_monitoring_service, 'game_detector'):
                from modules.game_detector import GameDetector
                self.tm.game_monitoring_service.game_detector = GameDetector()
        
        # 마틴 단계 유지 옵션에 따라 처리
        if not preserve_martin:
            # 초이스 픽 시스템 초기화
            self.tm.excel_trading_service.reset_after_room_change()
            
            # 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset()
            
            self.logger.info("방 이동 시 마틴 단계 초기화 완료")
        else:
            self.logger.info("N값 연속 발생으로 인한 방 이동: 마틴 단계 유지")
        
        # 이전 방 이동 신호 초기화
        self.tm.should_move_to_next_room = False
        
        # 베팅 위젯 초기화 방지 플래그 - 마틴 유지 시에는 항상
        if hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
            if preserve_martin:
                self.tm.main_window.betting_widget.prevent_reset = True
            else:
                self.tm.main_window.betting_widget.prevent_reset = False
        
        self.logger.info(f"방 이동 시 상태 초기화 완료 (마틴 유지: {preserve_martin})")