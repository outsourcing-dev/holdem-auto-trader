# utils/prediction_engine.py
import logging
from typing import List, Optional
from utils.choice_pick import ChoicePickSystem

class PredictionEngine:
    """
    게임 결과 예측 엔진
    - 기존 규칙 기반 방식과 새로운 초이스 픽 방식 모두 지원
    """
    
    def __init__(self, logger=None):
        """예측 엔진 초기화"""
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.recent_results = []  # 최근 결과 (P, B만 포함)
        
        # 초이스 픽 시스템 초기화
        self.choice_pick_system = ChoicePickSystem(logger)
        
        # 예측 모드 설정 (default: choice)
        self.prediction_mode = "choice"  # 'classic' 또는 'choice'
        
    def add_result(self, result):
        """
        새로운 결과 추가 (최대 15개 유지)
        
        Args:
            result (str): 게임 결과 ('P', 'B', 'T' 중 하나)
        """
        # T는 무시
        if result not in ['P', 'B']:
            return
            
        # 예전 시스템용 결과 추가
        self.recent_results.append(result)
        if len(self.recent_results) > 10:
            self.recent_results.pop(0)
            
        # 초이스 픽 시스템에도 결과 추가
        self.choice_pick_system.add_result(result)
        
    def add_multiple_results(self, results):
        """
        여러 게임 결과 한번에 추가
        
        Args:
            results (list): 게임 결과 리스트
        """
        for result in results:
            if result in ['P', 'B']:
                self.add_result(result)
                
        # 초이스 픽 시스템에는 직접 추가 (필터링 기능 내장)
        self.choice_pick_system.add_multiple_results(results)
    
    def predict_next_pick(self) -> str:
        """
        다음 픽 예측 (현재 선택된 모드 사용)
        
        Returns:
            str: 다음 픽 ('P', 'B' 또는 'N')
        """
        if self.prediction_mode == "choice":
            return self._predict_with_choice_system()
        else:
            return self._predict_with_classic_system()
    
    def _predict_with_choice_system(self) -> str:
        """
        초이스 픽 시스템으로 예측
        
        Returns:
            str: 예측된 픽 ('P', 'B' 또는 'N')
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
            
    def _predict_with_classic_system(self) -> str:
        """
        기존 규칙 기반 시스템으로 예측 (기존 코드 유지)
        
        Returns:
            str: 예측된 픽 ('P', 'B' 또는 'N')
        """
        if len(self.recent_results) < 10:
            self.logger.warning(f"결과가 10개 미만으로 예측 불가: {len(self.recent_results)}개")
            return 'N'

        try:
            # 최근 10개 기준
            window = self.recent_results[-10:]
            self.logger.info(f"[예측] 최근 10개 결과: {window}")

            # 비교: 1-7, 2-8, 3-9
            comparisons = [
                (window[0], window[6]),
                (window[1], window[7]),
                (window[2], window[8])
            ]

            pattern = []
            for idx, (a, b) in enumerate(comparisons, start=1):
                result = 'O' if a == b else 'X'
                pattern.append(result)
                self.logger.info(f"[비교] {idx}-{idx+6}: {a} vs {b} → {result}")

            pattern_key = ''.join(pattern)
            self.logger.info(f"[패턴] 패턴 키: {pattern_key}")

            # 룰 정의
            pattern_rule = {
                "XXX": "O",
                "OOO": "X",
                "XOX": "O",
                "OXO": "X",
                "OOX": "X",
                "XXO": "O",
                "OXX": "O",
                "XOO": "X",
            }

            match_target = pattern_rule.get(pattern_key, "X")
            self.logger.info(f"[룰결정] 매치 타겟: {match_target} (기본값은 X)")

            reference_value = window[3]
            prediction = reference_value if match_target == 'O' else ('P' if reference_value == 'B' else 'B')
            self.logger.info(f"[결과] 참조값(4번): {reference_value} → 예측: {prediction}")

            return prediction

        except Exception as e:
            self.logger.error(f"PICK 예측 중 오류 발생: {e}")
            return 'N'
            
    def set_mode(self, mode: str) -> None:
        """
        예측 모드 변경
        
        Args:
            mode (str): 'classic' 또는 'choice'
        """
        if mode in ['classic', 'choice']:
            self.prediction_mode = mode
            self.logger.info(f"예측 모드 변경: {mode}")
        else:
            self.logger.warning(f"올바르지 않은 예측 모드: {mode} (classic 또는 choice만 가능)")
            self.prediction_mode = "choice"  # 기본값으로 설정
    
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
        if self.prediction_mode == "choice":
            return self.choice_pick_system.should_change_room()
        return False  # 기존 방식은 이 메소드로 방 이동 결정 안함
    
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
        self.recent_results = []
        self.choice_pick_system.clear()