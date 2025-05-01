# utils/trading_manager_game.py 수정된 코드
import time
import logging
from PyQt6.QtWidgets import QMessageBox, QApplication

class TradingManagerGame:
    """TradingManager의 게임 처리 관련 기능 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager  # trading_manager 참조
        self.logger = trading_manager.logger or logging.getLogger(__name__)
        self.has_processed_new_game_result = False

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

    def handle_successful_room_entry(self, new_room_name, preserve_martin=False):
        self.tm.main_window.stop_button.setEnabled(True)
        self.tm.main_window.update_button_styles()
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        self.tm.just_changed_room = True
        self.tm.wait_first_result = True  # 🔥 대기 모드 켜기
        self.logger.info("✅ [대기 모드 ON] 첫 결과가 나올 때까지 PICK 생성을 막습니다.")

        # ✅ direction 초기화
        if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
            self.tm.excel_trading_service.choice_pick_system.current_direction = "normal"
            self.logger.info("[초기화] 새 방 입장 시 direction을 normal로 초기화 완료")

        # ✅ 마틴 단계 동기화
        current_widget_pos = 0
        if hasattr(self.tm.main_window, 'betting_widget') and hasattr(self.tm.main_window.betting_widget, 'room_position_counter'):
            current_widget_pos = self.tm.main_window.betting_widget.room_position_counter
            if hasattr(self.tm.martin_service, 'current_step'):
                self.tm.martin_service.current_step = current_widget_pos
                self.logger.info(f"[싱크] 마틴 단계 동기화 완료: {current_widget_pos+1}단계")
        if hasattr(self.tm.betting_service, 'has_bet_current_round'):
            self.tm.betting_service.has_bet_current_round = False
            self.logger.info("[싱크] has_bet_current_round 초기화 완료")

        # ✅ choice_pick 초기화
        cps = getattr(self.tm.excel_trading_service, 'choice_pick_system', None)
        if cps:
            cps.consecutive_n_count = 0
            cps.skip_n_count = True
            self.logger.info("방 입장 후 N 카운트 초기화 및 첫 분석 건너뛰기 플래그 설정")

        # ✅ 잔액 체크
        if getattr(self.tm, 'check_balance_after_room_change', False):
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

        # ✅ 베팅 금액 설정
        bet_amount = None
        if hasattr(self.tm.excel_trading_service, 'get_current_bet_amount'):
            bet_amount = self.tm.excel_trading_service.get_current_bet_amount(widget_position=current_widget_pos)
            self.logger.info(f"[방 이동 성공] 현재 베팅 금액: {bet_amount:,}원")

        # ✅ 방 이름 및 라운드 저장
        self.tm.current_room_name = new_room_name

        try:
            game_state = self.tm.game_monitoring_service.get_current_game_state(log_always=True)
            if game_state:
                actual_game_count = game_state.get('round', 0)
                self.tm.game_count = actual_game_count
                self.tm.entered_round = actual_game_count
                self.logger.info(f"[방 입장] 입장 직후 게임 수 저장: {actual_game_count}")

                # ✅ ChoicePickSystem도 동일하게 반영
                if cps:
                    cps._entered_round = actual_game_count
                    cps._current_game_round = actual_game_count
                    self.logger.info(f"[초이스픽 초기화] entered_round, current_game_round = {actual_game_count}")

                # ✅ 결과 기록
                filtered_results = game_state.get('filtered_results', [])
                self.logger.info(f"방 입장 후 수집된 결과: {len(filtered_results)}개, 필요: 15개")

                self.tm.excel_trading_service.process_game_results(
                    game_state,
                    0,
                    self.tm.current_room_name,
                    log_on_change=True
                )

                if cps:
                    cps.clear()
                    if len(filtered_results) >= 15:
                        cps.add_multiple_results(filtered_results[-15:])
                        self.logger.info("예측 엔진에 15개 결과 추가 완료")
                    else:
                        self.logger.warning(f"예측 엔진에 충분한 결과가 없음: {len(filtered_results)}개")

        except Exception as e:
            self.logger.error(f"새 방 최근 결과 기록 오류: {e}")

        # ✅ 첫 분석 후 skip_n_count 해제
        if cps:
            cps.skip_n_count = False
            self.logger.info("첫 분석 완료 - N 카운트 건너뛰기 플래그 해제")

        # ✅ 상태 및 UI 반영
        self.tm.main_window.update_betting_status(
            room_name=self.tm.current_room_name,
            pick=self.tm.current_pick,
            bet_amount=bet_amount
        )

        if hasattr(self.tm.main_window, 'room_log_widget'):
            self.logger.info(f"[방 이동 성공] 방 로그 위젯 설정: {self.tm.current_room_name}, 새방문=True")
            self.tm.main_window.room_log_widget.set_current_room(
                self.tm.current_room_name,
                is_new_visit=True
            )
            self.tm.main_window.room_log_widget.has_changed_room = True

        # if hasattr(self, 'run_auto_trading'):
        #     self.logger.info("[타이머 재시작] 방 이동 완료 후 분석 예약")
        #     self.run_auto_trading()
        return True


    def process_excel_result(self, result, game_state, previous_game_count):
        try:
            # 현재 처리 시도에 대한 고유 식별자 추가
            actual_game_count = game_state.get('round', 0)
            latest_result = game_state.get('latest_result')
            process_id = f"{actual_game_count}_{latest_result}"
            
            # choice_pick_system에 현재 게임 라운드 전달
            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                cps = self.tm.excel_trading_service.choice_pick_system
                cps._current_game_round = actual_game_count
            
            # 이미 이 게임 사이클에서 이 정확한 결과를 처리했다면 건너뜀
            if hasattr(self, '_last_processed_id') and self._last_processed_id == process_id:
                self.logger.info(f"이미 결과 {process_id}를 처리했습니다 - 건너뜁니다")
                return
                
            self._last_processed_id = process_id
            
            # 승리 직후 초기화
            if getattr(self.tm, 'just_won', False):
                self.logger.info("[승리 후 초기화] just_won 상태 감지, 모든 플래그 초기화")

                if  \
                hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                    cps = self.tm.excel_trading_service.choice_pick_system
                    cps.consecutive_n_count = 0
                    cps.should_refresh_data = True
                    cps.failure_count = 0
                    self.logger.info("[N 카운트 초기화] 승리 후 초기화")

                if hasattr(self.tm.main_window, 'betting_widget'):
                    self.tm.main_window.betting_widget.reset_step_markers()
                    self.tm.main_window.betting_widget.room_position_counter = 0

                if hasattr(self.tm, 'martin_service'):
                    self.tm.martin_service.reset_room_bet_status()
                    self.logger.info("[마틴] 승리 후 recent_results 및 상태 초기화 수행")

                self.tm.wait_first_result = False
                self.tm.just_won = False

            # N 4회 연속 감지 시 방 이동
            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                n_count = self.tm.excel_trading_service.choice_pick_system.consecutive_n_count
                if n_count >= 4:
                    self.logger.warning(f"[방 이동 트리거] Excel 처리 중 4회 연속 N값 감지 ({n_count}회)")
                    self.tm.change_room()
                    return

            last_column, new_game_count, recent_results, next_pick = result
            actual_game_count = game_state.get('round', 0)

            current_martin_step = getattr(self.tm.martin_service, 'current_step', 0)
            self.logger.info(f"현재 마틴 단계 확인: {current_martin_step+1}단계")

            last_marker = None
            if hasattr(self.tm.main_window.betting_widget, 'get_current_marker'):
                last_marker = self.tm.main_window.betting_widget.get_current_marker()
            elif hasattr(self.tm.main_window.betting_widget, 'markers'):
                markers = self.tm.main_window.betting_widget.markers
                for i in range(len(markers)-1, -1, -1):
                    if markers[i] in ["O", "X", "T"]:
                        last_marker = markers[i]
                        break

            self.logger.info(f"현재 위젯 마지막 마커: {last_marker}")

            is_martin_in_progress = (last_marker == "X")

            if previous_game_count > 10 and actual_game_count <= 5:
                self.logger.info(f"게임 카운트 초기화 감지! {previous_game_count} -> {actual_game_count}")
                self.tm.change_room()
                return

            # 새로운 결과 발생시만 처리
            if new_game_count > previous_game_count:
                # 한 사이클에서 이 코드는 한 번만 실행되도록 보장
                if not hasattr(self, '_processed_game_count') or self._processed_game_count != new_game_count:
                    self._processed_game_count = new_game_count
                    
                    self.process_previous_game_result(game_state, actual_game_count)

                    if game_state.get('latest_result') == 'T':
                        pass

                    # 3연패 감지
                    cs = getattr(self.tm.excel_trading_service, 'choice_pick_system', None)
                    if cs and hasattr(cs, 'pick_results') and len(cs.pick_results) >= 3:
                        if all(not r for r in cs.pick_results[-3:]):
                            self.logger.info("3연패 감지! 베팅 전 방 이동 실행")
                            self.tm.change_room(due_to_consecutive_n=False)
                            return

                    if hasattr(self.tm.martin_service, 'recent_results'):
                        recent_results = self.tm.martin_service.recent_results
                        if len(recent_results) >= 3 and all(not result for result in recent_results[-3:]):
                            self.logger.info("마틴 서비스에서 3연패 감지! 베팅 전 방 이동 실행")
                            self.tm.change_room(due_to_consecutive_n=False)
                            return

                    # 방 이동 체크
                    should_move = False
                    due_to_consecutive_n = False

                    if self.tm.excel_trading_service.should_change_room():
                        consecutive_n = getattr(self.tm.excel_trading_service.choice_pick_system, 'consecutive_n_count', 0) >= 3
                        if consecutive_n:
                            self.logger.info(f"N값 3회 이상 연속 감지 - 마틴 유지하며 방 이동")
                            should_move = True
                            due_to_consecutive_n = True
                        elif not is_martin_in_progress:
                            self.logger.info(f"초이스 픽 시스템 방 이동 신호 - 마틴 없거나 성공했으므로 방 이동")
                            should_move = True
                    elif actual_game_count >= 55:
                        widget_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                        if widget_pos == 0:
                            self.logger.info(f"처음 위치에서 55게임 도달 → 방 이동")
                            should_move = True

                    if should_move:
                        self.tm.change_room(due_to_consecutive_n=due_to_consecutive_n)
                        return

                    # ✅ 여기서 wait_first_result 명확히 체크
                    if getattr(self.tm, 'wait_first_result', False):
                        self.logger.info(f"첫 결과 대기 모드입니다. 아직 베팅하지 않습니다. (PICK: {next_pick})")
                        if previous_game_count > 0:
                            self.tm.current_pick = next_pick
                        return

                    # 추가 안전 장치: 유효하지 않은 PICK 검증
                    if next_pick not in ['P', 'B']:
                        self.logger.warning(f"유효하지 않은 PICK '{next_pick}'로 베팅 시도가 중단되었습니다.")
                        return

                    # 베팅 조건
                    if not self.tm.betting_service.has_bet_current_round and next_pick in ['P', 'B']:
                        if getattr(self.tm, 'just_won', False):
                            self.logger.info("[베팅 전 초기화] just_won 상태이므로 마커 리셋")
                            self.tm.main_window.betting_widget.reset_step_markers()
                            self.tm.main_window.betting_widget.room_position_counter = 0
                            self.tm.just_won = False

                        self.tm.main_window.update_betting_status(pick=next_pick)

                        if previous_game_count > 0:
                            # ✅ 베팅 직전에 고정 후보 확정
                            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                                cps = self.tm.excel_trading_service.choice_pick_system
                                if cps.fixed_candidate is None:
                                    cps.fixed_candidate = {
                                        'next_pick': next_pick,
                                        'betting_direction': cps.betting_direction
                                    }
                                    cps.current_candidate_index = 999  # 베팅 시점 확정 표시
                                    cps.consecutive_loss_with_candidate = 0
                                    self.logger.info(f"[후보 고정] 베팅 직전 PICK을 후보로 확정: {next_pick}, 방향: {cps.betting_direction}")
                            # ✅ 실제 베팅 수행
                            self.tm.bet_helper.place_bet(next_pick, actual_game_count)

                        else:
                            self.tm.current_pick = next_pick
                    else:
                        self.logger.info(f"베팅 조건 불충족: has_bet_current_round={self.tm.betting_service.has_bet_current_round}, next_pick={next_pick}")

                    self.tm.game_count = actual_game_count
                else:
                    self.logger.warning(f"[SKIP] 이미 게임 {new_game_count}의 새 결과를 처리했음")
            elif self.tm.betting_service.has_bet_current_round:
                last_bet = self.tm.betting_service.get_last_bet()
                if last_bet and last_bet['round'] < actual_game_count:
                    # 결과 대기
                    pass

        except Exception as e:
            self.logger.error(f"Excel 결과 처리 오류: {e}")
            
    def handle_tie_result(self, latest_result, game_state):
        try:
            if latest_result == 'T' and self.tm.game_count > 0:
                self.logger.info("무승부(T) 감지. 기존 PICK 유지 모드 활성화")
                
                # 무승부 시 pick 재생성 금지: 이전 pick 유지
                if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                    cps = self.tm.excel_trading_service.choice_pick_system
                    cps.skip_pick_generation = True  # <- 추가!!
                    self.logger.info("TIE 발생: 새 pick 생성 금지 설정 완료")
                
                # UI만 업데이트 (방 이동 없이)
                if hasattr(self.tm.main_window, 'room_log_widget'):
                    self.tm.main_window.room_log_widget.set_current_room(
                        self.tm.current_room_name, 
                        is_new_visit=False
                    )
                
                # 게임 분석 다시 시작 (pick 재생성은 skip_pick_generation이 막아줌)
                self.logger.info("무승부 후 게임 상태 다시 분석 시작")
                self.tm.analyze_current_game()
                self.tm.main_window.set_remaining_time(0, 0, 2)
                
        except Exception as e:
            self.logger.error(f"TIE 결과 처리 오류: {e}")


    def process_previous_game_result(self, game_state, new_game_count):
        """이전 게임 결과 처리 - 실패 시 16-17개 결과 적용 수정"""
        try:
            # ✅ 적중 마커 리셋 (적중 후 다음 턴)
            if getattr(self.tm, 'just_won', False):
                self.logger.info("이전 적중 후 UI 완전 초기화")
                self.tm.main_window.betting_widget.reset_step_markers()
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.tm.current_pick = None
                self.tm.just_won = False
                self.tm.main_window.update_betting_status(
                    room_name=self.tm.current_room_name,
                    pick=None,
                    reset_counter=True
                )

            # ✅ 베팅 결과 처리
            last_bet = self.tm.betting_service.get_last_bet()
            latest_result = game_state.get('latest_result')

            if last_bet and last_bet['type'] in ['P', 'B']:
                result_status = self.tm.bet_helper.process_bet_result(last_bet['type'], latest_result, new_game_count)

                # ❌ 실패 시 재파싱 로직 주석처리 (append 방식으로 대체됨)
                if result_status == 'lose':
                    if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                        failure_count = self.tm.excel_trading_service.choice_pick_system.failure_count
                        self.logger.info(f"[실패 처리] 현재 실패 카운트: {failure_count}, should_refresh_data: {self.tm.excel_trading_service.choice_pick_system.should_refresh_data}")

                        # 아래 불필요한 로직 전체 주석처리
                        # desired_count = min(15 + failure_count, 17)
                        # self.logger.info(f"[실패 처리] {desired_count}개 결과로 예측 엔진 갱신 시도")

                        # self.tm.devtools.driver.switch_to.default_content()
                        # html = self.tm.devtools.get_page_source()
                        # game_state = self.tm.game_monitoring_service.game_detector.detect_game_state(
                        #     html, desired_pb_count=desired_count
                        # )
                        # filtered_results = game_state.get("filtered_results", [])
                        # result_count = len(filtered_results)
                        # self.logger.info(f"[실패 처리] 수집된 결과 개수: {result_count}개 (목표: {desired_count}개)")

                        # if not self.tm.excel_trading_service.choice_pick_system.should_refresh_data:
                        #     if result_count >= desired_count:
                        #         self.tm.excel_trading_service.choice_pick_system.add_multiple_results(filtered_results[-desired_count:])
                        #         self.logger.info(f"[실패 처리] {desired_count}개 결과로 예측 엔진 갱신 완료")
                        #     elif result_count >= 15:
                        #         self.tm.excel_trading_service.choice_pick_system.add_multiple_results(filtered_results)
                        #         self.logger.info(f"[실패 처리] 가용한 {result_count}개 결과로 예측 엔진 갱신")
                        #     else:
                        #         self.logger.warning(f"[실패 처리] 예측 불가 - 결과 부족: {result_count}개")
                        # else:
                        #     self.logger.info("[실패 처리] should_refresh_data가 True - 데이터 누적 모드 아님")

            # ✅ 타이가 아닌 경우 베팅 상태 초기화
            if latest_result != 'T':
                self.tm.betting_service.reset_betting_state(new_round=new_game_count)

            # ✅ UI 상태 업데이트
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
        