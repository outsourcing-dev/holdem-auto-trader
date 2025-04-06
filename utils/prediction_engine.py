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
    
    def add_result(self, result):
        """
        새로운 결과 추가
        
        Args:
            result (str): 게임 결과 ('P', 'B', 'T' 중 하나)
        """
        # T는 무시, 초이스 픽 시스템에 추가
        if result in ['P', 'B']:
            self.choice_pick_system.add_result(result)
                
    def add_multiple_results(self, results):
        """
        여러 게임 결과 한번에 추가
        
        Args:
            results (list): 게임 결과 리스트
        """
        # 초이스 픽 시스템에 결과 추가 (내부에서 P/B만 필터링)
        self.choice_pick_system.add_multiple_results(results)
    
    def predict_next_pick(self) -> str:
        """
        다음 픽 예측 (15판 기준 초이스 픽 시스템 사용)
        
        Returns:
            str: 다음 픽 ('P', 'B' 또는 'N')
        """
        # 초이스 픽 시스템에서 픽 생성
        pick = self.choice_pick_system.generate_choice_pick()
        
        if pick:
            direction = self.choice_pick_system.betting_direction
            self.logger.info(f"초이스 픽 생성 완료: {pick} ({direction} 배팅)")
            return pick
        else:
            self.logger.warning("초이스 픽 생성 실패 - 데이터 부족 또는 적합한 후보 없음")
            return 'N'  # 예측 불가능 시 'N' 반환
    
    def record_betting_result(self, is_win: bool) -> None:
        """
        베팅 결과 기록
        
        Args:
            is_win (bool): 베팅 성공 여부
        """
        # 초이스 픽 시스템에 결과 기록
        self.choice_pick_system.record_betting_result(is_win)
    
    def should_change_room(self) -> bool:
        """
        방 이동 필요 여부 확인
        
        Returns:
            bool: 방 이동 필요 여부
        """
        return self.choice_pick_system.should_change_room()
    
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
    
    def reset_after_room_change(self) -> None:
        """방 이동 후 초기화"""
        self.choice_pick_system.reset_after_room_change()
    
    def clear(self) -> None:
        """모든 데이터 초기화"""
        self.choice_pick_system.clear()