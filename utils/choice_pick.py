import logging
from turtle import pd
from typing import List, Dict, Optional, Tuple, Any


class ChoicePickSystem:
    """
    초이스 픽 시스템 - 15판 기준의 베팅 전략 구현
    """
    # utils/choice_pick.py의 ChoicePickSystem 클래스 __init__ 수정
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

        # 기존 초기화 변수들
        self.results: List[str] = []  # 최근 15판 결과 (P/B만)
        self.current_pick: Optional[str] = None  # 현재 초이스 픽
        self.betting_direction: str = "normal"  # 'normal' 또는 'reverse'
        self.consecutive_failures: int = 0  # 연속 실패 횟수
        self.pick_scores: Dict[str, int] = {}  # 픽 후보들의 점수
        self.betting_attempts: int = 0  # 현재 픽으로 배팅 시도 횟수

        # 3마틴 배팅 관련 변수
        self.martin_step: int = 0  # 현재 마틴 단계 (0부터 시작)
        
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
        
        self.consecutive_n_count: int = 0  # 연속 N 발생 카운트
        
        # 추가: 새로 추가된 속성들
        self.should_refresh_data: bool = True  # 데이터 리프레시 필요 여부 플래그
        self.failure_count: int = 0  # 연속 실패 카운트 (3회까지만 추적)

        # 로그 메시지 (logger가 없을 경우 대비)
        if self.logger:
            self.logger.info("ChoicePickSystem 인스턴스 생성")
        
        self.last_results: List[str] = []
        self.cached_pick: Optional[str] = None

    # utils/choice_pick.py의 ChoicePickSystem 클래스에 추가할 메서드
    def set_martin_amounts(self, amounts):
        """마틴 금액 설정"""
        self.martin_amounts = amounts
        if self.logger:
            self.logger.info(f"마틴 금액 업데이트: {amounts}")

    def add_result(self, result: str) -> None:
        """
        새 결과 추가 (TIE는 무시) - 실패 시 기존 데이터에 계속 추가
        """
        if result not in ['P', 'B']:
            return

        # ✅ 항상 추가하고
        self.results.append(result)

        # ✅ failure_count가 0일 때만 리스트를 자름 (실패 모드가 아닐 때만)
        if self.should_refresh_data and getattr(self, 'failure_count', 0) == 0 and len(self.results) > 15:
            self.results = self.results[-15:]  # 최근 15개만 유지
            if self.logger:
                self.logger.info(f"리스트 잘라냄: 15개 유지 (상태: should_refresh_data={self.should_refresh_data}, failure_count={getattr(self, 'failure_count', 0)})")
        else:
            if self.logger:
                self.logger.info(f"결과 추가 후 길이: {len(self.results)}개 (현재 데이터)")

        if self.logger:
            self.logger.info(f"결과 추가: {result} (현재 {len(self.results)}개 데이터)")
            self.logger.debug(f"현재 결과 리스트: {self.results}")

        self.last_win_count += 1
        
    def add_multiple_results(self, results: List[str]) -> None:
        # 디버깅: 원본 전달된 결과 로그
        self.logger.info(f"[DEBUG] add_multiple_results 호출 전 원본 결과: {results}")
        
        filtered_results = [r for r in results if r in ['P', 'B']]
        
        # 필터링된 결과 확인
        self.logger.info(f"[DEBUG] add_multiple_results 필터링된 결과: {filtered_results}")

        # 중요: failure_count에 따라 결과 개수 제한
        failure_count = getattr(self, 'failure_count', 0)
        max_results = 15 + min(failure_count, 2)  # 최대 17개 (15 + 실패횟수 최대 2)
        
        # 결과가 max_results보다 많으면 최근 데이터만 유지
        if len(filtered_results) > max_results:
            filtered_results = filtered_results[-max_results:]
            self.logger.info(f"결과가 너무 많아 최근 {max_results}개만 유지합니다")
            
        self.results = filtered_results

        if self.logger:
            self.logger.info(f"다중 결과 추가: 총 {len(self.results)}개 (최대 {max_results}개 제한)")
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

            # 세부 계산 로깅 추가
            if self.logger and pick_number >= 6:  # 6번 픽부터 로깅
                self.logger.debug(f"\n픽번호 {global_pick_num} 계산 시작:")
                
            # 1단계 계산 로깅
            pick1 = safe_get(sliced_results, pos - 4)
            pick2 = safe_get(sliced_results, pos - 3)
            pick4 = safe_get(sliced_results, pos - 1)
            
            if self.logger and pick_number >= 6:
                self.logger.debug(f"  1단계 입력: pick1({pos-4})={pick1}, pick2({pos-3})={pick2}, pick4({pos-1})={pick4}")
                
            stage1 = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4) if pick1 != 'N' and pick2 != 'N' and pick4 != 'N' else 'N'
            stage1_picks[pos] = stage1
            
            if self.logger and pick_number >= 6:
                condition = "같음" if pick1 == pick2 else "다름"
                result = "pick4 그대로" if pick1 == pick2 else "pick4의 반대"
                self.logger.debug(f"  1단계 판단: pick1과 pick2는 {condition} → {result} → 결과={stage1}")

            # 2단계 로깅 추가
            if pick_number < 6:
                stage2 = 'N'
                if self.logger and pick_number >= 6:
                    self.logger.debug(f"  2단계: 픽번호 6 미만이라 N 반환")
            else:
                win_count = 0
                win_details = []
                
                for i in range(1, 5):
                    prev = pick_number - i
                    prev_idx = prev - 1
                    if 0 <= prev_idx < len(stage1_picks):
                        prev_stage1 = stage1_picks[prev_idx]
                        prev_result = safe_get(sliced_results, prev_idx)
                        
                        if prev_stage1 != 'N' and prev_result == prev_stage1:
                            win_count += 1
                            win_details.append(f"픽{prev}(1단계={prev_stage1}, 결과={prev_result}): 적중")
                        elif prev_stage1 != 'N':
                            win_details.append(f"픽{prev}(1단계={prev_stage1}, 결과={prev_result}): 실패")
                        
                stage2 = stage1 if win_count >= 2 else self.get_opposite_pick(stage1)
                
                if self.logger and pick_number >= 6:
                    self.logger.debug(f"  2단계 승수 계산: {win_details}")
                    self.logger.debug(f"  2단계 판단: 이전 4판 중 {win_count}승 → {'유지' if win_count >= 2 else '반대'} → 결과={stage2}")
            
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
                    # self.logger.info(f"[5단계 계산] pick={global_pick_num}, 이전 4판 승수={win_count}, stage4={stage4}, 결정={stage5}")
                    pass
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
            # if self.logger:
            #     self.logger.info(
            #         f"[5단계 계산] pick={pick_number}, 이전 4판 승수={win_count}, stage4={stage4}, 결정={stage5}"
            #     )
        
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
 
    # utils/choice_pick.py 파일의 record_betting_result 메소드
    def record_betting_result(self, is_win: bool, reset_after_win: bool = True) -> None:
        """
        베팅 결과 기록 - 실패 시 데이터 유지 및 추가 로직
        
        Args:
            is_win (bool): 베팅 성공 여부
            reset_after_win (bool): 승리 후 초기화 여부
        """
        # 여기에 디버깅 코드 추가 (함수 시작 부분)
        self.logger.info(f"[DEBUG] record_betting_result 전: should_refresh_data={getattr(self, 'should_refresh_data', None)}, failure_count={getattr(self, 'failure_count', 0)}")
        
        # 기존 코드
        self.betting_attempts += 1
        self.pick_results.append(is_win)

        if is_win:
            if self.logger:
                self.logger.info(f"베팅 성공! 시도: {self.betting_attempts}번째")
            
            # 성공 시 데이터 리프레시 플래그 활성화 - 새로운 15개 데이터 수집으로 전환
            self.should_refresh_data = True
            self.failure_count = 0
            if len(self.results) > 15:
                self.results = self.results[-15:]
                if self.logger:
                    self.logger.info(f"[초기화] 예측 적중으로 최근 15개만 유지: {self.results}")
            if reset_after_win:
                self.consecutive_failures = 0
                self.last_win_count = 0
        else:
            if self.logger:
                self.logger.info(f"베팅 실패. 시도: {self.betting_attempts}번째")
            
            self.consecutive_failures += 1
            self.failure_count += 1
            self.should_refresh_data = False  # ✅ 실패 모드 전환 → 누적 유지

            # 3연패까지는 데이터 계속 추가, 그 이상은 리프레시
            if self.failure_count >= 3:
                self.should_refresh_data = True
                self.failure_count = 0
                self.cached_pick = None
                self.last_results = []
                self.current_pick = None  # ✅ 여기에 추가
                if self.logger:
                    self.logger.info("3연패로 인해 데이터 리프레시 플래그 활성화")
            else:
                if self.logger:
                    self.logger.info(f"실패 {self.failure_count}회: 기존 데이터 유지 + 결과 추가 모드")
        
        # 여기에 디버깅 코드 추가 (함수 끝 부분)
        self.logger.info(f"[DEBUG] record_betting_result 후: should_refresh_data={getattr(self, 'should_refresh_data', None)}, failure_count={getattr(self, 'failure_count', 0)}")
            
    def get_current_bet_amount(self, widget_position=None) -> int:
        # 최신 설정 로드
        from utils.settings_manager import SettingsManager
        settings_manager = SettingsManager()
        _, latest_martin_amounts = settings_manager.get_martin_settings()
        
        # 최신 마틴 금액으로 업데이트
        self.martin_amounts = latest_martin_amounts

        # widget_position이 제공되지 않으면 기본값 0 사용
        if widget_position is None:
            widget_position = 0
            if self.logger:
                self.logger.debug(f"위젯 포지션 제공되지 않음, 기본값 0 사용")
        
        # 마틴 단계 수 확인
        martin_stages = len(self.martin_amounts)
        
        # 마틴 단계 계산 (모듈러 방식)
        effective_step = widget_position % martin_stages
        
        # 로그 추가
        if self.logger:
            self.logger.debug(f"위젯 포지션: {widget_position}, 마틴 단계: {effective_step+1}/{martin_stages}")
        
        # 계산된 단계에 해당하는 금액 반환
        bet_amount = self.martin_amounts[effective_step]
        if self.logger:
            self.logger.debug(f"현재 베팅 금액: {bet_amount:,}원 (위젯: {widget_position+1}번, 마틴: {effective_step+1}단계)")
            self.logger.debug(f"전체 마틴 금액 설정: {self.martin_amounts}")
        
        return bet_amount

    def should_change_room(self) -> bool:
        """
        방 이동이 필요한지 확인
        Returns:
            bool: 방 이동 필요 여부
        """

        # ✅ 2연패 조건 (pick_results에서 False 2번 연속 확인)
        if len(self.pick_results) >= 3 and all(not r for r in self.pick_results[-3:]):
            if self.logger:
                self.logger.info("최근 3연패 감지로 방 이동 필요")
            return True
        
        # ✅ 4연속 N
        if self.consecutive_n_count >= 4:
            if self.logger:
                self.logger.info(f"4번 연속 유효한 픽 없음(N) 발생으로 방 이동 필요 (연속 카운트: {self.consecutive_n_count})")
            return True

        # ✅ 55판 이상이고 배팅 안함
        if self.betting_attempts == 0 and self.last_win_count >= 55:
            if self.logger:
                self.logger.info(f"현재 게임 판수가 55판 이상이고 배팅 중이 아님 → 방 이동 필요")
            return True

        return False

    
    # utils/choice_pick.py 파일의 ChoicePickSystem 클래스에 있는 함수
    def reset_after_room_change(self, preserve_martin: bool = False) -> None:
        """
        방 이동 후 상태 초기화
        
        Args:
            preserve_martin (bool): True면 마틴 단계 유지
        """
        # 'consecutive_losses' 대신 'consecutive_failures' 사용
        prev_failures = self.consecutive_failures
        prev_results = len(self.pick_results)
        prev_n_count = self.consecutive_n_count

        self.betting_attempts = 0

        # ✅ 마틴 상태 유지 여부에 따라 분기
        if preserve_martin:
            self.logger.info("방 이동 시 preserve_martin=True → 마틴 상태 유지")
            # 최근 실패 기록 유지
            self.pick_results = self.pick_results[-3:]  # 최근 3개 정도 유지
        else:
            self.consecutive_failures = 0
            self.pick_results = []
            self.logger.info("방 이동 시 preserve_martin=False → 마틴 상태 초기화")

        # ✅ 추가: recent_results 초기화 (방 이동 후 연속 패배 기록 리셋)
        if hasattr(self, 'recent_results'):
            self.recent_results = []
            self.logger.info("방 이동 후 recent_results 배열 초기화")

        # ✅ 공통 초기화 항목
        self.consecutive_n_count = 0
        self.current_pick = None

        if self.logger:
            self.logger.info(
                f"방 이동 후 초기화 완료 - 연속실패({prev_failures}→{self.consecutive_failures}), "
                f"결과개수({prev_results}), 연속 N({prev_n_count}→{self.consecutive_n_count})"
            )
            
    def clear(self) -> None:
        """전체 데이터 초기화"""
        self.results = []
        self.current_pick = None
        self.betting_direction = "normal"
        self.consecutive_failures = 0
        self.pick_scores = {}
        self.betting_attempts = 0
        self.pick_results = []
        self.last_win_count = 0
        self.stage1_picks = []
        self.stage2_picks = []
        self.stage3_picks = []
        self.stage4_picks = []
        self.stage5_picks = []
    
    def generate_six_pick_candidates(self) -> Dict[int, Dict[str, List[str]]]:
        """
        6개의 후보 픽 생성 (시작 위치별)

        Returns:
            Dict[int, Dict[str, List[str]]]: 각 후보별 {
                1: {"scoring_picks": [...], "next_pick": 'B'},
                2: {...},
                ...
            }
        """
        if self.logger:
            self.logger.info(f"===== 후보 픽 생성 시작 =====")
            self.logger.info(f"입력 데이터 (총 {len(self.results)}개): {self.results}")

        if not self.has_sufficient_data():
            if self.logger:
                self.logger.warning(f"후보 픽 생성 실패: 데이터 부족 (현재 {len(self.results)}/15판)")
            return {}

        candidates = {}

        for i in range(6):  # 후보 1~6번
            start = i
            results_slice = self.results[start:]

            if len(results_slice) < 6:  # 최소 6개 결과 필요
                if self.logger:
                    self.logger.info(f"후보 {i+1}번: 데이터 부족으로 생성 불가 (필요: 6개, 있음: {len(results_slice)}개)")
                continue

            stage_picks = self._generate_all_stage_picks(start_from=start)

            picks = []
            for local_pick_num in range(6, 18):  # 픽 번호 6~17까지 시도 (예측 실패 대비)
                global_pick_num = start + local_pick_num
                if global_pick_num in stage_picks:
                    picks.append(stage_picks[global_pick_num]["최종픽"])

            if picks:
                candidate_data = {
                    "scoring_picks": picks[:-1] if len(picks) > 1 else [],
                    "next_pick": picks[-1] if len(picks) > 0 else 'N'
                }
                candidates[i + 1] = candidate_data

                if self.logger:
                    self.logger.info(f"후보 {i+1}번 픽 생성 결과: {picks}")

        # ===== 후보 간 길이 통일 처리 =====
        if candidates:
            max_len = max(len(c["scoring_picks"]) for c in candidates.values())
            for c in candidates.values():
                while len(c["scoring_picks"]) < max_len:
                    c["scoring_picks"].append("N")  # 비교용 패딩

        if self.logger:
            self.logger.info(f"===== 총 {len(candidates)}개 후보 생성 완료 =====")

        return candidates


    def generate_choice_pick(self) -> str:
        # 로그 추가: 데이터 상태
        self.logger.info(f"generate_choice_pick 실행 - 현재 데이터: {self.results}, 길이: {len(self.results)}")
        
        six_pick_candidates = self.generate_six_pick_candidates()
        
        # 로그 추가: 후보 수
        self.logger.info(f"생성된 픽 후보 수: {len(six_pick_candidates)}")
        
        if not six_pick_candidates:
            self.logger.warning("픽 후보가 생성되지 않음")
            return 'N'

        actual_results = self.results[5:]  # 결과 비교 시작은 6번부터
        valid_candidates = []

        for candidate_idx, candidate in six_pick_candidates.items():
            picks = candidate["scoring_picks"]
            next_pick = candidate["next_pick"]
            
            # 로그 추가: 각 후보 정보
            self.logger.debug(f"후보 {candidate_idx}: scoring_picks={picks}, next_pick={next_pick}")

            compare_len = min(len(picks), len(actual_results))
            if compare_len < 3:  # 비교할 데이터가 너무 적으면 제외
                continue

            wins = 0
            for i in range(compare_len):
                if picks[i] == actual_results[i]:
                    wins += 1
            losses = compare_len - wins

            score = wins - losses
            candidate["score"] = score
            
            # 로그 추가: 점수 계산
            self.logger.debug(f"후보 {candidate_idx} 점수 계산: {wins}승 {losses}패, 점수={score}")

            # 'WWW', 'LLL' 같은 특정 패턴 제외 등 추가 조건 가능
            valid_candidates.append(candidate)

        if not valid_candidates:
            self.logger.warning("유효한 후보가 없음")
            return 'N'

        best_candidate = max(valid_candidates, key=lambda c: c["score"])
        
        # 로그 추가: 최종 선택
        self.logger.info(f"최종 선택 후보 점수: {best_candidate['score']}, 픽: {best_candidate['next_pick']}")
        
        return best_candidate["next_pick"]

    def get_reverse_bet_pick(self, original_pick):
        """
        베팅 방향에 따라 실제 베팅할 픽을 결정합니다.
        """
        self.original_pick = original_pick
        
        if self.logger:
            self.logger.info(f"[최종 베팅 결정] 원래 PICK: {original_pick}, 방향: {self.betting_direction}")
            
        if self.betting_direction == 'normal':
            if self.logger:
                self.logger.info(f"정배팅 적용 → 최종 베팅: {original_pick}")
            return original_pick
        elif self.betting_direction == 'reverse':
            reversed_pick = 'B' if original_pick == 'P' else 'P'
            if self.logger:
                self.logger.info(f"역배팅 적용 → 최종 베팅: {reversed_pick}")
            return reversed_pick
        
        return original_pick