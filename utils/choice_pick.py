# utils/choice_pick.py (대폭 단순화)
import logging
from typing import List, Optional

class ChoicePickSystem:
    """
    초이스 픽 시스템 - 서버 기반으로 단순화
    서버에서 연패 방 정보를 받아오므로 복잡한 로컬 분석 로직 제거
    """
    
    def __init__(self, logger=None):
        """초기화"""
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # 설정 매니저를 통해 마틴 금액 불러오기
        from utils.settings_manager import SettingsManager
        settings_manager = SettingsManager()
        
        # 설정 파일에서 마틴 금액 불러오기
        _, self.martin_amounts = settings_manager.get_martin_settings()
        
        # 만약 설정 파일에서 불러오지 못하면 기본값 사용
        if not self.martin_amounts:
            self.martin_amounts = [1000, 2000, 4000, 8000, 16000, 32000]
        
        self.logger.info(f"초이스 픽 시스템 초기화 - 마틴 금액: {self.martin_amounts}")

        # 기본 상태 변수들만 유지
        self.results: List[str] = []  # 최근 결과
        self.current_pick: Optional[str] = None  # 현재 픽
        self.consecutive_failures: int = 0  # 연속 실패 횟수
        self.pick_results: List[bool] = []  # 픽 결과 기록
        
        # 방 이동 관련
        self.consecutive_n_count: int = 0  # 연속 N 발생 카운트
        self.failure_count: int = 0  # 실패 카운트
        
        # 상태 플래그들
        self.skip_n_count = False  # N 카운트 건너뛰기
        self.wait_first_result = False  # 첫 결과 대기
        
        # 라운드 정보
        self._entered_round = 0
        self._current_game_round = 0

        if self.logger:
            self.logger.info("단순화된 ChoicePickSystem 인스턴스 생성")

    def set_martin_amounts(self, amounts):
        """마틴 금액 설정"""
        self.martin_amounts = amounts
        if self.logger:
            self.logger.info(f"마틴 금액 업데이트: {amounts}")

    def add_result(self, result: str) -> None:
        """결과 추가"""
        if result not in ['P', 'B']:
            return
        
        self.results.append(result)
        # 최대 20개까지만 유지
        if len(self.results) > 20:
            self.results = self.results[-20:]
        
        if self.logger:
            self.logger.debug(f"결과 추가: {result}, 총 {len(self.results)}개")

    def add_multiple_results(self, results: List[str]) -> None:
        """다수 결과 추가"""
        filtered_results = [r for r in results if r in ['P', 'B']]
        self.results.extend(filtered_results)
        
        # 최대 20개까지만 유지
        if len(self.results) > 20:
            self.results = self.results[-20:]

    def has_sufficient_data(self) -> bool:
        """충분한 데이터가 있는지 확인"""
        return len(self.results) >= 15

    def generate_choice_pick(self) -> str:
        """
        초이스 픽 생성 - 서버 기반으로 단순화
        실제 복잡한 로직은 서버에서 처리하고, 여기서는 기본적인 픽만 생성
        """
        # 방 입장 직후 대기 상태
        if self.wait_first_result:
            self.logger.info("[초이스픽] wait_first_result=True → PICK 생략: N 반환")
            self.current_pick = "N"
            return "N"

        # 데이터 부족
        if not self.has_sufficient_data():
            if not getattr(self, 'skip_n_count', False):
                self.consecutive_n_count += 1
            self.logger.warning(f"데이터 부족으로 N 반환 (현재 {len(self.results)}/15개)")
            return 'N'

        # 간단한 패턴 기반 픽 생성 (서버가 주 로직을 담당하므로 단순화)
        try:
            recent_5 = self.results[-5:] if len(self.results) >= 5 else self.results
            p_count = recent_5.count('P')
            b_count = recent_5.count('B')
            
            # 단순한 반대 패턴 로직
            if p_count > b_count:
                pick = 'B'  # P가 많으면 B 선택
            elif b_count > p_count:
                pick = 'P'  # B가 많으면 P 선택
            else:
                # 동점이면 마지막 결과의 반대
                pick = 'B' if self.results[-1] == 'P' else 'P'
            
            self.current_pick = pick
            self.consecutive_n_count = 0  # 성공적으로 픽 생성
            
            if self.logger:
                self.logger.info(f"픽 생성 완료: {pick} (최근5개: {recent_5})")
            
            return pick

        except Exception as e:
            self.logger.error(f"픽 생성 중 오류: {e}")
            self.consecutive_n_count += 1
            return 'N'

    def record_betting_result(self, is_win: bool, reset_after_win: bool = True) -> None:
        """베팅 결과 기록"""
        self.pick_results.append(is_win)
        
        if is_win:
            self.consecutive_failures = 0
            self.failure_count = 0
            if self.logger:
                self.logger.info("베팅 성공 - 실패 카운트 초기화")
        else:
            self.consecutive_failures += 1
            self.failure_count += 1
            if self.logger:
                self.logger.info(f"베팅 실패 - 연속 실패: {self.consecutive_failures}회")

    def get_current_bet_amount(self, widget_position=None) -> int:
        """현재 베팅 금액 반환"""
        # 최신 설정 로드
        from utils.settings_manager import SettingsManager
        settings_manager = SettingsManager()
        _, latest_martin_amounts = settings_manager.get_martin_settings()
        
        # 최신 마틴 금액으로 업데이트
        self.martin_amounts = latest_martin_amounts

        # widget_position이 제공되지 않으면 기본값 0 사용
        if widget_position is None:
            widget_position = 0
        
        # 마틴 단계 수 확인
        martin_stages = len(self.martin_amounts)
        
        # 마틴 단계 계산 (모듈러 방식)
        effective_step = widget_position % martin_stages
        
        # 계산된 단계에 해당하는 금액 반환
        bet_amount = self.martin_amounts[effective_step]
        
        if self.logger:
            self.logger.debug(f"현재 베팅 금액: {bet_amount:,}원 (위젯: {widget_position+1}번, 마틴: {effective_step+1}단계)")
        
        return bet_amount

    def should_change_room(self) -> bool:
        """방 이동 필요 여부 확인 - 단순화"""
        # 연속 N 발생 (서버에서 방을 찾지 못하는 경우)
        if self.consecutive_n_count >= 8:
            if self.logger:
                self.logger.warning(f"방 이동 필요: 연속 N 발생 {self.consecutive_n_count}회")
            return True

        # 3연패 확인
        if len(self.pick_results) >= 3:
            recent_three = self.pick_results[-3:]
            if all(not result for result in recent_three):
                if self.logger:
                    self.logger.info("방 이동 필요: 3연패 감지")
                return True

        return False

    def reset_after_room_change(self, preserve_martin: bool = False) -> None:
        """방 이동 후 상태 초기화"""
        if not preserve_martin:
            self.consecutive_failures = 0
            self.pick_results = []
            self.failure_count = 0
            if self.logger:
                self.logger.info("방 이동: 마틴 상태 초기화")
        else:
            # 최근 3개 정도만 유지
            self.pick_results = self.pick_results[-3:]
            if self.logger:
                self.logger.info("방 이동: 마틴 상태 유지")

        # 공통 초기화
        self.consecutive_n_count = 0
        self.current_pick = None
        self.skip_n_count = True  # 방 입장 후 첫 N은 카운트하지 않음
        self.wait_first_result = True  # 첫 결과 대기 모드
        
        if self.logger:
            self.logger.info(f"방 이동 후 초기화 완료 (마틴 유지: {preserve_martin})")

    def clear(self) -> None:
        """전체 데이터 초기화"""
        self.results = []
        self.current_pick = None
        self.consecutive_failures = 0
        self.pick_results = []
        self.consecutive_n_count = 0
        self.failure_count = 0
        
        if self.logger:
            self.logger.info("ChoicePickSystem 전체 초기화 완료")

    def get_reverse_bet_pick(self, original_pick):
        """베팅 방향 적용 - 단순화"""
        # 서버 기반에서는 복잡한 역배팅 로직 제거하고 정배팅만 사용
        if self.logger:
            self.logger.info(f"정배팅 적용: {original_pick}")
        return original_pick