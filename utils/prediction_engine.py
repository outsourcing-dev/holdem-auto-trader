# utils/prediction_engine.py
import logging
from typing import List, Optional
from utils.choice_pick import ChoicePickSystem

class PredictionEngine:
    """
    게임 결과 예측 엔진
    - 기존 10판 기준 방식을 제거하고 15판 기준 초이스 픽 방식으로 통합
    """
    
    def __init__(self, logger=None):
        """예측 엔진 초기화"""
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        


        # 초이스 픽 시스템 초기화
        self.choice_pick_system = ChoicePickSystem(logger)
                
    def add_multiple_results(self, results):
        """
        여러 게임 결과 한번에 추가 - 초기화 시에만 호출됨
        
        Args:
            results (list): 게임 결과 리스트
        """
        # should_refresh_data 플래그 활성화 후 결과 추가
        # 이 메서드는 초기화용이므로 항상 데이터를 새로 설정해야 함
        if hasattr(self.choice_pick_system, 'should_refresh_data'):
            self.choice_pick_system.should_refresh_data = True
            
        # 초이스 픽 시스템에 결과 추가 (내부에서 P/B만 필터링)
        self.choice_pick_system.add_multiple_results(results)
        
    def predict_next_pick(self) -> str:
        """다음 픽 예측 (15~17판까지 지원)"""

        # 이전 승리 여부에 따라 캐시 초기화 결정
        if hasattr(self.choice_pick_system, 'recent_results') and self.choice_pick_system.recent_results:
            if self.choice_pick_system.recent_results[-1] == True:
                self.logger.info("최근 승리 감지: 픽 캐시 초기화")
                self.choice_pick_system.cached_pick = None
                self.choice_pick_system.last_results = []
                self.choice_pick_system.current_pick = None
                # N 카운트도 초기화
                self.choice_pick_system.consecutive_n_count = 0
                self.logger.info("[N 카운트 초기화] 승리로 인한 초기화")

        # 로그 추가: 현재 데이터 상태
        if hasattr(self.choice_pick_system, 'results'):
            self.logger.info(f"현재 choice_pick_system에 저장된 데이터: {self.choice_pick_system.results}, 길이: {len(self.choice_pick_system.results)}")
        
        # 데이터 충분한지 확인 (최소 15개 필요)
        if not self.choice_pick_system.has_sufficient_data():
            self.logger.warning(f"데이터 부족: {len(self.choice_pick_system.results)}/15판, 픽 생성 불가")
            self.choice_pick_system.consecutive_n_count += 1
            self.logger.warning(f"[N 카운트 증가] 데이터 부족으로 N 처리, 현재: {self.choice_pick_system.consecutive_n_count}")
            return 'N'

        # PICK 생성
        pick = self.choice_pick_system.generate_choice_pick()

        if pick and pick in ['P', 'B']:
            self.current_pick = pick
            self.cached_pick = pick
            self.last_results = self.choice_pick_system.results.copy()
            # N 카운트 초기화 (ChoicePickSystem의 값 사용)
            self.choice_pick_system.consecutive_n_count = 0
            self.logger.info("[N 카운트 초기화] 유효한 픽(P/B) 생성으로 초기화")

            direction = self.choice_pick_system.betting_direction
            self.logger.info(f"초이스 픽 생성 완료: {pick} ({direction} 배팅)")
        else:
            pick = 'N'

        return pick

    def should_change_room(self) -> bool:
        """
        방 이동 필요 여부 확인 - 이 메서드를 통해 ChoicePickSystem의 판단을 전달
        
        Returns:
            bool: 방 이동 필요 여부
        """

        return self.choice_pick_system.should_change_room()
    
    def record_betting_result(self, is_win: bool) -> None:
        """
        베팅 결과 기록
        
        Args:
            is_win (bool): 베팅 성공 여부
        """
        
        
        # 초이스 픽 시스템에 결과 기록
        self.choice_pick_system.record_betting_result(is_win)
    
    def get_current_bet_amount(self) -> int:
        """
        현재 마틴 단계에 따른 베팅 금액 반환
        
        Returns:
            int: 베팅 금액
        """
        return self.choice_pick_system.get_current_bet_amount()
    
    def set_martin_amounts(self, amounts: List[int]) -> None:
        """
        마틴 금액 설정
        
        Args:
            amounts (List[int]): 마틴 단계별 금액 목록
        """
        self.choice_pick_system.set_martin_amounts(amounts)
    
    def reset_after_room_change(self, preserve_martin: bool = False) -> None:
        # 초이스 픽 시스템 속성 초기화
        if hasattr(self.choice_pick_system, 'should_refresh_data'):
            self.choice_pick_system.should_refresh_data = True
            self.choice_pick_system.failure_count = 0
            self.choice_pick_system.cached_pick = None
            self.choice_pick_system.last_results = []
            self.choice_pick_system.current_pick = None
                
        # 초이스 픽 시스템의 reset_after_room_change 호출
        self.choice_pick_system.reset_after_room_change(preserve_martin=preserve_martin)
    
    def clear(self) -> None:
        """모든 데이터 초기화"""
        self.choice_pick_system.clear()