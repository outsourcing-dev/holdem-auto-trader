# 📁 utils/prediction_engine.py
import logging

class PredictionEngine:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.recent_results = []  # 최근 15개 결과 (P, B)
        self.choice_pick = None   # 고정된 초이스 픽
        self.pick_type = None     # 현재 픽 타입 (정배/역배)
        self.consecutive_n_count = 0  # 연속 N 결과 카운트
        self.last_candidates = []  # 마지막 후보 목록 저장
        self.entry_pick_done = False  # 방 입장 후 첫 예측 완료 여부
        
    def add_result(self, result):
        """단일 결과 추가"""
        if result in ['P', 'B']:
            self.recent_results.append(result)
            if len(self.recent_results) > 15:
                self.recent_results.pop(0)
            # 결과가 추가되면 매번 초이스 픽 초기화 (선택적)
            # self.choice_pick = None

    def add_multiple_results(self, results):
        """여러 결과 한 번에 추가"""
        for result in results:
            self.add_result(result)
        # 처음 방 입장 시 여러 결과를 한 번에 추가하는 경우를 표시
        self.entry_pick_done = False

    def has_streak(self, result_list, target, count):
        """특정 패턴의 연속 여부 확인"""
        streak = 0
        for r in reversed(result_list):
            if r == target:
                streak += 1
                if streak >= count:
                    return True
            else:
                streak = 0
        return False

    def get_win_rate(self, result_list, pick):
        """특정 픽에 대한 승률 계산"""
        if not result_list:
            return 0.5
        
        matches = sum(1 for r in result_list if r == pick)
        return matches / len(result_list)
        
    def calculate_win_loss_gap(self, result_list, pick):
        """승패 차이 계산 (양수: 승리 많음, 음수: 패배 많음)"""
        if not result_list:
            return 0
            
        win_count = sum(1 for r in result_list if r == pick)
        lose_count = len(result_list) - win_count
        return win_count - lose_count

    def predict_next_pick(self):
        """다음 베팅 픽 예측"""
        # 1. 고정된 초이스가 있다면 유지
        if self.choice_pick:
            self.logger.info(f"[고정 초이스 픽 사용] → {self.choice_pick} (type: {self.pick_type})")
            self.consecutive_n_count = 0  # 고정 초이스가 있으면 연속 N 카운트 초기화
            return self.choice_pick

        # 2. 데이터가 부족한 경우 처리
        if len(self.recent_results) < 15:
            self.logger.warning(f"최근 결과가 15개 미만({len(self.recent_results)}개) → 픽 분석 불가")
            self.consecutive_n_count += 1
            return 'N'

        # 3. 후보 생성
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
                    # 추가 값: 최근 5개 데이터 내 해당 픽의 승률 (0.1~0.9)
                    recent_win_rate = self.get_win_rate(window[-5:], pick)
                    # 추가 값: 5개 데이터 내 승패 차이
                    win_loss_gap = self.calculate_win_loss_gap(window[-5:], pick)
                    candidates.append(('정배', pick, score, recent_win_rate, win_loss_gap))
                    
                elif is_reverse:
                    score = (len(window) - sum(win_loss_seq)) - sum(win_loss_seq)
                    flipped = 'B' if pick == 'P' else 'P'
                    # 추가 값: 최근 5개 데이터 내 반대 픽의 승률 (0.1~0.9)
                    recent_win_rate = self.get_win_rate(window[-5:], flipped)
                    # 추가 값: 5개 데이터 내 승패 차이
                    win_loss_gap = self.calculate_win_loss_gap(window[-5:], flipped)
                    candidates.append(('역배', flipped, score, recent_win_rate, win_loss_gap))

        # 4. 후보 없는 경우 처리
        if not candidates:
            self.logger.info("[초이스 실패] 조건 만족 후보 없음")
            self.consecutive_n_count += 1
            self.last_candidates = []  # 후보 목록 비우기
            
            # 방 입장 후 첫 예측에서 후보가 없는 경우, 방 이동 방지를 위해 초기화
            if not self.entry_pick_done:
                self.consecutive_n_count = 0
                self.entry_pick_done = True
                self.logger.info("[방 입장 첫 예측] 후보 없음 → 연속 카운트 초기화 (방 이동 방지)")
            
            return 'N'

        # 5. 점수 높은 후보 선택
        candidates.sort(key=lambda x: x[2], reverse=True)  # 기본 점수 기준 정렬
        top_score = candidates[0][2]
        top_picks = [c for c in candidates if c[2] == top_score]
        
        # 상세 로그 출력 (후보 목록과 점수)
        candidate_log = [f"({c[0]}, {c[1]}, 점수:{c[2]}, 승률:{c[3]:.2f}, 승패차:{c[4]})" for c in candidates]
        self.logger.info(f"후보 목록: {candidate_log}")
        
        # 마지막 후보 목록 저장
        self.last_candidates = candidates
        
        # 6. 동점 처리 개선: 추가 기준으로 재정렬
        if len(top_picks) > 1:
            self.logger.info(f"[동점 후보 발견] {len(top_picks)}개 후보 중 최적 후보 선택")
            
            # 6.1 최근 승률로 동점 해소 시도
            top_picks.sort(key=lambda x: x[3], reverse=True)  # 최근 승률 높은 순
            best_win_rate = top_picks[0][3]
            win_rate_picks = [p for p in top_picks if abs(p[3] - best_win_rate) < 0.01]  # 1% 내 차이는 같은 것으로 간주
            
            if len(win_rate_picks) == 1:
                self.logger.info(f"[동점 해소] 승률 기준 → {win_rate_picks[0][1]} 선택")
                self.pick_type, self.choice_pick, _, _, _ = win_rate_picks[0]
                self.consecutive_n_count = 0
                self.entry_pick_done = True
                return self.choice_pick
                
            # 6.2 승패 차이로 동점 해소 시도
            if len(win_rate_picks) > 1:
                win_rate_picks.sort(key=lambda x: x[4], reverse=True)  # 승패 차이 큰 순
                
                if win_rate_picks[0][4] != win_rate_picks[1][4]:  # 1등과 2등의 승패 차이가 다르면
                    self.logger.info(f"[동점 해소] 승패 차이 기준 → {win_rate_picks[0][1]} 선택")
                    self.pick_type, self.choice_pick, _, _, _ = win_rate_picks[0]
                    self.consecutive_n_count = 0
                    self.entry_pick_done = True
                    return self.choice_pick
            
            # 6.3 여전히 동점이면 최근 결과와 다른 것 선택
            if len(win_rate_picks) > 1 and self.recent_results:
                last_result = self.recent_results[-1]
                for pick in win_rate_picks:
                    if pick[1] != last_result:  # 마지막 결과와 다른 픽 선택
                        self.logger.info(f"[동점 해소] 마지막 결과({last_result})와 다른 픽 → {pick[1]} 선택")
                        self.pick_type, self.choice_pick, _, _, _ = pick
                        self.consecutive_n_count = 0
                        self.entry_pick_done = True
                        return self.choice_pick
                
            # 6.4 최후 해결책: 첫번째 것 선택
            self.logger.info(f"[동점 해소] 모든 기준 동일 → 첫번째 후보 {win_rate_picks[0][1]} 선택")
            self.pick_type, self.choice_pick, _, _, _ = win_rate_picks[0]
            self.consecutive_n_count = 0
            self.entry_pick_done = True
            return self.choice_pick
            
        # 7. 단일 후보 처리 (기존 로직)
        self.pick_type, self.choice_pick, _, _, _ = top_picks[0]
        self.logger.info(f"[초이스 픽 선택] {self.pick_type} → {self.choice_pick}")
        self.consecutive_n_count = 0
        self.entry_pick_done = True

        # 8. 정배/역배 필터링 (기존 로직)
        if self.pick_type == '정배':
            opponent = 'B' if self.choice_pick == 'P' else 'P'
            if self.has_streak(self.recent_results, opponent, 3):
                self.logger.info("[정배 필터링] 최근 3연패 이상 → PASS")
                self.choice_pick = None  # 초이스를 무효화
                self.consecutive_n_count += 1
                return 'N'

        elif self.pick_type == '역배':
            if self.has_streak(self.recent_results, self.choice_pick, 3):
                self.logger.info("[역배 필터링] 최근 3연승 이상 → PASS")
                self.choice_pick = None  # 초이스를 무효화
                self.consecutive_n_count += 1
                return 'N'

        return self.choice_pick

    def reset_consecutive_n_count(self):
        """연속 N 카운트 초기화"""
        old_count = self.consecutive_n_count
        self.consecutive_n_count = 0
        self.logger.info(f"연속 N 카운트 초기화: {old_count} → 0")

    def clear(self):
        """모든 상태 초기화"""
        self.recent_results = []
        self.choice_pick = None
        self.pick_type = None
        self.consecutive_n_count = 0
        self.last_candidates = []
        self.entry_pick_done = False
        self.logger.info("예측 엔진 완전 초기화 완료")