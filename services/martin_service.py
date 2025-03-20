# services/martin_service.py 리팩토링
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
        self.current_step = 0
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

    def get_current_bet_amount(self):
        """현재 마틴 단계에 따른 베팅 금액을 반환합니다."""
        # 최신 설정 로드
        self._refresh_settings()
        
        # 단계가 범위를 벗어나면 마지막 단계 금액 사용
        if self.current_step >= len(self.martin_amounts):
            self.logger.warning(f"마틴 단계({self.current_step})가 최대 단계({len(self.martin_amounts)})를 초과하여 마지막 단계 금액 사용: {self.martin_amounts[-1]:,}원")
            return self.martin_amounts[-1]
        
        # 현재 마틴 단계에 해당하는 금액 반환
        bet_amount = self.martin_amounts[self.current_step]
        self.logger.info(f"현재 마틴 단계: {self.current_step+1}, 베팅 금액: {bet_amount:,}원")
        
        return bet_amount
    
    def _refresh_settings(self):
        """최신 마틴 설정 로드"""
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
    
    def process_bet_result(self, result_status, game_count=None):
        """베팅 결과에 따라 마틴 단계를 조정합니다."""
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
        
        self.logger.info(f"[마틴] 베팅 결과 처리: {result_status}, 현재 단계: {self.current_step+1}")
        
        # 결과에 따른 처리
        if result_status == "win":
            return self._handle_win_result(current_result_position)
        elif result_status == "tie":
            return self._handle_tie_result(current_result_position)
        else:  # "lose"
            return self._handle_lose_result(current_result_position)
        
    def _handle_win_result(self, position):
        """승리 결과 처리"""
        self.current_step = 0
        self.consecutive_losses = 0
        self.win_count += 1
        self.need_room_change = True
        self.has_bet_in_current_room = True
        self.logger.info(f"[마틴] 베팅 성공: 마틴 단계 초기화, 방 이동 필요 설정")
        return self.current_step, self.consecutive_losses, position
        
    def _handle_tie_result(self, position):
        """무승부 결과 처리"""
        self.tie_count += 1
        self.has_bet_in_current_room = False
        self.need_room_change = False
        self.logger.info(f"[마틴] 베팅 무승부: 마틴 단계 유지, 같은 방에서 재시도")
        return self.current_step, self.consecutive_losses, position
        
    def _handle_lose_result(self, position):
        """패배 결과 처리"""
        self.consecutive_losses += 1
        self.current_step += 1
        self.lose_count += 1
        self.has_bet_in_current_room = True
        
        # 최대 마틴 단계 도달 시 방 이동 플래그 설정
        if self.current_step >= self.martin_count:
            self.need_room_change = True
            self.current_step = 0  # 다음 방을 위해 초기화
        else:
            # 패배 후 다음 단계로 진행하기 위해 방 이동 필요
            self.need_room_change = True
            
        return self.current_step, self.consecutive_losses, position

    def get_result_position_for_game(self, game_count):
        """특정 게임 카운트에 해당하는 결과 위치를 반환합니다."""
        # 게임 카운트에 해당하는 위치가 있으면 반환
        if game_count in self.current_game_position:
            return self.current_game_position[game_count]
        
        # 기록에 없으면 배팅 카운터 반환
        return self.betting_counter
    
    def should_change_room(self):
        """방 이동이 필요한지 확인합니다."""
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
        # 마틴 단계 완전 초기화
        self.current_step = 0
        self.consecutive_losses = 0
        
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
        
        self.logger.info("[마틴] 마틴 베팅 상태 완전 초기화 완료")
        
        # 마틴 설정 최신 상태로 다시 로드
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        
    # services/martin_service.py의 update_settings 메서드 강화

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
        
        return True