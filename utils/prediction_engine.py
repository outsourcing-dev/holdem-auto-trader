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
        if len(self.recent_results) > 15:
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
        if len(self.recent_results) < 15:
            self.logger.warning(f"결과가 15개 미만으로 예측 불가: {len(self.recent_results)}개")
            return 'N'

        # 초이스 픽이 이미 선택되어 있으면 고정 사용
        if hasattr(self, 'choice_pick') and self.choice_pick:
            self.logger.info(f"[초이스 픽 고정 사용] → {self.choice_pick}")
            return self.choice_pick

        candidates = []

        for offset in range(len(self.recent_results) - 14):  # 유효한 시퀀스만
            sequence = self.recent_results[offset:offset + 15]
            if len(sequence) < 15:
                continue  # 데이터 부족시 스킵

            stage1 = []
            try:
                for i in range(4, 15):
                    a, b, ref = sequence[i - 4], sequence[i - 3], sequence[i - 1]
                    pick = ref if a == b else ('B' if ref == 'P' else 'P')
                    stage1.append(pick)

                # 2단계
                stage2 = []
                for i in range(4, len(stage1)):
                    window = stage1[i - 4:i]
                    actual = sequence[4 + i]
                    win = sum(1 for x, y in zip(window, sequence[i:i + 4]) if x == y)
                    if win >= 2:
                        stage2.append(stage1[i])
                    else:
                        flipped = 'B' if stage1[i] == 'P' else 'P'
                        stage2.append(flipped)

                def stepwise(prev_stage, actuals):
                    result = prev_stage[:]
                    for i in range(len(prev_stage)):
                        if i < 4:
                            continue
                        prev_pick = result[i - 1]
                        prev_actual = actuals[i - 1]
                        if prev_pick != prev_actual:
                            flipped = 'B' if prev_pick == 'P' else 'P'
                            if i < len(actuals) and flipped == actuals[i]:
                                result[i] = flipped
                    return result

                stage3 = stepwise(stage2, sequence[9:])
                stage4 = stepwise(stage3, sequence[9:])
                stage5 = stage3[:7] + stage4[7:]

                final_pick = stage5[-1]

                last3 = stage5[-3:]
                actual3 = sequence[-3:]

                wins = sum(1 for x, y in zip(last3, actual3) if x == y)
                losses = 3 - wins

                if losses < 2 and last3[-1] != actual3[-1]:
                    candidates.append(('정배', final_pick, wins - losses))
                elif wins < 2 and last3[-1] == actual3[-1]:
                    flipped = 'B' if final_pick == 'P' else 'P'
                    candidates.append(('역배', flipped, losses - wins))

            except IndexError as e:
                self.logger.warning(f"[예측 스킵] 시퀀스 처리 중 오류: {e}")
                continue

        if not candidates:
            self.logger.info("[초이스 실패] 조건 만족 픽 없음")
            return 'N'

        candidates.sort(key=lambda x: x[2], reverse=True)
        top_score = candidates[0][2]
        top_picks = [c for c in candidates if c[2] == top_score]

        if len(top_picks) > 1:
            self.logger.info("[초이스 실패] 승패차 동점 → PASS")
            return 'N'

        selected = top_picks[0][1]
        self.choice_pick = selected
        self.logger.info(f"[초이스 픽 선택] {top_picks[0][0]} → {selected}")
        return selected


    def clear(self):
        """결과 초기화"""
        self.recent_results = []
        self.choice_pick = None
