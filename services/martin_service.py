import logging
from utils.settings_manager import SettingsManager
from utils.trading_manager_helpers import get_widget_position

class MartinBettingService:
    def __init__(self, main_window, logger=None):
        """마틴 베팅 서비스 초기화"""
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.main_window = main_window
        self.settings_manager = SettingsManager()
        
        # 마틴 설정 로드
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        self.logger.info(f"마틴 설정 로드 완료 - 단계 수: {self.martin_count}, 금액: {self.martin_amounts}")
        
        # 상태 변수 초기화
        # current_step 속성 추가 - 호환성을 위해 유지
        self.current_step = 0  # 위젯의 position_counter와 동기화할 값
        self.consecutive_losses = 0
        self.total_bet_amount = 0
        self.win_count = 0
        self.lose_count = 0
        self.tie_count = 0
        self.result_counter = 0
        self.betting_counter = 0
        self.current_game_position = {}
        self.need_room_change = False
        self.has_bet_in_current_room = False
        
        # 역배팅 관련 변수
        self.recent_results = []  # 최근 결과 기록 (True=승리, False=패배)
        self.game_count_for_mode = 0  # 모드 결정을 위한 게임 카운터
        self.mode_game_threshold = 5  # 모드 결정을 위한 게임 수 임계값
        self.original_pick = None  # 원래 선택한 PICK 값
        self.diff_history = []  # 10판 단위 승패차 기록
        self.current_direction = 'forward'  # 현재 방향 (forward / reverse)

    def get_current_bet_amount(self):
        """현재 마틴 단계에 따른 베팅 금액을 반환합니다."""
        # 최신 설정 리프레시
        self._refresh_settings()
        
        # 위젯 포지션 확인 - 항상 최신 값 사용
        widget_position = get_widget_position(self.main_window)
        
        # 동기화 강화 - 항상 위젯 포지션으로 마틴 단계 갱신
        self.current_step = widget_position
        
        # 마틴 단계 수 확인 및 적용
        martin_stages = len(self.martin_amounts)
        if martin_stages == 0:
            self.logger.error("❌ 마틴 금액 설정이 비어있음!")
            return 10000  # 기본값
        
        effective_martin_step = widget_position % martin_stages
        
        # 계산된 단계에 해당하는 금액 반환
        bet_amount = self.martin_amounts[effective_martin_step]
        
        # 🔥 디버깅 강화: 실제 위젯 상태도 확인
        actual_widget_pos = 0
        if hasattr(self.main_window, 'betting_widget'):
            actual_widget_pos = getattr(self.main_window.betting_widget, 'room_position_counter', 0)
            if actual_widget_pos != widget_position:
                self.logger.warning(f"⚠️ 위젯 포지션 불일치! helper: {widget_position}, widget: {actual_widget_pos}")
                # 실제 위젯 값 사용
                widget_position = actual_widget_pos
                effective_martin_step = widget_position % martin_stages
                bet_amount = self.martin_amounts[effective_martin_step]
        
        self.logger.info(f"💰 현재 베팅 금액: {bet_amount:,}원 (위젯: {widget_position+1}번, 마틴: {effective_martin_step+1}단계)")
        self.logger.info(f"   마틴 금액 설정: {self.martin_amounts}")
        
        return bet_amount


    def _refresh_settings(self):
        """최신 마틴 설정 로드"""
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()

    def process_bet_result(self, result_status, game_count=None):
        """
        베팅 결과 처리 - 위젯의 position_counter 기준으로 작동
        """
        # 현재 베팅 금액 기록
        current_bet = self.get_current_bet_amount()
        self.total_bet_amount += current_bet
        
        # 카운터 증가
        self.result_counter += 1
        self.betting_counter += 1
        current_result_position = self.betting_counter
        
        # 게임 카운트 기록
        if game_count is not None:
            self.current_game_position[game_count] = current_result_position
        
        # 현재 위젯 위치 확인 (로그용)
        widget_position = 0
        widget_position = get_widget_position(self.main_window)

        self.logger.info(f"[마틴] 결과 처리 전 위젯 포지션: {widget_position+1}")
        
        # 호환성을 위해 current_step 동기화
        self.current_step = widget_position
        
        self.logger.info(f"[마틴] 베팅 결과 처리: {result_status}")
        
        # 결과에 따른 처리 (승리, 패배, 무승부)
        if result_status == "win":
            # 승리 결과 처리
            result = self._handle_win_result(current_result_position)
            # ✅ 승리 시 연속 패배 카운터 초기화
            self.consecutive_failures = 0
            self.recent_results = []  # 중요: 승리 시 패배 기록 초기화
            self.logger.info("✅ 승리로 consecutive_failures와 recent_results 초기화")
        elif result_status == "tie":
            # 무승부 결과 처리
            result = self._handle_tie_result(current_result_position)
        else:  # "lose"
            # 패배 결과 처리
            result = self._handle_lose_result(current_result_position)
        
        # 베팅 결과를 리스트에 추가
        if result_status == "win":
            self.recent_results = []  # 승리 시 리스트 비우고 시작
            self.recent_results.append(True)
        else:
            if result_status == "lose":
                self.recent_results.append(False)
            # tie는 무시
        
        # 최근 5개만 유지
        if len(self.recent_results) > 5:
            self.recent_results = self.recent_results[-5:]
        
        # 연속 패배 확인 - 새로운 로직 추가
        self._check_consecutive_failures()
        
        # 위젯 포지션 확인 후 로깅
        new_position = get_widget_position(self.main_window)
        self.logger.info(f"[마틴] 결과 처리 후 위젯 포지션: {new_position+1}")
        self.current_step = new_position
        
        return result

    # 새로운 메서드 추가
    def _check_consecutive_failures(self):
        """연속 패배 확인"""
        # 최근 결과에서 연속 패배 확인
        consecutive_count = 0
        for result in reversed(self.recent_results):
            if result == False:
                consecutive_count += 1
            else:
                break  # 승리를 만나면 중단
        
        # 3연패 이상인 경우 방 이동 필요 플래그 설정
        if consecutive_count >= 3:
            self.need_room_change = True
            self.logger.info(f"✅ {consecutive_count}연패 감지 (recent_results: {self.recent_results}) - 방 이동 플래그 활성화")
            # 방 로그 위젯에 방 변경 예정 알림
            if hasattr(self.main_window, 'room_log_widget'):
                self.main_window.room_log_widget.has_changed_room = True
                self.logger.info("[마틴] 3연패로 방 로그 위젯에 방 변경 예정 알림")
        else:
            # 3연패가 아닌 경우 플래그 유지 (다른 조건에서 설정된 경우 유지)
            if not self.need_room_change:
                self.logger.info(f"현재 {consecutive_count}연패 상태 (방 이동 필요 없음)")
                
    def _handle_win_result(self, position):
        """
        승리 결과 처리 - 위젯의 카운터는 TradingManagerBet에서 0으로 설정함
        """
        self.consecutive_losses = 0
        self.need_room_change = True  # 승리 시 방 이동 필요 (새로운 픽 선택을 위해)
        self.has_bet_in_current_room = True
        self.logger.info(f"[마틴] 베팅 성공: 승리 처리 완료, 다음에 새 방으로 이동하여 새 픽 선택")
        
        # 방 로그 위젯에 방 변경 예정 알림
        if hasattr(self.main_window, 'room_log_widget'):
            self.main_window.room_log_widget.has_changed_room = True
            self.logger.info("[마틴] 방 로그 위젯에 방 변경 예정 알림")
        
        # 🔥 승리 시 마커만 표시 (카운터 리셋은 reset_after_win에서 처리)
        if hasattr(self.main_window, 'betting_widget'):
            widget = self.main_window.betting_widget
            current_pos = getattr(widget, 'room_position_counter', 0)
            # 승리 마커 표시
            widget.set_step_marker(current_pos, "O")
            self.logger.info(f"[마틴] 승리 마커 표시 - 현재 위치: {current_pos}")
        
        # 위젯 포지션 확인
        new_position = get_widget_position(self.main_window)
        self.logger.info(f"[마틴] 결과 처리 후 위젯 포지션: {new_position}")
        self.current_step = new_position
        
        return 0, self.consecutive_losses, position
        
    def _handle_tie_result(self, position):
        """
        무승부 결과 처리 - 위젯 카운터는 변경하지 않음
        """
        self.tie_count += 1
        self.has_bet_in_current_room = False  # 같은 방에서 재배팅 가능하도록 설정
        self.need_room_change = False
        self.logger.info(f"[마틴] 베팅 무승부: 같은 방에서 동일 단계로 재배팅")
        
        # 타이 직후 플래그 설정
        if hasattr(self.main_window, 'trading_manager'):
            self.main_window.trading_manager.had_tie_last_round = True
            self.logger.info(f"[마틴] 타이 직후 플래그 설정")
        
        # 현재 위젯 포지션 반환
        widget_position = 0
        widget_position = get_widget_position(self.main_window)

        # 호환성을 위해 current_step 동기화
        self.current_step = widget_position
            
        return widget_position, self.consecutive_losses, position

    def _handle_lose_result(self, position):
        """
        패배 결과 처리 - 위젯 카운터를 직접 증가시킴
        """
        self.consecutive_losses += 1
        self.lose_count += 1
        self.has_bet_in_current_room = True

        # 3연패 검사에서 플래그가 설정되지 않은 경우에만 False로 설정
        if not getattr(self, 'need_room_change', False):
            self.need_room_change = False
            self.logger.info(f"[마틴] 베팅 실패: 패배 처리 완료, 같은 방에서 계속")
        
        # 위젯 카운터 증가 - 다음 마틴 단계로 이동
        if hasattr(self.main_window, 'betting_widget'):
            widget = self.main_window.betting_widget
            current_pos = getattr(widget, 'room_position_counter', 0)
            self.logger.info(f"[마틴] 패배 처리 - 현재 위치: {current_pos}")
            
            # 패배 마커 표시
            widget.set_step_marker(current_pos, "X")
            
            # 🔥 카운터를 명시적으로 증가 (set_step_marker는 더 이상 카운터를 증가시키지 않음)
            widget.room_position_counter = current_pos + 1
            self.logger.info(f"[마틴] 카운터 증가: {current_pos} → {current_pos + 1}")
            
            # 🔥 증가 후 즉시 확인
            new_pos = widget.room_position_counter
            if new_pos != current_pos + 1:
                self.logger.error(f"❌ 카운터 증가 실패! 예상: {current_pos + 1}, 실제: {new_pos}")
            else:
                self.logger.info(f"✅ 카운터 증가 확인: {new_pos}")
                
            # 다음 베팅 금액 미리 계산 및 로깅
            next_bet = self.get_current_bet_amount()
            self.logger.info(f"💰 다음 베팅 금액 예상: {next_bet:,}원")
        
        # 증가된 위젯 포지션 가져오기
        widget_position = get_widget_position(self.main_window)
        
        # 호환성을 위해 current_step 동기화
        self.current_step = widget_position
        
        return widget_position, self.consecutive_losses, position

    def get_result_position_for_game(self, game_count):
        """특정 게임 카운트에 해당하는 결과 위치를 반환합니다."""
        # 게임 카운트에 해당하는 위치가 있으면 반환
        if game_count in self.current_game_position:
            return self.current_game_position[game_count]
        
        # 기록에 없으면 배팅 카운터 반환
        return self.betting_counter
    
    def should_change_room(self):
        """
        방 이동이 필요한지 확인합니다.
        Returns:
            bool: 방 이동 필요 여부
        """
        
        # 🔥 마틴게일 전략에서는 3연패 조건을 사용하지 않음
        # 마지막 마틴 단계 실패 시 game_processor에서 직접 처리
        
        # 방 이동 플래그 확인
        if self.need_room_change:
            self.logger.info(f"[마틴] 방 이동 플래그가 설정되어 있어 방 이동 필요")
            return True
        
        return False

    def reset_room_bet_status(self):
        """새 방 입장 시 현재 방 배팅 상태 초기화"""
        self.has_bet_in_current_room = False
        self.need_room_change = False
        
        # ✅ 추가: recent_results 초기화
        if hasattr(self, 'recent_results'):
            self.recent_results = []
            self.logger.info("[마틴] 새 방 입장으로 recent_results 초기화")
        
        # 🔥 새 방 입장 시 위젯 카운터도 0으로 초기화 (마틴 1단계부터 시작)
        if hasattr(self.main_window, 'betting_widget'):
            self.main_window.betting_widget.room_position_counter = 0
            self.main_window.betting_widget.reset_step_markers()
            self.logger.info("[마틴] 새 방 입장으로 위젯 카운터도 0으로 초기화")
        
        self.logger.info("[마틴] 새 방 입장으로 방 배팅 상태 초기화 - 1단계부터 시작")

    def reset(self):
        """마틴 베팅 상태를 완전히 초기화합니다."""
        # 연속 실패 카운터 초기화
        self.consecutive_losses = 0
        
        # 호환성을 위해 current_step 초기화
        self.current_step = 0
        
        # 카운터 초기화
        self.win_count = 0
        self.lose_count = 0
        self.tie_count = 0
        self.result_counter = 0
        self.betting_counter = 0
        self.current_game_position = {}
        
        # 방 이동 플래그 초기화
        self.need_room_change = False
        self.has_bet_in_current_room = False
        
        # 역배팅 변수 초기화
        self.recent_results = []
        self.game_count_for_mode = 0
        self.original_pick = None
        
        self.logger.info("[마틴] 마틴 베팅 상태 완전 초기화 완료")
        
        # 마틴 설정 최신 상태로 다시 로드
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        
    def update_settings(self):
        """설정이 변경된 경우 마틴 설정을 다시 로드합니다."""
        # 이전 설정 값 저장
        old_martin_count = self.martin_count
        old_martin_amounts = self.martin_amounts.copy() if self.martin_amounts else []
        
        # 새 설정 로드 - 설정 매니저도 리프레시
        self.settings_manager = SettingsManager()
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        
        # 목표 금액 및 Double & Half 설정도 로그에 출력
        target_amount = self.settings_manager.get_target_amount()
        double_half_start, double_half_stop = self.settings_manager.get_double_half_settings()
        
        # 설정이 변경되었는지 확인하고 로그 출력
        if old_martin_count != self.martin_count or old_martin_amounts != self.martin_amounts:
            self.logger.info(f"[마틴] 설정 변경됨! 이전: 단계={old_martin_count}, 금액={old_martin_amounts}")
            self.logger.info(f"[마틴] 새 설정: 단계={self.martin_count}, 금액={self.martin_amounts}")
        
        # 추가 설정 로그
        self.logger.info(f"[마틴] 목표 금액: {target_amount:,}원")
        self.logger.info(f"[마틴] Double & Half 설정: 시작={double_half_start}, 중지={double_half_stop}")
        
        # 역배팅 모드 임계값 설정 - 기본 5게임
        self.mode_game_threshold = 5  # 필요시 설정 파일에서 로드
        self.logger.info(f"[역배팅] 모드 결정 게임 수: {self.mode_game_threshold}게임")
        
        return True
        
    def get_reverse_bet_pick(self, original_pick):
        self.original_pick = original_pick
        self.logger.info(f"[PICK 결정] 현재 방향: {self.current_direction}, 원 PICK: {original_pick}")

        if self.current_direction == 'normal':
            return original_pick
        if original_pick == 'P':
            return 'B'
        elif original_pick == 'B':
            return 'P'
        return original_pick

    def update_bet_direction_by_diff(self, game_count):
        """10판 단위로 승패차 기록하고, 2연속 손실이면 방향 전환"""
        
        if game_count % 10 != 0 or game_count < 30:
            return

        current_diff = self.win_count - self.lose_count
        self.diff_history.append(current_diff)

        self.logger.info(f"[DEBUG] game_count={game_count}, win={self.win_count}, lose={self.lose_count}, current_diff={current_diff}")
        self.logger.info(f"[DEBUG] diff_history = {self.diff_history}")

        if len(self.diff_history) >= 3:
            a, b, c = self.diff_history[-3:]
            # self.logger.info(f"[DEBUG] 최근 3개 diff: {a}, {b}, {c}")

            if b < a and c < b:
                old = self.current_direction
                self.current_direction = 'reverse' if self.current_direction == 'forward' else 'forward'
                self.logger.info(f"[방향 전환] 2연속 손실 감지 → {old.upper()} → {self.current_direction.upper()}")

                if hasattr(self.main_window.betting_widget, 'update_reverse_mode'):
                    self.main_window.betting_widget.update_reverse_mode(self.current_direction == 'reverse')

    def reset_after_win(self):
        """승리 후 마틴 상태 초기화 - 검증 로직 포함"""
        try:
            self.logger.info("[마틴] 승리 후 마틴 상태 초기화 시작")
            
            # 마틴 상태 초기화
            self.consecutive_losses = 0
            self.current_step = 0
            self.need_room_change = True
            self.has_bet_in_current_room = True
            
            # 위젯 카운터 강제 0으로 초기화 (검증 포함)
            if hasattr(self.main_window, 'betting_widget'):
                widget = self.main_window.betting_widget
                
                # prevent_reset 플래그 해제
                widget.prevent_reset = False
                
                # 위젯 카운터 초기화
                widget.room_position_counter = 0
                widget.reset_step_markers()
                
                # 초기화 검증
                if widget.room_position_counter != 0:
                    self.logger.error(f"🚨 위젯 카운터 초기화 실패! 현재 값: {widget.room_position_counter}")
                    widget.room_position_counter = 0  # 재시도
                    self.logger.info("🔄 위젯 카운터 재초기화 완료")
                else:
                    self.logger.info("✅ 위젯 카운터 정상 초기화 (0)")
            
            # 현재 베팅 금액 확인 (디버깅용)
            current_bet = self.get_current_bet_amount()
            self.logger.info(f"🎯 초기화 후 다음 베팅 금액: {current_bet:,}원 (1단계)")
            
            self.logger.info("[마틴] 승리 후 마틴 상태 완전 초기화 완료 - 다음 방에서 1단계부터 시작")
            
        except Exception as e:
            self.logger.error(f"승리 후 마틴 초기화 오류: {e}")
            # 강제로라도 위젯 카운터는 0으로 설정
            if hasattr(self.main_window, 'betting_widget'):
                self.main_window.betting_widget.room_position_counter = 0
                self.logger.info("🚨 예외 발생으로 위젯 카운터 강제 초기화")

    def record_loss(self):
        """패배 기록"""
        self.consecutive_losses += 1
        self.lose_count += 1
        self.logger.info(f"[마틴] 패배 기록 - 연속 패배: {self.consecutive_losses}회")