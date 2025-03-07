# services/martin_service.py
import logging
from utils.settings_manager import SettingsManager

class MartinBettingService:
# services/martin_service.py
    def __init__(self, main_window, logger=None):
        """
        마틴 베팅 서비스 초기화
        
        Args:
            main_window (QMainWindow): 메인 윈도우 객체
            logger (logging.Logger, optional): 로깅을 위한 로거 객체
        """
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.main_window = main_window
        self.settings_manager = SettingsManager()
        
        # 마틴 설정 로드
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        
        # 로그에 설정값 출력
        self.logger.info(f"마틴 설정 로드 완료 - 단계 수: {self.martin_count}, 금액: {self.martin_amounts}")
        
        # 현재 마틴 단계 (0부터 시작, 인덱스로 사용)
        # 0일 때 self.martin_amounts[0] 값 사용
        self.current_step = 0
        self.consecutive_losses = 0
        self.total_bet_amount = 0
        self.win_count = 0
        self.lose_count = 0
        self.tie_count = 0  # TIE 카운트 추가
        
    def get_current_bet_amount(self):
        """
        현재 마틴 단계에 따른 베팅 금액을 반환합니다.
        매번 호출할 때마다 최신 설정을 다시 로드합니다.
        
        Returns:
            int: 베팅 금액
        """
        # 매번 호출 시 최신 설정 로드
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        self.logger.info(f"[INFO] 마틴 설정 다시 로드 - 단계: {self.martin_count}, 금액: {self.martin_amounts}")
        
        # 단계가 범위를 벗어나면 마지막 단계 금액 사용
        if self.current_step >= len(self.martin_amounts):
            self.logger.warning(f"마틴 단계({self.current_step})가 최대 단계({len(self.martin_amounts)})를 초과하여 마지막 단계 금액 사용: {self.martin_amounts[-1]:,}원")
            return self.martin_amounts[-1]
        
        # 현재 마틴 단계에 해당하는 금액 반환
        bet_amount = self.martin_amounts[self.current_step]
        self.logger.info(f"현재 마틴 단계: {self.current_step}, 설정된 마틴 금액 목록: {self.martin_amounts}, 현재 베팅 금액: {bet_amount:,}원")
        
        return bet_amount
    
    def process_bet_result(self, result_status):
        """
        베팅 결과에 따라 마틴 단계를 조정합니다.
        
        Args:
            result_status (str): 'win'(승리), 'lose'(패배), 'tie'(무승부)
                
        Returns:
            tuple: (현재 단계, 연속 패배 수)
        """
        # 현재 베팅 금액 기록
        current_bet = self.get_current_bet_amount()
        self.total_bet_amount += current_bet
        
        if result_status == "win":
            # 승리 시 마틴 단계 초기화
            self.current_step = 0
            self.consecutive_losses = 0
            self.win_count += 1
            self.logger.info(f"베팅 성공: 마틴 단계 초기화 (금액: {current_bet:,}원)")
        elif result_status == "tie":
            # 무승부 시 마틴 단계 유지 (변경 없음)
            self.tie_count += 1  # TIE 카운트 증가
            self.logger.info(f"베팅 무승부: 마틴 단계 유지 (금액: {current_bet:,}원)")
        else:  # "lose"
            # 패배 시 다음 마틴 단계로 진행
            self.consecutive_losses += 1
            self.current_step += 1
            self.lose_count += 1
            
            # 최대 마틴 단계 제한
            if self.current_step >= self.martin_count:
                self.logger.warning(f"최대 마틴 단계({self.martin_count})에 도달했습니다. 다음 베팅에서 초기화됩니다.")
                self.current_step = 0
            
            self.logger.info(f"베팅 실패: 마틴 단계 증가 -> {self.current_step}/{self.martin_count} (금액: {current_bet:,}원)")
        
        # UI 업데이트
        self.main_window.update_user_data(
            total_bet=self.total_bet_amount
        )
        
        return self.current_step, self.consecutive_losses

    def should_change_room(self):
        """
        방 이동이 필요한지 확인합니다.
        
        Returns:
            bool: 방 이동 필요 여부
        """
        # 배팅에 1번이라도 성공하면 방 이동
        # win_count가 0보다 크면 적어도 한 번 이상 이겼다는 의미
        if self.win_count > 0:
            self.logger.info(f"베팅 성공 횟수: {self.win_count}, 방 이동 필요")
            return True
        return False
    
    def reset(self):
        """
        마틴 베팅 상태를 초기화합니다.
        """
        self.current_step = 0
        self.consecutive_losses = 0
        self.win_count = 0
        self.lose_count = 0
        self.tie_count = 0  # TIE 카운트도 초기화
        self.logger.info("마틴 베팅 상태 초기화 완료")
    
    def update_settings(self):
        """
        설정이 변경된 경우 마틴 설정을 다시 로드합니다.
        """
        # 이전 설정 값 저장
        old_martin_count = self.martin_count
        old_martin_amounts = self.martin_amounts.copy() if self.martin_amounts else []
        
        # 새 설정 로드
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        
        # 설정이 변경되었는지 확인하고 로그 출력
        if old_martin_count != self.martin_count or old_martin_amounts != self.martin_amounts:
            self.logger.info(f"[INFO] 마틴 설정 변경됨!")
            self.logger.info(f"  이전: 단계={old_martin_count}, 금액={old_martin_amounts}")
            self.logger.info(f"  현재: 단계={self.martin_count}, 금액={self.martin_amounts}")
        else:
            self.logger.info(f"[INFO] 마틴 설정 업데이트 (변경 없음) - 단계: {self.martin_count}, 금액: {self.martin_amounts}")