# utils/prediction_engine.py
import logging

class PredictionEngine:
    """
    10개의 이전 결과를 기반으로 다음 픽을 예측하는 엔진
    엑셀을 사용하지 않고 코드 내에서 직접 계산
    """
    
    def __init__(self, logger=None):
        """예측 엔진 초기화"""
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.recent_results = []  # 최근 결과 (P, B만 포함)
        
    def add_result(self, result):
        """
        새로운 결과 추가 (최대 10개 유지)
        
        Args:
            result (str): 게임 결과 ('P', 'B', 'T' 중 하나)
        """
        # T는 무시
        if result not in ['P', 'B']:
            return
            
        # 결과 추가 및 최대 10개 유지
        self.recent_results.append(result)
        if len(self.recent_results) > 10:
            self.recent_results.pop(0)
            
    def add_multiple_results(self, results):
        """
        여러 게임 결과 한번에 추가
        
        Args:
            results (list): 게임 결과 리스트
        """
        for result in results:
            self.add_result(result)
    
    def predict_next_pick(self):
        """
        다음 픽 예측 (클라이언트 룰 기반)
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


    def clear(self):
        """결과 초기화"""
        self.recent_results = []