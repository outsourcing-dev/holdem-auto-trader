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
            return self.tm.change_room(due_to_consecutive_n=True)  # ✅ 여기!
        else:
            # 중지 버튼 비활성화
            self.tm.main_window.stop_button.setEnabled(False)
            self.tm.main_window.update_button_styles()

            self.tm.stop_trading()
            QMessageBox.warning(self.tm.main_window, "오류", "체크된 방이 없거나 모든 방 입장에 실패했습니다.")
            return False

    # utils/trading_manager_game.py의 handle_successful_room_entry 메서드 수정
    def handle_successful_room_entry(self, new_room_name, preserve_martin=False):
        """
        방 입장 성공 처리 - 첫 입장 시 바로 베팅하지 않고 한 번의 결과 추가 대기
        
        Args:
            new_room_name (str): 새 방 이름
            preserve_martin (bool): 마틴 단계 유지 여부
        """
        # 중지 버튼 활성화
        self.tm.main_window.stop_button.setEnabled(True)
        self.tm.main_window.update_button_styles()
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        self.tm.just_changed_room = True
        
        # ✅ 최초 방 입장 플래그 설정 - 첫 결과를 기다리기 위한 플래그
        self.tm.wait_first_result = True
        self.logger.info("방 입장 후 첫 결과 대기 모드 활성화")

        # 방 이동 후 로비 잔액 확인
        if hasattr(self.tm, 'check_balance_after_room_change') and self.tm.check_balance_after_room_change:
            try:
                balance = self.tm.balance_service.get_lobby_balance()

                if balance is not None:
                    self.tm.main_window.update_user_data(current_amount=balance)
                    if self.tm.balance_service.check_target_amount(balance, source="방 이동 후 확인"):
                        self.exit_current_game_room()
                        self.tm.stop_trading()
                        self.tm.check_balance_after_room_change = False
                        return False

                self.tm.check_balance_after_room_change = False

            except Exception as e:
                self.logger.error(f"방 이동 후 잔액 확인 오류: {e}")
                self.tm.check_balance_after_room_change = False

        # 현재 위젯 포지션 확인 (로그용)
        current_widget_pos = 0
        if hasattr(self.tm.main_window, 'betting_widget') and hasattr(self.tm.main_window.betting_widget, 'room_position_counter'):
            current_widget_pos = self.tm.main_window.betting_widget.room_position_counter
            self.logger.info(f"[방 이동 성공] 위젯 포지션: {current_widget_pos+1}번")

        # 마틴 유지 시 현재 베팅 금액 다시 설정
        bet_amount = None
        if hasattr(self.tm.excel_trading_service, 'get_current_bet_amount'):
            bet_amount = self.tm.excel_trading_service.get_current_bet_amount(widget_position=current_widget_pos)
            self.logger.info(f"[방 이동 성공] 현재 베팅 금액: {bet_amount:,}원")

        # UI 상태 업데이트
        self.tm.current_room_name = new_room_name
        self.tm.main_window.update_betting_status(
            room_name=self.tm.current_room_name,
            pick=self.tm.current_pick,
            bet_amount=bet_amount
        )

        # 방 로그 위젯 설정 - 수정된 부분: 항상 is_new_visit=True로 설정
        if hasattr(self.tm.main_window, 'room_log_widget'):
            # 디버그 로그 추가
            self.logger.info(f"[방 이동 성공] 방 로그 위젯 설정: {self.tm.current_room_name}, 새방문=True")
            
            # 명시적으로 is_new_visit=True로 설정하여 새 방문으로 처리
            self.tm.main_window.room_log_widget.set_current_room(
                self.tm.current_room_name,
                is_new_visit=True
            )
            
            # has_changed_room 플래그 명시적으로 설정
            self.tm.main_window.room_log_widget.has_changed_room = True

        # 입장 직후 게임 상태 분석 및 15게임 처리
        try:
            if not getattr(self.tm.balance_service, '_target_amount_reached', False):
                game_state = self.tm.game_monitoring_service.get_current_game_state(log_always=True)

                if game_state:
                    actual_game_count = game_state.get('round', 0)
                    self.tm.game_count = actual_game_count

                    filtered_results = game_state.get('filtered_results', [])
                    self.logger.info(f"방 입장 후 수집된 결과: {len(filtered_results)}개, 필요: 15개")

                    result = self.tm.excel_trading_service.process_game_results(
                        game_state,
                        0,
                        self.tm.current_room_name,
                        log_on_change=True
                    )

                    if result[0] is not None and result[3] in ['P', 'B']:
                        self.tm.current_pick = result[3]
                        actual_pick = self.tm.excel_trading_service.get_reverse_bet_pick(result[3])

                        self.tm.main_window.update_betting_status(
                            pick=result[3],
                            bet_amount=bet_amount
                        )
                        self.logger.info(f"첫 분석 결과 PICK: {result[3]} (실제 베팅: {actual_pick})")
                        # ✅ 하지만 바로 베팅하지는 않음 (wait_first_result 플래그로 첫 결과 대기)

        except Exception as e:
            self.logger.error(f"새 방 최근 결과 기록 오류: {e}")

        return True

    # utils/trading_manager_game.py 수정 부분

    def process_excel_result(self, result, game_state, previous_game_count):
        """엑셀 처리 결과 활용 - 첫 결과 대기 플래그 확인 추가"""
        try:
            # 승리 직후 플래그 확인 및 초기화 - 여기에 추가
            if getattr(self.tm, 'just_won', False):
                self.logger.info("[승리 후 초기화] just_won 상태 감지, 모든 플래그 초기화")
                # 마커 리셋
                if hasattr(self.tm.main_window, 'betting_widget'):
                    self.tm.main_window.betting_widget.reset_step_markers()
                    self.tm.main_window.betting_widget.room_position_counter = 0
                # 첫 결과 대기 플래그도 초기화
                if hasattr(self.tm, 'wait_first_result'):
                    self.tm.wait_first_result = False
                    self.logger.info("wait_first_result 플래그 초기화")
                self.tm.just_won = False
            
            last_column, new_game_count, recent_results, next_pick = result
            
            # 실제 게임 카운트 사용
            actual_game_count = game_state.get('round', 0)
            
            # 현재 마틴 단계 확인 - 항상 최신 값을 가져옴
            current_martin_step = 0
            if hasattr(self.tm, 'martin_service') and hasattr(self.tm.martin_service, 'current_step'):
                # 실시간으로 마틴 단계 다시 확인
                current_martin_step = self.tm.martin_service.current_step
                self.logger.info(f"현재 마틴 단계 확인: {current_martin_step+1}단계")
            
            # 위젯의 마지막 마커 상태 확인
            last_marker = None
            if hasattr(self.tm.main_window, 'betting_widget'):
                if hasattr(self.tm.main_window.betting_widget, 'get_current_marker'):
                    last_marker = self.tm.main_window.betting_widget.get_current_marker()
                elif hasattr(self.tm.main_window.betting_widget, 'markers'):
                    # markers 배열에서 마지막 유효한 마커 찾기
                    markers = self.tm.main_window.betting_widget.markers
                    for i in range(len(markers)-1, -1, -1):
                        if markers[i] in ["O", "X", "T"]:
                            last_marker = markers[i]
                            break
            
            self.logger.info(f"현재 위젯 마지막 마커: {last_marker}")
            
            # 마지막 마커가 'O'면 성공, 마지막 마커가 'X'면 마틴 진행중
            is_martin_in_progress = (last_marker == "X")
            is_last_bet_win = (last_marker == "O")
            
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
                due_to_consecutive_n = False

                # 1. 초이스 픽 시스템의 방 이동 신호 - 여기서 N 값 3회 이상 확인
                if self.tm.excel_trading_service.should_change_room():
                    # N값 감지 확인
                    consecutive_n = False
                    if hasattr(self.tm.excel_trading_service, 'choice_pick_system') and \
                    hasattr(self.tm.excel_trading_service.choice_pick_system, 'consecutive_n_count'):
                        consecutive_n = self.tm.excel_trading_service.choice_pick_system.consecutive_n_count >= 3
                    
                    if consecutive_n:
                        # N값 3회 이상인 경우에만 방 이동 허용
                        self.logger.info(f"N값 3회 이상 연속 감지 - 마틴 유지하며 방 이동")
                        should_move = True
                        due_to_consecutive_n = True  # 마틴 유지
                    elif not is_martin_in_progress:
                        # 마틴 진행중이 아니면 일반 방 이동 허용
                        self.logger.info(f"초이스 픽 시스템 방 이동 신호 - 마틴 없거나 성공했으므로 방 이동")
                        should_move = True
                        due_to_consecutive_n = False  # 마틴 초기화
                    else:
                        # 마틴 중이고 N값 조건도 아니면 방 이동 안함
                        self.logger.info(f"초이스 픽 방 이동 신호지만 마틴 진행 중(X 마커)이므로 무시")
                
                # 2. 55게임 조건 확인 - 수정된 부분
                elif actual_game_count >= 55:
                    # 위젯 포지션 확인
                    widget_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)

                    self.logger.info(
                        f"55게임 체크 - 게임 수: {actual_game_count}, "
                        f"위젯 포지션: {widget_pos + 1}번"
                    )

                    if widget_pos != 0:
                        self.logger.info(f"현재 포지션이 {widget_pos + 1}번이므로 방 유지")
                        should_move = False
                    else:
                        self.logger.info(f"처음 위치 (1번)에서 55게임 도달 → 방 이동")
                        should_move = True
                        due_to_consecutive_n = False  # 마틴은 초기화

                
                # 방 이동 필요 시 실행
                if should_move:
                    # 수정: 항상 True가 아닌 상황에 맞게 플래그 전달
                    self.tm.change_room(due_to_consecutive_n=due_to_consecutive_n)
                    return
                
                # ✅ PICK 값에 따른 베팅 실행 (첫 결과 대기 모드가 아닌 경우에만)
                if not hasattr(self.tm, 'wait_first_result') or not self.tm.wait_first_result:
                    if not self.tm.betting_service.has_bet_current_round and next_pick in ['P', 'B']:
                        # ✅ 베팅 전에 just_won 상태라면 마커 초기화 먼저!
                        if getattr(self.tm, 'just_won', False):
                            self.logger.info("[베팅 전 초기화] just_won 상태이므로 마커 리셋")
                            self.tm.main_window.betting_widget.reset_step_markers()
                            self.tm.main_window.betting_widget.room_position_counter = 0
                            self.tm.just_won = False

                        # PICK UI 갱신
                        self.tm.main_window.update_betting_status(pick=next_pick)

                        # 베팅 실행
                        if previous_game_count > 0:
                            self.tm.bet_helper.place_bet(next_pick, actual_game_count)
                        else:
                            self.tm.current_pick = next_pick
                else:
                    # 첫 결과 대기 모드일 경우 로그만 남김
                    self.logger.info(f"첫 결과 대기 모드입니다. 아직 베팅하지 않습니다. (PICK: {next_pick})")
                    if previous_game_count > 0:
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
                time.sleep(1)
                
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
                
