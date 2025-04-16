import logging
from utils.settings_manager import SettingsManager

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
        # 위젯 포지션 확인 - 항상 최신 값 사용
        widget_position = 0
        if hasattr(self.main_window, 'betting_widget') and hasattr(self.main_window.betting_widget, 'room_position_counter'):
            widget_position = self.main_window.betting_widget.room_position_counter
        
        # 동기화 강화 - 항상 위젯 포지션으로 마틴 단계 갱신
        self.current_step = widget_position
        
        # 마틴 단계 수 확인 및 적용
        martin_stages = len(self.martin_amounts)
        effective_martin_step = widget_position % martin_stages
        
        # 계산된 단계에 해당하는 금액 반환
        bet_amount = self.martin_amounts[effective_martin_step]
        self.logger.info(f"현재 베팅 금액: {bet_amount:,}원 (위젯: {widget_position+1}번, 마틴: {effective_martin_step+1}단계)")
        
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
        if hasattr(self.main_window, 'betting_widget') and hasattr(self.main_window.betting_widget, 'room_position_counter'):
            widget_position = self.main_window.betting_widget.room_position_counter
            self.logger.info(f"[마틴] 결과 처리 전 위젯 포지션: {widget_position+1}")
        
        # 호환성을 위해 current_step 동기화
        self.current_step = widget_position
        
        self.logger.info(f"[마틴] 베팅 결과 처리: {result_status}")
        
        # 결과에 따른 처리 (승리, 패배, 무승부)
        if result_status == "win":
            # 승리 결과 처리
            result = self._handle_win_result(current_result_position)
        elif result_status == "tie":
            # 무승부 결과 처리
            result = self._handle_tie_result(current_result_position)
        else:  # "lose"
            # 패배 결과 처리
            result = self._handle_lose_result(current_result_position)
        
        # 베팅 결과를 리스트에 추가
        self.recent_results.append(result_status == "win")
        
        # 최근 5개만 유지
        if len(self.recent_results) > 5:
            self.recent_results = self.recent_results[-5:]
        
        # 위젯 포지션 확인 후 로깅
        if hasattr(self.main_window, 'betting_widget') and hasattr(self.main_window.betting_widget, 'room_position_counter'):
            new_position = self.main_window.betting_widget.room_position_counter
            self.logger.info(f"[마틴] 결과 처리 후 위젯 포지션: {new_position+1}")
            # 호환성을 위해 current_step 동기화
            self.current_step = new_position
        
        return result

    def _handle_win_result(self, position):
        """
        승리 결과 처리 - 위젯의 카운터는 TradingManagerBet에서 0으로 설정함
        """
        self.consecutive_losses = 0
        self.need_room_change = True  # 승리 시 방 이동 필요 (새로운 픽 선택을 위해)
        self.has_bet_in_current_room = True
        self.logger.info(f"[마틴] 베팅 성공: 승리 처리 완료, 다음에 새 방으로 이동하여 새 픽 선택")
        
        # 위젯 포지션을 0으로 설정
        if hasattr(self.main_window, 'betting_widget') and hasattr(self.main_window.betting_widget, 'room_position_counter'):
            self.main_window.betting_widget.room_position_counter = 0
            # 호환성을 위해 current_step도 0으로 설정
            self.current_step = 0
        
        return 0, self.consecutive_losses, position
        
    def _handle_tie_result(self, position):
        """
        무승부 결과 처리 - 위젯 카운터는 변경하지 않음
        """
        self.tie_count += 1
        self.has_bet_in_current_room = False  # 같은 방에서 재배팅 가능하도록 설정
        self.need_room_change = False
        self.logger.info(f"[마틴] 베팅 무승부: 같은 방에서 동일 단계로 재배팅")
        
        # 현재 위젯 포지션 반환
        widget_position = 0
        if hasattr(self.main_window, 'betting_widget') and hasattr(self.main_window.betting_widget, 'room_position_counter'):
            widget_position = self.main_window.betting_widget.room_position_counter
            # 호환성을 위해 current_step 동기화
            self.current_step = widget_position
            
        return widget_position, self.consecutive_losses, position
        
    def _handle_lose_result(self, position):
        """
        패배 결과 처리 - 위젯 카운터는 TradingManagerBet에서 증가시킴
        """
        self.consecutive_losses += 1
        self.lose_count += 1
        self.has_bet_in_current_room = True

        # 3연패 검사에서 플래그가 설정되지 않은 경우에만 False로 설정
        if not getattr(self, 'need_room_change', False):
            self.need_room_change = False
            self.logger.info(f"[마틴] 베팅 실패: 패배 처리 완료, 같은 방에서 계속")
        
        # 현재 위젯 포지션 (TradingManagerBet에서 이미 증가됨)
        widget_position = 0
        if hasattr(self.main_window, 'betting_widget') and hasattr(self.main_window.betting_widget, 'room_position_counter'):
            widget_position = self.main_window.betting_widget.room_position_counter
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
        """방 이동이 필요한지 확인합니다."""
        # 2연패로 인한 방 이동 필요 (3 → 2로 변경)
        if hasattr(self, 'recent_results') and len(self.recent_results) >= 2:
            # 최근 2개 결과가 모두 False(패배)인지 확인
            recent_two = self.recent_results[-2:]
            if len(recent_two) == 2 and all(not result for result in recent_two):
                self.logger.info(f"[마틴] 2연패로 인한 방 이동 필요: {recent_two}")
                return True
        
        # 현재 방에서 이미 배팅했는지 확인
        if self.has_bet_in_current_room:
            self.logger.info(f"[마틴] 현재 방에서 이미 배팅했으므로 방 이동 필요")
            return True
        
        # 방 이동 플래그 확인
        if self.need_room_change:
            self.logger.info(f"[마틴] 방 이동 플래그가 설정되어 있어 방 이동 필요")
            return True
        
        return False

    def reset_room_bet_status(self):
        """새 방 입장 시 현재 방 배팅 상태 초기화"""
        self.has_bet_in_current_room = False
        self.need_room_change = False
        self.logger.info("[마틴] 새 방 입장으로 방 배팅 상태 초기화")

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

        if self.current_direction == 'forward':
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
            self.logger.info(f"[DEBUG] 최근 3개 diff: {a}, {b}, {c}")

            if b < a and c < b:
                old = self.current_direction
                self.current_direction = 'reverse' if self.current_direction == 'forward' else 'forward'
                self.logger.info(f"[방향 전환] 2연속 손실 감지 → {old.upper()} → {self.current_direction.upper()}")

                if hasattr(self.main_window.betting_widget, 'update_reverse_mode'):
                    self.main_window.betting_widget.update_reverse_mode(self.current_direction == 'reverse')