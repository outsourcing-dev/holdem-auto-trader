# services/martin_service.py

import logging
from utils.settings_manager import SettingsManager

class MartinBettingService:
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
        
        # 결과 표시용 카운터 (방 내에서의 순차적 위치)
        self.result_counter = 0  # 같은 방 내에서의 결과 위치 카운터
        self.betting_counter = 0  # 배팅 횟수 카운터 추가 (실제 배팅한 횟수)
        self.current_game_position = {}  # 게임 라운드별 위치 추적용 딕셔너리 추가

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
    
    def process_bet_result(self, result_status, game_count=None):
        """
        베팅 결과에 따라 마틴 단계를 조정합니다.
        
        Args:
            result_status (str): 'win'(승리), 'lose'(패배), 'tie'(무승부)
                
        Returns:
            tuple: (현재 단계, 연속 패배 수, 결과 위치)
        """
        # 현재 베팅 금액 기록
        current_bet = self.get_current_bet_amount()
        self.total_bet_amount += current_bet
        
        # 결과 표시 위치 카운터 증가 (방 내에서만 유효한 순차적 위치)
        self.result_counter += 1
        
        # 배팅 카운터 증가 (실제 배팅 횟수 - 무승부 포함)
        self.betting_counter += 1
        
        current_result_position = self.betting_counter  # 배팅 카운터를 위치로 사용
        
        # 게임 카운트가 제공된 경우, 해당 게임의 위치 기록
        if game_count is not None:
            self.current_game_position[game_count] = current_result_position
            self.logger.info(f"[마틴] 게임 {game_count}의 결과 위치를 {current_result_position}으로 기록")
        
        # 로그 추가
        self.logger.info(f"[마틴] 베팅 결과 처리: {result_status}, 현재 단계: {self.current_step}, 단계값: {current_bet:,}원")
        
        if result_status == "win":
            # 승리 시 마틴 단계 초기화
            self.current_step = 0
            self.consecutive_losses = 0
            self.win_count += 1
            self.logger.info(f"[마틴] 베팅 성공: 마틴 단계 초기화 (금액: {current_bet:,}원), 총 성공 수: {self.win_count}")
        elif result_status == "tie":
            # 무승부 시 마틴 단계 유지 (변경 없음)
            self.tie_count += 1  # TIE 카운트 증가
            self.logger.info(f"[마틴] 베팅 무승부: 마틴 단계 유지 (금액: {current_bet:,}원), 총 무승부 수: {self.tie_count}")
        else:  # "lose"
            # 패배 시 다음 마틴 단계로 진행
            self.consecutive_losses += 1
            self.current_step += 1
            self.lose_count += 1
            
            # 최대 마틴 단계 제한
            if self.current_step >= self.martin_count:
                self.logger.warning(f"[마틴] 최대 마틴 단계({self.martin_count})에 도달했습니다. 다음 베팅에서 초기화됩니다.")
                self.current_step = 0
            
            self.logger.info(f"[마틴] 베팅 실패: 마틴 단계 증가 -> {self.current_step}/{self.martin_count} (금액: {current_bet:,}원), 총 실패 수: {self.lose_count}")
        
        # UI 업데이트
        self.main_window.update_user_data(
            total_bet=self.total_bet_amount
        )
        
        # 로그 추가
        self.logger.info(f"[마틴] 현재 상태: 성공:{self.win_count}, 실패:{self.lose_count}, 무승부:{self.tie_count}")
        
        return self.current_step, self.consecutive_losses, current_result_position

    def get_result_position_for_game(self, game_count):
        """
        특정 게임 카운트에 해당하는 결과 위치를 반환합니다.
        기록에 없으면 현재 결과 카운터 값을 반환합니다.
        
        Args:
            game_count (int): 게임 카운트
            
        Returns:
            int: 결과 위치
        """
        # 게임 카운트에 해당하는 위치가 있으면 반환
        if game_count in self.current_game_position:
            return self.current_game_position[game_count]
        
        # 기록에 없으면 배팅 카운터 반환 (변경 사항)
        return self.betting_counter
    
    def should_change_room(self):
        """
        방 이동이 필요한지 확인합니다.
        
        Returns:
            bool: 방 이동 필요 여부
        """
        # 배팅에 1번이라도 성공하면 방 이동
        # win_count가 0보다 크면 적어도 한 번 이상 이겼다는 의미
        if self.win_count > 0:
            self.logger.info(f"[마틴] 베팅 성공 횟수: {self.win_count}, 방 이동 필요")
            # 추가 로그로 더 명확하게 정보 출력
            self.logger.info(f"[마틴] 방 이동 상태: 성공:{self.win_count}, 실패:{self.lose_count}, 무승부:{self.tie_count}")
            return True
        
        # 타이가 있었는지 로그
        if self.tie_count > 0:
            self.logger.info(f"[마틴] 무승부가 있었지만 승리가 없어 방 이동하지 않음 (무승부 수: {self.tie_count})")
        
        return False

    def reset(self):
        """
        마틴 베팅 상태를 완전히 초기화합니다.
        모든 관련 변수를 기본값으로 재설정합니다.
        """
        # 마틴 단계 완전 초기화
        self.current_step = 0  # 0 = 1단계 베팅
        self.consecutive_losses = 0
        
        # 카운터 초기화
        self.win_count = 0
        self.lose_count = 0
        self.tie_count = 0
        self.result_counter = 0
        self.betting_counter = 0  # 배팅 카운터 초기화
        self.current_game_position = {}  # 게임 위치 기록도 초기화
        
        # 총 베팅 금액은 초기화하지 않음 (기록 보존)
        # self.total_bet_amount = 0  # 필요시 주석 해제
        
        # 로그 남기기
        self.logger.info("[마틴] 마틴 베팅 상태 완전 초기화 완료 - 단계: 1단계, 연속 패배: 0, 베팅 카운터: 0")
        
        # 마틴 설정 최신 상태로 다시 로드 (선택적)
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        self.logger.info(f"[마틴] 설정 재로드 - 단계 수: {self.martin_count}, 금액: {self.martin_amounts}")
        
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