# utils/trading_manager_game.py - process_previous_game_result 메서드 수정

    def process_previous_game_result(self, game_state, new_game_count):
        """이전 게임 결과 처리 - 중복 로그 방지 수정"""
        try:
            # 적중 마커 리셋 (적중 후 다음 턴)
            if getattr(self.tm, 'just_won', False):
                self.logger.info("이전 적중 후 UI 완전 초기화")
                # 마커 초기화
                self.tm.main_window.betting_widget.reset_step_markers()
                # 카운터 초기화
                self.tm.main_window.betting_widget.room_position_counter = 0
                # PICK 값 초기화
                self.tm.current_pick = None
                # 상태 초기화
                self.tm.just_won = False
                # UI 업데이트
                self.tm.main_window.update_betting_status(
                    room_name=self.tm.current_room_name,
                    pick=None,  # PICK 값도 초기화
                    reset_counter=True
                )

            # 베팅 결과 처리
            last_bet = self.tm.betting_service.get_last_bet()
            latest_result = game_state.get('latest_result')

            if last_bet and last_bet['type'] in ['P', 'B']:
                # 베팅 결과 처리 - room_log 업데이트는 process_bet_result에서만 한 번 실행
                result_status = self.tm.bet_helper.process_bet_result(last_bet['type'], latest_result, new_game_count)
                
                # 승리 후 게임 판수 확인
                actual_game_count = game_state.get('round', 0)
                if result_status == 'win' and actual_game_count >= 55:
                    self.logger.info(f"trading_manager_game : 승리 후 55게임 이상 도달 ({actual_game_count}회차). 방 이동 진행")
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
        방 이동 시 상태 초기화 - 위젯 포지션 중심으로 리팩토링
        
        Args:
            preserve_martin (bool): True인 경우 마틴 단계 유지 (위젯 포지션 유지)
        """
        # 게임 정보 초기화
        self.tm.game_count = 0
        self.tm.result_count = 0
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
        
        # 현재 위젯 포지션 확인
        current_widget_pos = 0
        if hasattr(self.tm.main_window, 'betting_widget') and hasattr(self.tm.main_window.betting_widget, 'room_position_counter'):
            current_widget_pos = self.tm.main_window.betting_widget.room_position_counter
            
        # 마틴 단계 유지 여부에 따라 처리
        if not preserve_martin:
            # 위젯 포지션 초기화
            if hasattr(self.tm.main_window, 'betting_widget'):
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.logger.info(f"[방 이동] 위젯 포지션 초기화: {current_widget_pos} → 0")
                
                # 마커도 초기화
                if hasattr(self.tm.main_window.betting_widget, 'reset_step_markers'):
                    self.tm.main_window.betting_widget.reset_step_markers()
                    self.logger.info("[방 이동] 모든 마커 초기화")
            
            # 초이스 픽 시스템 초기화
            self.tm.excel_trading_service.reset_after_room_change(preserve_martin=False)
            
            # 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset_room_bet_status()  # 방 상태만 초기화
                
            self.logger.info("방 이동 시 마틴 단계 초기화 완료")
        else:
            # 마틴 단계 유지 (위젯 포지션 유지)
            self.logger.info(f"[방 이동] 위젯 포지션 유지: {current_widget_pos+1}번")
            
            # 베팅 위젯 초기화 방지 플래그 설정
            if hasattr(self.tm.main_window.betting_widget, 'prevent_reset'):
                self.tm.main_window.betting_widget.prevent_reset = True
                self.logger.info("[방 이동] 위젯 초기화 방지 플래그 설정")
            
            # 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset_room_bet_status()  # 방 상태만 초기화
            
            # 초이스 픽 시스템 초기화 (마틴 단계 유지)
            self.tm.excel_trading_service.reset_after_room_change(preserve_martin=True)
        
        # 이전 방 이동 신호 초기화
        self.tm.should_move_to_next_room = False
        
        # 현재 PICK 값은 초기화하지 않음 (preserve_martin이 True인 경우 유지)
        if not preserve_martin:
            self.tm.current_pick = None
        
        self.logger.info(f"방 이동 시 상태 초기화 완료 (마틴 유지: {preserve_martin})")
        