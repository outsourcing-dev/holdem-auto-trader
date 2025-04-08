from turtle import pd
from typing import List, Dict, Optional, Tuple, Any


class ChoicePickSystem:
    """
    초이스 픽 시스템 - 15판 기준의 베팅 전략 구현
    """
    def __init__(self, logger=None):
        """초기화"""
        self.logger = logger
        self.results: List[str] = []  # 최근 15판 결과 (P/B만)
        self.current_pick: Optional[str] = None  # 현재 초이스 픽
        self.betting_direction: str = "normal"  # 'normal' 또는 'reverse'
        self.consecutive_failures: int = 0  # 연속 실패 횟수
        self.pick_scores: Dict[str, int] = {}  # 픽 후보들의 점수
        self.betting_attempts: int = 0  # 현재 픽으로 배팅 시도 횟수
        
        # 3마틴 배팅 관련 변수
        self.martin_step: int = 0  # 현재 마틴 단계 (0부터 시작)
        self.martin_amounts: List[int] = [1000, 2000, 4000]  # 기본 마틴 금액
        
        # 픽 생성 후 성공/실패 여부 추적
        self.pick_results: List[bool] = []  # True=성공, False=실패
        
        # 방 이동 카운터
        self.last_win_count: int = 0  # 마지막 승리 이후 판 수
        
        # 알고리즘용 각 단계별 픽 저장
        self.stage1_picks: List[str] = []  # 1단계 픽 리스트
        self.stage2_picks: List[str] = []  # 2단계 픽 리스트
        self.stage3_picks: List[str] = []  # 3단계 픽 리스트
        self.stage4_picks: List[str] = []  # 4단계 픽 리스트
        self.stage5_picks: List[str] = []  # 5단계 픽 리스트
        
        # 로그 메시지 (logger가 없을 경우 대비)
        if self.logger:
            self.logger.info("ChoicePickSystem 인스턴스 생성")

    def add_result(self, result: str) -> None:
        """
        새 결과 추가 (TIE는 무시)
        
        Args:
            result: 'P', 'B', 또는 'T' (Player, Banker, Tie)
        """
        if result not in ['P', 'B']:
            return
            
        self.results.append(result)
        if len(self.results) > 15:
            self.results.pop(0)
            
        if self.logger:
            self.logger.info(f"결과 추가: {result} (현재 {len(self.results)}/15판)")
            self.logger.debug(f"현재 결과 리스트: {self.results}")
        
        self.last_win_count += 1

    def add_multiple_results(self, results: List[str]) -> None:
        """
        여러 결과 한번에 추가 (TIE 제외)
        
        Args:
            results: 결과 목록 ['P', 'B', 'T', ...]
        """
        filtered_results = [r for r in results if r in ['P', 'B']]
        if len(filtered_results) > 15:
            filtered_results = filtered_results[-15:]
            
        self.results = filtered_results
        
        if self.logger:
            self.logger.info(f"다중 결과 추가: 총 {len(self.results)}/15판")
            self.logger.debug(f"현재 결과 리스트: {self.results}")

    def has_sufficient_data(self) -> bool:
        """15판 데이터가 모두 있는지 확인"""
        return len(self.results) >= 15

    def get_opposite_pick(self, pick: str) -> str:
        """반대 픽 반환"""
        return 'B' if pick == 'P' else 'P'
    
    def _initialize_stage_picks(self, max_pick: int) -> None:
        """
        각 단계별 픽 리스트 초기화
        
        Args:
            max_pick: 생성할 최대 픽 번호
        """
        # 인덱스는 0부터 시작하므로 최대 픽 번호만큼 공간 필요
        self.stage1_picks = ['' for _ in range(max_pick)]
        self.stage2_picks = ['' for _ in range(max_pick)]
        self.stage3_picks = ['' for _ in range(max_pick)]
        self.stage4_picks = ['' for _ in range(max_pick)]
        self.stage5_picks = ['' for _ in range(max_pick)]

    def _generate_all_stage_picks(self, start_from: int = 0) -> Dict[int, Dict[str, str]]:
        sliced_results = self.results[start_from:]
        if len(sliced_results) < 5:
            if self.logger:
                self.logger.warning(f"데이터 부족: {len(sliced_results)}개, 픽 생성 불가")
            return {}

        result_based_max_pick = len(sliced_results) + 1
        max_pick = min(18, result_based_max_pick)

        stage1_picks = ['' for _ in range(max_pick)]
        stage2_picks = ['' for _ in range(max_pick)]
        stage3_picks = ['' for _ in range(max_pick)]
        stage4_picks = ['' for _ in range(max_pick)]
        stage5_picks = ['' for _ in range(max_pick)]

        all_picks = {}

        def safe_get(lst, idx, default='N'):
            return lst[idx] if 0 <= idx < len(lst) else default

        for pick_number in range(5, max_pick + 1):
            pos = pick_number - 1
            global_pick_num = start_from + pick_number

            pick1 = safe_get(sliced_results, pos - 4)
            pick2 = safe_get(sliced_results, pos - 3)
            pick4 = safe_get(sliced_results, pos - 1)
            stage1 = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4) if pick1 != 'N' and pick2 != 'N' and pick4 != 'N' else 'N'
            stage1_picks[pos] = stage1

            # 2단계
            if pick_number < 6:
                stage2 = 'N'
            else:
                win_count = 0
                for i in range(1, 5):
                    prev = pick_number - i
                    prev_idx = prev - 1
                    if 0 <= prev_idx < len(stage1_picks):
                        prev_stage1 = stage1_picks[prev_idx]
                        prev_result = safe_get(sliced_results, prev_idx)
                        if prev_stage1 != 'N' and prev_result == prev_stage1:
                            win_count += 1
                stage2 = stage1 if win_count >= 2 else self.get_opposite_pick(stage1)
            stage2_picks[pos] = stage2

            # 3단계
            if pick_number < 6:
                stage3 = 'N'
            elif pick_number <= 8:
                stage3 = stage2
            else:
                prev_idx = pick_number - 2
                prev_result = safe_get(sliced_results, prev_idx)
                prev_stage2 = safe_get(stage2_picks, prev_idx)
                stage3 = stage2 if prev_stage2 != 'N' and prev_result == prev_stage2 else self.get_opposite_pick(stage2)
            stage3_picks[pos] = stage3

            # 4단계
            if pick_number == 5:
                stage4 = 'N'
            elif pick_number <= 10:
                stage4 = stage3
            else:
                prev_idx = pick_number - 2
                prev_result = safe_get(sliced_results, prev_idx)
                prev_stage3 = safe_get(stage3_picks, prev_idx)
                stage4 = stage3 if prev_stage3 != 'N' and prev_result == prev_stage3 else self.get_opposite_pick(stage3)
            stage4_picks[pos] = stage4

            # 5단계
            if pick_number == 5:
                stage5 = 'N'
            elif pick_number <= 11:
                stage5 = stage1
            else:
                win_count = 0
                for i in range(1, 5):
                    prev_idx = pick_number - i - 1
                    pred = safe_get(stage4_picks, prev_idx)
                    actual = safe_get(sliced_results, prev_idx)
                    if pred != 'N' and pred == actual:
                        win_count += 1
                stage5 = stage4 if win_count >= 2 else self.get_opposite_pick(stage4)
                if self.logger:
                    self.logger.info(f"[5단계 계산] pick={global_pick_num}, 이전 4판 승수={win_count}, stage4={stage4}, 결정={stage5}")
            stage5_picks[pos] = stage5

            final_pick = next((x for x in [stage5, stage4, stage3, stage2, stage1] if x != 'N'), 'N')
            all_picks[global_pick_num] = {
                "1단계": stage1,
                "2단계": stage2,
                "3단계": stage3,
                "4단계": stage4,
                "5단계": stage5,
                "최종픽": final_pick
            }

        return all_picks


    def _calculate_five_stage_picks(self, pick_number: int, results: List[str]) -> Tuple[str, str, str, str, str]:
        """
        5단계 픽 계산 함수 - 이전 단계 참조를 포함
        
        Args:
            pick_number: 현재 픽 번호
            results: 결과 리스트
            
        Returns:
            Tuple[str, str, str, str, str]: 5단계 픽 값
        """
        # 안전하게 리스트에서 값 가져오는 헬퍼 함수
        def safe_get(lst, idx, default='N'):
            return lst[idx] if 0 <= idx < len(lst) else default
        
        pos = pick_number - 1  # 0-기반 인덱스로 변환

        # ========= 1단계 =========
        # 1단계: pick1 == pick2 ? pick4 : !pick4
        pick1 = safe_get(results, pos - 4)
        pick2 = safe_get(results, pos - 3)
        pick4 = safe_get(results, pos - 1)
        
        if pick1 == 'N' or pick2 == 'N' or pick4 == 'N':
            stage1 = 'N'  # 필요한 데이터가 부족하면 'N' 반환
        else:
            stage1 = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4)

        # ========= 2단계 =========
        if pick_number < 6:
            stage2 = 'N'  # 픽 번호가 6 미만이면 계산 불가
        else:
            # 이전 4판의 결과와 1단계 픽 비교
            win_count = 0
            for i in range(1, 5):
                prev_num = pick_number - i
                if prev_num < 1:
                    continue
                    
                prev_idx = prev_num - 1
                if prev_idx < 0 or prev_idx >= len(self.stage1_picks):
                    continue
                    
                prev_stage1 = self.stage1_picks[prev_idx]
                prev_result = safe_get(results, prev_idx)
                
                if prev_stage1 != 'N' and prev_result != 'N' and prev_stage1 == prev_result:
                    win_count += 1
            
            stage2 = stage1 if win_count >= 2 else self.get_opposite_pick(stage1)
        
                # ✅ 디버그 로그 추가: pick_number가 12인 경우만 추적
            if self.logger and pick_number == 12:
                self.logger.info(
                    f"[2단계 계산] pick={pick_number}, stage1={stage1}, "
                    f"이전 4픽 승수={win_count}, 결정={stage2}"
                )
        # ========= 3단계 =========
        if pick_number < 6:
            stage3 = 'N'
        elif 6 <= pick_number <= 8:
            stage3 = stage2  # 6~8번 픽은 2단계와 동일
        else:
            # 이전 픽의 결과 확인
            prev_num = pick_number - 1
            prev_idx = prev_num - 1
            
            prev_stage2 = self.stage2_picks[prev_idx] if 0 <= prev_idx < len(self.stage2_picks) else 'N'
            prev_result = safe_get(results, prev_idx)
            
            if prev_stage2 != 'N' and prev_result != 'N':
                stage3 = stage2 if prev_result == prev_stage2 else self.get_opposite_pick(stage2)
            else:
                stage3 = stage2

        # ========= 4단계 =========
        if pick_number == 5:
            stage4 = 'N'
        elif 6 <= pick_number <= 10:
            stage4 = stage3  # 6~10번 픽은 3단계와 동일
        else:
            # 이전 픽의 결과 확인
            prev_num = pick_number - 1
            prev_idx = prev_num - 1
            
            prev_stage3 = self.stage3_picks[prev_idx] if 0 <= prev_idx < len(self.stage3_picks) else 'N'
            prev_result = safe_get(results, prev_idx)
            
            if prev_stage3 != 'N' and prev_result != 'N':
                stage4 = stage3 if prev_result == prev_stage3 else self.get_opposite_pick(stage3)
            else:
                stage4 = stage3

        # ========= 5단계 =========
        if pick_number == 5:
            stage5 = 'N'
        elif 6 <= pick_number <= 11:
            stage5 = stage1  # 6~11번 픽은 1단계와 동일
        else:
            # 이전 4판의 4단계 픽과 결과 비교해서 승률 계산
            win_count = 0
            for i in range(1, 5):
                prev_num = pick_number - i
                if prev_num < 5:
                    continue
                    
                prev_idx = prev_num - 1
                if prev_idx < 0 or prev_idx >= len(self.stage4_picks):
                    continue
                    
                prev_stage4 = self.stage4_picks[prev_idx]
                prev_result = safe_get(results, prev_idx)
                
                if prev_stage4 != 'N' and prev_result != 'N' and prev_stage4 == prev_result:
                    win_count += 1
            
            stage5 = stage4 if win_count >= 2 else self.get_opposite_pick(stage4)
            if self.logger:
                self.logger.info(
                    f"[5단계 계산] pick={pick_number}, 이전 4판 승수={win_count}, stage4={stage4}, 결정={stage5}"
                )
        
        return stage1, stage2, stage3, stage4, stage5

    def _apply_five_stage_algorithm(self, pick_number: int, results: List[str],
                                    stage1_ref: List[str], stage2_ref: List[str],
                                    stage3_ref: List[str], stage4_ref: List[str]) -> Tuple[str, str, str, str, str]:
        """
        5단계 알고리즘 적용 (더 이상 사용하지 않음 - _generate_all_stage_picks에서 대체)
        
        참고용으로 유지
        """
        pos = pick_number - 1

        def safe_get(lst, idx, default='N'):
            return lst[idx] if 0 <= idx < len(lst) else default

        # ========= 1° =========
        pick1 = safe_get(results, pos - 4)
        pick2 = safe_get(results, pos - 3)
        pick4 = safe_get(results, pos - 1)
        stage1 = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4)

        # ========= 2° =========
        if pick_number < 6:
            stage2 = 'N'
        else:
            recent_results = results[pick_number - 5:pick_number - 1]
            recent_picks = stage1_ref[pick_number - 5:pick_number - 1]
            wins = sum(1 for r, p in zip(recent_results, recent_picks) if r == p)
            stage2 = stage1 if wins >= 2 else self.get_opposite_pick(stage1)

        # ========= 3° =========
        if pick_number < 6:
            stage3 = 'N'
        elif 6 <= pick_number <= 8:
            stage3 = stage2
        else:
            prev_idx = pick_number - 2
            result_at_prev = safe_get(results, prev_idx)
            prev_stage2 = safe_get(stage2_ref, prev_idx)
            stage3 = stage2 if result_at_prev == prev_stage2 else self.get_opposite_pick(stage2)

        # ========= 4° =========
        if pick_number == 5:
            stage4 = 'N'
        elif 6 <= pick_number <= 10:
            stage4 = stage3
        else:
            prev_idx = pick_number - 2
            prev_pick = safe_get(stage3_ref, prev_idx)
            prev_result = safe_get(results, prev_idx)
            stage4 = stage3 if prev_pick == prev_result else self.get_opposite_pick(stage3)

        # ========= 5° =========
        if pick_number == 5:
            stage5 = 'N'
        elif 6 <= pick_number <= 11:
            stage5 = stage1
        else:
            win_count = 0
            for offset in range(4):
                idx = pick_number - 2 - offset
                pred = safe_get(stage4_ref, idx)
                actual = safe_get(results, idx)
                if pred == actual:
                    win_count += 1

            stage5 = stage4 if win_count >= 2 else self.get_opposite_pick(stage4)

        return stage1, stage2, stage3, stage4, stage5

    def _generate_six_picks(self) -> Dict[int, str]:
        """
        6개의 픽 생성 (시작 위치만 다른 동일한 알고리즘)
        
        Returns:
            Dict[int, str]: 각 시작 위치별 최종 픽 값 {1: 'P', 2: 'B', ...}
        """
        if self.logger:
            self.logger.info("6개 픽 생성 시작")
        
        if not self.has_sufficient_data():
            if self.logger:
                self.logger.warning(f"6개 픽 생성 실패: 데이터 부족 (현재 {len(self.results)}/15판)")
            return {}
        
        # 먼저 모든 단계별 픽 생성
        all_stage_picks = self._generate_all_stage_picks()
        
        # 결과가 15개인 경우 예측픽은 16번, 16개인 경우 17번, 17개인 경우 18번까지
        next_pick_number = len(self.results) + 1
        
        # 예측 픽 번호들: 항상 16번부터 시작하며, 최대 18번까지
        available_pick_numbers = list(range(16, min(next_pick_number + 1, 19)))
        
        if self.logger:
            self.logger.info(f"생성 가능한 예측픽: {available_pick_numbers}")
        
        # 6개 픽에 해당하는 최종 값 추출
        picks = {}
        for pos in range(1, 7):
            if pos <= len(available_pick_numbers):
                pick_number = available_pick_numbers[pos-1]
                
                if pick_number in all_stage_picks:
                    final_pick = all_stage_picks[pick_number]["최종픽"]
                    
                    # 'N'인 경우 유효한 픽이 아니므로 건너뜀
                    if final_pick == 'N':
                        if self.logger:
                            self.logger.warning(f"픽 {pos}번 (위치 {pick_number}번) 계산 결과가 'N'이므로 제외")
                        continue
                    
                    picks[pos] = final_pick
                    if self.logger:
                        self.logger.info(f"픽 {pos}번 생성 완료: {final_pick} (위치 {pick_number}번)")
            else:
                # 계산 가능한 예측픽 개수가 부족한 경우 (이전 픽들로 채움)
                if self.logger:
                    self.logger.warning(f"픽 {pos}번 생성 실패: 예측 가능 범위 초과")
        
        if self.logger:
            p_count = sum(1 for p in picks.values() if p == 'P')
            b_count = sum(1 for p in picks.values() if p == 'B')
            self.logger.info(f"6개 픽 생성 완료: P={p_count}개, B={b_count}개")
            self.logger.debug(f"6개 픽 전체: {picks}")
        
        return picks

    def _find_streaks(self, results: List[str], condition_func, min_length: int) -> List[tuple]:
        """
        특정 조건에 맞는 연속 구간 찾기
        
        Args:
            results: 결과 리스트
            condition_func: 각 결과에 적용할 조건 함수
            min_length: 최소 연속 길이
            
        Returns:
            List[tuple]: (시작인덱스, 종료인덱스, 길이) 형태의 연속 구간 목록
        """
        streaks = []
        current_streak = 0
        streak_start = -1
        
        for i, r in enumerate(results):
            if condition_func(r):  # 조건 만족
                if current_streak == 0:
                    streak_start = i
                current_streak += 1
                if current_streak >= min_length:
                    # 이미 최소 길이를 만족했음을 표시 (아래에서 중복 기록 방지)
                    if len(streaks) == 0 or streaks[-1][1] < i - min_length:
                        streaks.append((streak_start, i, current_streak))
            else:  # 조건 불만족
                if current_streak >= min_length:
                    # 방금 끝난 연속 구간 기록
                    streaks.append((streak_start, i - 1, current_streak))
                current_streak = 0
                streak_start = -1
        
        # 마지막 요소까지 연속될 경우
        if current_streak >= min_length:
            streaks.append((streak_start, len(results) - 1, current_streak))
        
        return streaks

    def _calculate_win_loss_diff(self, pick: str) -> int:
        """픽에 대한 승패 차이 계산"""
        wins = sum(1 for r in self.results if r == pick)
        losses = len(self.results) - wins
        diff = wins - losses
        if self.logger:
            self.logger.debug(f"승패 차이 계산: pick={pick}, wins={wins}, losses={losses}, diff={diff}")
        return diff

    def record_betting_result(self, is_win: bool, reset_after_win: bool = True) -> None:
        """
        베팅 결과 기록 및 처리
        
        Args:
            is_win: 베팅이 성공했는지 여부
            reset_after_win: 승리 시 카운터 리셋 여부
        """
        self.betting_attempts += 1
        self.pick_results.append(is_win)
        
        if is_win:
            if self.logger:
                self.logger.info(f"베팅 성공! 시도: {self.betting_attempts}번째, 마틴 단계: {self.martin_step+1}")
            if reset_after_win:
                self.consecutive_failures = 0
                self.martin_step = 0
                self.last_win_count = 0
                if self.logger:
                    self.logger.info("베팅 성공으로 마틴 단계와 실패 카운터 초기화")
        else:
            if self.logger:
                self.logger.info(f"베팅 실패. 시도: {self.betting_attempts}번째, 마틴 단계: {self.martin_step+1}")
            if self.martin_step < 2:
                self.martin_step += 1
                if self.logger:
                    self.logger.info(f"마틴 단계 증가: {self.martin_step+1}단계")
            else:
                self.consecutive_failures += 1
                self.martin_step = 0
                if self.logger:
                    self.logger.warning(f"3마틴 모두 실패! 연속 실패: {self.consecutive_failures}회")
    
    def get_current_bet_amount(self) -> int:
        """현재 마틴 단계에 따른 베팅 금액 반환"""
        if self.martin_step < len(self.martin_amounts):
            return self.martin_amounts[self.martin_step]
        return self.martin_amounts[-1]
        
    def should_change_room(self) -> bool:
        """
        방 이동이 필요한지 확인
        
        Returns:
            bool: 방 이동 필요 여부
        """
        if self.consecutive_failures >= 1 and self.martin_step == 0:
            if self.logger:
                self.logger.info("3마틴 모두 실패로 방 이동 필요")
            return True
            
        if len(self.pick_results) >= 2 and not any(self.pick_results[-2:]):
            if self.logger:
                self.logger.info("초이스 픽 2회 연속 실패로 방 이동 필요")
            return True
            
        if self.betting_attempts == 0 and self.martin_step == 0 and self.last_win_count >= 57:
            if self.logger:
                self.logger.info(f"현재 게임 판수가 57판 이상이고 배팅 중이 아님 → 방 이동 필요")
            return True
            
        return False
    
    def reset_after_room_change(self) -> None:
        """방 이동 후 초기화"""
        prev_failures = self.consecutive_failures
        prev_martin = self.martin_step
        prev_results = len(self.pick_results)
        self.betting_attempts = 0
        self.martin_step = 0
        self.current_pick = None
        if self.logger:
            self.logger.info(f"방 이동 후 초기화: 연속실패({prev_failures}→{self.consecutive_failures}), "
                          f"마틴({prev_martin+1}→{self.martin_step+1}), 결과개수({prev_results})")
    
    def clear(self) -> None:
        """전체 데이터 초기화"""
        self.results = []
        self.current_pick = None
        self.betting_direction = "normal"
        self.consecutive_failures = 0
        self.pick_scores = {}
        self.betting_attempts = 0
        self.martin_step = 0
        self.pick_results = []
        self.last_win_count = 0
        self.stage1_picks = []
        self.stage2_picks = []
        self.stage3_picks = []
        self.stage4_picks = []
        self.stage5_picks = []
    
    def generate_six_pick_candidates(self) -> Dict[int, List[str]]:
        """
        6개의 후보 픽 생성 (시작 위치별)
        
        Returns:
            Dict[int, List[str]]: 각 후보별 픽 리스트 {1: ['P', 'B', ...], 2: ['B', 'P', ...], ...}
        """
        if not self.has_sufficient_data():
            if self.logger:
                self.logger.warning(f"후보 픽 생성 실패: 데이터 부족 (현재 {len(self.results)}/15판)")
            return {}
        
        candidates = {}
        
        for i in range(6):  # 후보 1~6번
            # 시작 위치 설정 (0부터 5까지)
            start = i
            
            # i번째부터 시작하는 결과 슬라이스
            results_slice = self.results[start:]
            if len(results_slice) < 6:  # 최소 6개 결과 필요 (5번 픽부터 계산 가능)
                continue
                
            # 현재 시작 위치에서 픽 생성
            stage_picks = self._generate_all_stage_picks(start_from=start)
            # ⭐ 5번 후보의 각 단계별 픽 로그 출력
            if (i + 1) == 5 and self.logger:
                debug_stage_picks = self._generate_all_stage_picks(start_from=start)
                for local_pick_num in range(6, 16):  # 픽 번호 6~15 (로컬 기준)
                    global_pick_num = start + local_pick_num  # 전역 픽 번호
                    if global_pick_num in debug_stage_picks:
                        pick_info = debug_stage_picks[global_pick_num]
                        self.logger.info(
                            f"[5번 후보 상세] 픽번호={global_pick_num} | "
                            f"1단계={pick_info['1단계']}, 2단계={pick_info['2단계']}, "
                            f"3단계={pick_info['3단계']}, 4단계={pick_info['4단계']}, "
                            f"5단계={pick_info['5단계']} → 최종={pick_info['최종픽']}"
                        )

            
            picks = []
            # 최종 픽 수집 (6번부터 15번까지)
            for local_pick_num in range(6, 16):  # 로컬 픽 번호 (6~15)
                global_pick_num = start + local_pick_num  # 글로벌 픽 번호
                
                if global_pick_num in stage_picks:
                    picks.append(stage_picks[global_pick_num]["최종픽"])
            
            candidates[i + 1] = picks
            
            # 디버깅용
            if self.logger:
                self.logger.info(f"{i+1}번 후보 픽 생성: {len(picks)}개, 시작위치={start}")
                self.logger.debug(f"{i+1}번 후보 픽 값: {picks}")
        
        return candidates

    def generate_choice_pick(self) -> str:
        if not self.has_sufficient_data():
            if self.logger:
                self.logger.warning("초이스 픽 생성 실패: 충분한 데이터가 없음 (15판 필요)")
            return 'N'

        candidates = self.generate_six_pick_candidates()
        valid_candidates = []

        for idx, picks in candidates.items():
            if len(picks) < 3:
                continue  # 비교할 게 너무 적음

            start = idx - 1
            picks_to_compare = picks[:-1]
            compare_start = start + 5  # 후보 시작 위치 + 로컬 픽 6번
            compare_end = compare_start + len(picks_to_compare)

            if compare_end > len(self.results):
                            # 디버그용 로그 출력
                if self.logger:
                    self.logger.info(
                        f"후보 {idx}번: 결과 비교 구간={results_to_compare}, 픽={picks_to_compare}, "
                        f"W/L 패턴={win_loss_pattern}, 마지막 패턴={last_pattern}"
                    )
                continue  # 결과가 부족하면 제외

            results_to_compare = self.results[compare_start:compare_end]
            win_loss_pattern = ['W' if p == r else 'L' for p, r in zip(picks_to_compare, results_to_compare)]
            last_pattern = win_loss_pattern[-2:]

    
            # 정배 or 역배 판단
            if last_pattern == ['W', 'L']:
                score = win_loss_pattern.count('W') - win_loss_pattern.count('L')
                bet_direction = 'normal'
            elif last_pattern == ['L', 'W']:
                score = win_loss_pattern.count('L') - win_loss_pattern.count('W')
                bet_direction = 'reverse'
            else:
                continue  # LL 등 무효

            if self.logger:
                self.logger.info(
                    f"후보 {idx}번: 픽={picks_to_compare[-2:]}, 결과={results_to_compare[-2:]}, "
                    f"패턴={last_pattern}, 점수={score}, 방향={bet_direction}"
                )

            valid_candidates.append({
                'index': idx,
                'picks': picks,
                'score': score,
                'bet_direction': bet_direction,
                'next_pick': picks[-1],
            })

        if not valid_candidates:
            if self.logger:
                self.logger.warning("유효한 후보 없음. 배팅 중단 (N 반환)")
            return 'N'


        best = max(valid_candidates, key=lambda x: x['score'])
        self.selected_candidate_idx = best['index']
        self.selected_candidate_score = best['score']
        self.betting_direction = best['bet_direction']

        if self.logger:
            self.logger.info(f"🏆 후보 {best['index']}번 선택 | 승점 {best['score']} | 방향: {self.betting_direction}")
        
        return best['next_pick']


    def get_reverse_bet_pick(self, original_pick):
        """
        베팅 방향에 따라 실제 베팅할 픽을 결정합니다.
        
        Args:
            original_pick (str): 원래 선택된 픽
            
        Returns:
            str: 실제 베팅할 픽
        """
        self.original_pick = original_pick
        
        if self.logger:
            self.logger.info(f"[PICK 결정] 현재 방향: {self.betting_direction}, 원 PICK: {original_pick}")

        if self.betting_direction == 'normal':
            return original_pick
        elif self.betting_direction == 'reverse':
            if original_pick == 'P':
                return 'B'
            elif original_pick == 'B':
                return 'P'
        
        return original_pick



