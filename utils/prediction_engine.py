# 📁 utils/prediction_engine.py
import logging

class PredictionEngine:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.recent_results = []  # 최근 15개 결과 (P, B)
        self.choice_pick = None
        self.pick_type = None

    def add_result(self, result):
        if result in ['P', 'B']:
            self.recent_results.append(result)
            if len(self.recent_results) > 15:
                self.recent_results.pop(0)

    def add_multiple_results(self, results):
        for result in results:
            self.add_result(result)

    def has_streak(self, result_list, target, count):
        streak = 0
        for r in reversed(result_list):
            if r == target:
                streak += 1
                if streak >= count:
                    return True
            else:
                streak = 0
        return False

    def predict_next_pick(self):
        # 고정된 초이스가 있다면 유지
        if self.choice_pick:
            self.logger.info(f"[고정 초이스 픽 사용] → {self.choice_pick} (type: {self.pick_type})")
            return self.choice_pick

        if len(self.recent_results) < 15:
            self.logger.warning("최근 결과가 15개 미만 → 픽 분석 불가")
            return 'N'

        candidates = []

        # 후보 6개 생성 (길이 10~5)
        for i in range(6):
            window = self.recent_results[i:i+10-i]  # 슬라이딩 윈도우: 10 → 5
            if len(window) < 5:
                continue

            for pick in ['P', 'B']:
                last_result = window[-1]
                win_loss_seq = [1 if r == pick else 0 for r in window]  # 1: 승, 0: 패

                # 연승/연패 조건 체크
                max_streak = 0
                curr_streak = 1
                for j in range(1, len(win_loss_seq)):
                    if win_loss_seq[j] == win_loss_seq[j-1]:
                        curr_streak += 1
                    else:
                        curr_streak = 1
                    max_streak = max(max_streak, curr_streak)

                is_forward = False
                is_reverse = False

                if max_streak <= 2:
                    if win_loss_seq[-1] == 0:
                        is_forward = True  # 정배 조건: 연패 없음 + 마지막 패
                    elif win_loss_seq[-1] == 1:
                        is_reverse = True  # 역배 조건: 연승 없음 + 마지막 승

                if is_forward:
                    score = sum(win_loss_seq) - (len(window) - sum(win_loss_seq))
                    candidates.append(('정배', pick, score))
                elif is_reverse:
                    score = (len(window) - sum(win_loss_seq)) - sum(win_loss_seq)
                    flipped = 'B' if pick == 'P' else 'P'
                    candidates.append(('역배', flipped, score))

        if not candidates:
            self.logger.info("[초이스 실패] 조건 만족 후보 없음")
            return 'N'

        # 점수 높은 후보만 선택
        candidates.sort(key=lambda x: x[2], reverse=True)
        top_score = candidates[0][2]
        top_picks = [c for c in candidates if c[2] == top_score]

        if len(top_picks) > 1:
            self.logger.info("[초이스 PASS] 후보 점수 동률")
            return 'N'

        self.pick_type, self.choice_pick, _ = top_picks[0]
        self.logger.info(f"[초이스 픽 선택] {self.pick_type} → {self.choice_pick}")

        # === 정배/역배 기반 필터링 ===
        if self.pick_type == '정배':
            opponent = 'B' if self.choice_pick == 'P' else 'P'
            if self.has_streak(self.recent_results, opponent, 3):
                self.logger.info("[정배 필터링] 최근 3연패 이상 → PASS")
                return 'N'

        elif self.pick_type == '역배':
            if self.has_streak(self.recent_results, self.choice_pick, 3):
                self.logger.info("[역배 필터링] 최근 3연승 이상 → PASS")
                return 'N'

        return self.choice_pick

    def clear(self):
        self.recent_results = []
        self.choice_pick = None
        self.pick_type = None