# # 시스템 생성 시 로거 전달
# if __name__ == "__main__":
#     import pandas as pd
#     import logging

#     # 예시 결과 (15개)
#     sample_results = ["P", "B", "B", "P", "B", "B", "P", "B", "P", "B", "B", "P", "P", "P", "P"]
#     # 로깅 설정
#     logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
#     logger = logging.getLogger("ChoicePick")

#     # 시스템 인스턴스 생성
#     system = ChoicePickSystem(logger=logger)
#     system.add_multiple_results(sample_results)

#     # 단계별 결과 생성
#     all_picks = system._generate_all_stage_picks()
    
#     # 표로 정리
#     rows = []
#     for pick_num in sorted(all_picks.keys()):
#         row = {"픽번호": pick_num}
#         row.update(all_picks[pick_num])
#         rows.append(row)

#     df = pd.DataFrame(rows)
#     print("입력된 결과:", sample_results)
#     print("\n[단계별 픽 결과 표]")
#     print(df.to_string(index=False))
    
#     # 6픽 후보들 생성
#     print("\n[6개 후보 픽 결과]")
#     six_candidates = system.generate_six_pick_candidates()
#     # for idx, picks in six_candidates.items():
#         # print(f"{idx}번 후보 ({len(picks)}개): {picks}")
    
#     # 최종 선택된 픽과 배팅 방향
#     # print("\n[최종 픽 선택 및 배팅 방향]")
#     final_pick = system.generate_choice_pick()
#     betting_direction = "정배팅" if system.betting_direction == "normal" else "역배팅"
#     actual_pick = system.get_reverse_bet_pick(final_pick)
    
#     # 선택된 후보 번호와 승점 정보가 있다면 출력
#     if hasattr(system, 'selected_candidate_idx') and hasattr(system, 'selected_candidate_score'):
#         print(f"선택된 후보: {system.selected_candidate_idx}번")
#         print(f"승점: {system.selected_candidate_score}")
    
#     print(f"최종 선택된 픽: {final_pick}")
#     print(f"배팅 방향: {betting_direction}")
#     print(f"실제 베팅할 픽: {actual_pick}")
    
#     # 1번 후보 상세 분석
#     # print("\n[1번 후보 상세 분석]")
#     # candidate1_picks = system._generate_all_stage_picks(start_from=0)
#     # candidate1_df = pd.DataFrame([
#     #     {
#     #         "픽번호": num,
#     #         "1단계": pick["1단계"],
#     #         "2단계": pick["2단계"],
#     #         "3단계": pick["3단계"],
#     #         "4단계": pick["4단계"],
#     #         "5단계": pick["5단계"],
#     #         "최종": pick["최종픽"],
#     #     }
#     #     for num, pick in sorted(candidate1_picks.items())
#     # ])
#     # print(candidate1_df.to_string(index=False))