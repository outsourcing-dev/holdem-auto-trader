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
        
        # 중요: consecutive_n_count는 오직 ChoicePickSystem에서만 관리
        self.consecutive_n_count: int = 0  # 연속 N 발생 카운트
        
        # 추가: 새로 추가된 속성들
        self.should_refresh_data: bool = True  # 데이터 리프레시 필요 여부 플래그
        self.failure_count: int = 0  # 연속 실패 카운트 (3회까지만 추적)

        # 로그 메시지 (logger가 없을 경우 대비)
        if self.logger:
            self.logger.info("ChoicePickSystem 인스턴스 생성")
            self.logger.info("[N 카운트 초기화] 객체 생성 시 초기화: 0")
        
        self.last_results: List[str] = []
        self.cached_pick: Optional[str] = None
        
        self.current_candidate_index = None  # 현재 선택된 후보 인덱스 (1-6)
        self.current_candidates = {}         # 현재 6개 후보 정보 저장
        self.consecutive_loss_with_candidate = 0  # 현재 후보로 연속 실패 횟수
        self.max_loss_with_same_candidate = 3  # 동일 후보로 최대 허용 실패 횟수
        self.skip_n_count = False  # 방 입장 시 첫 분석에서 N 카운트 증가 건너뛰기 플래그
        self.fixed_candidate = None
        self._entered_round = 0
        self._current_game_round = 0
        self.wait_first_result = False  # ✅ 방 입장 직후 PICK 차단용 플래그

    # utils/choice_pick.py의 ChoicePickSystem 클래스에 추가할 메서드
    def set_martin_amounts(self, amounts):
        """마틴 금액 설정"""
        self.martin_amounts = amounts
        if self.logger:
            self.logger.info(f"마틴 금액 업데이트: {amounts}")

    def add_result(self, result: str) -> None:
        if result not in ['P', 'B']:
            return

        self.results.append(result)

        if self.should_refresh_data and getattr(self, 'failure_count', 0) == 0 and len(self.results) > 15:
            self.results = self.results[-15:]
        else:
            if self.logger:
                self.logger.info(f"결과 추가 후 길이: {len(self.results)}개 (현재 데이터)")

        if self.logger:
            self.logger.debug(f"현재 결과 리스트: {self.results}")

        self.last_win_count += 1


    def add_multiple_results(self, results: List[str]) -> None:
        filtered_results = [r for r in results if r in ['P', 'B']]

        failure_count = getattr(self, 'failure_count', 0)
        max_results = 15 + min(failure_count, 2)

        if len(filtered_results) > max_results:
            filtered_results = filtered_results[-max_results:]
            
        self.results = filtered_results



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
        self.logger.info(f"[DEBUG] record_betting_result 전: should_refresh_data={getattr(self, 'should_refresh_data', None)}, failure_count={getattr(self, 'failure_count', 0)}")

        self.betting_attempts += 1
        self.pick_results.append(is_win)

        if is_win:
            self.fixed_candidate = None
            self.should_refresh_data = True
            self.failure_count = 0

            if len(self.results) > 15:
                self.results = self.results[-15:]

            if reset_after_win:
                self.consecutive_failures = 0
                self.last_win_count = 0

        else:
            self.consecutive_loss_with_candidate += 1
            self.consecutive_failures += 1
            self.failure_count += 1

            # 🔥 실패한 게임 결과를 직접 추가 (기존 결과 유지 + 실패 반영)
            last_bet = getattr(self, 'current_pick', None)
            if last_bet in ['P', 'B']:
                corrected_result = 'B' if last_bet == 'P' else 'P'
                self.logger.info(f"[실패 처리] 반대 결과 추가: {corrected_result} (내 pick: {last_bet})")
                self.results.append(corrected_result)
                # 최대 17개까지 유지 (15 + 2회 실패 시)
                if len(self.results) > 17:
                    self.results = self.results[-17:]

            self.should_refresh_data = False

            if self.failure_count >= 3:
                self.should_refresh_data = True
                self.failure_count = 0
                self.fixed_candidate = None
                self.current_candidates = {}
                self.current_candidate_index = None
                self.consecutive_loss_with_candidate = 0
                self.cached_pick = None
                self.last_results = []
                self.current_pick = None
                self.logger.info("3회 연속 실패: 방 이동 및 상태 초기화")
            else:
                self.logger.info(f"실패 {self.failure_count}회: 기존 결과 유지 + 1개 추가")

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
        # 명확한 로깅 추가
        if self.logger:
            self.logger.info(f"[방 이동 조건 체크] 연속 N 카운트: {self.consecutive_n_count}")
        
        # ✅ 4연속 N - 명확한 로깅 추가 (뭐가 중복호출되서 1번 픽 생성시 2개씩 ..)
        if self.consecutive_n_count >= 8:
            if self.logger:
                self.logger.warning(f"[방 이동 필요!!] 4번 연속 유효한 픽 없음(N) 발생 - 현재 N 카운트: {self.consecutive_n_count}")
            return True

        # ✅ 3연패 조건 개선
        if len(self.pick_results) >= 3:
            # 최근 3개 결과가 모두 False(패배)인지 확인
            recent_three = self.pick_results[-3:]
            # 연속된 패배인지 확인 (연속성 체크 추가)
            consecutive_failures = 0
            for result in reversed(self.pick_results):
                if not result:  # 패배인 경우
                    consecutive_failures += 1
                else:  # 승리인 경우
                    break  # 연속성이 끊김
            
            if consecutive_failures >= 3:
                self.logger.info(f"[마틴] 3연패 감지: 최근 결과 {self.pick_results[-5:]}, 연속 패배 {consecutive_failures}회")
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
            
            # 현재 후보와 실패 횟수도 유지 - 마틴 유지 시 중요
            if self.current_candidate_index is not None:
                self.logger.info(f"방 이동 시에도 후보({self.current_candidate_index}번) 유지, 실패 횟수: {self.consecutive_loss_with_candidate}회")
        else:
            self.consecutive_failures = 0
            self.pick_results = []
            
            # 후보도 초기화
            self.current_candidates = {}
            self.current_candidate_index = None
            self.consecutive_loss_with_candidate = 0
            self.fixed_candidate = None  # ✅ 추가: 고정 후보 초기화 필요!
            self.logger.info("방 이동 시 preserve_martin=False → 마틴 상태와 후보 초기화")

        # ✅ 추가: recent_results 초기화 (방 이동 후 연속 패배 기록 리셋)
        if hasattr(self, 'recent_results'):
            self.recent_results = []
            self.logger.info("방 이동 후 recent_results 배열 초기화")

        # ✅ 중요: N 카운트 초기화 - 이 부분은 항상 초기화
        self.consecutive_n_count = 0
        self.logger.info("[N 카운트 초기화] 방 이동으로 인한 초기화")
        
        self.current_pick = None

        if self.logger:
            self.logger.info(
                f"방 이동 후 초기화 완료 - 연속실패({prev_failures}→{self.consecutive_failures}), "
                f"결과개수({prev_results}), 연속 N({prev_n_count}→{self.consecutive_n_count})"
            )
        
        self.skip_n_count = True  # 방 입장 후 첫 N은 카운트하지 않음

            
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
        6개의 후보 픽 생성 + 점수 계산 포함 (정배팅/역배팅 판별 포함)

        Returns:
            Dict[int, Dict[str, Any]]: 각 후보별 {
                1: {"scoring_picks": [...], "next_pick": 'B', "score": 2, "pattern": "WLWL", "betting_direction": "normal"},
                ...
            }
        """
        if self.logger:
            self.logger.info("===== 후보 픽 생성 시작 =====")
            self.logger.info(f"입력 데이터 (총 {len(self.results)}개): {self.results}")

        # 데이터 부족 시 종료
        if not self.has_sufficient_data():
            if self.logger:
                self.logger.warning(f"후보 픽 생성 실패: 데이터 부족 (현재 {len(self.results)}/15판)")
            return {}

        candidates = {}
        base_start = max(0, len(self.results) - 15)

        # 후보 1~6 생성 시도
        for i in range(6):
            start = base_start + i
            results_slice = self.results[start:]

            # 최소 6개 결과 필요
            if len(results_slice) < 6:
                if self.logger:
                    self.logger.info(f"후보 {i+1}번: 데이터 부족으로 생성 불가 (필요: 6개, 있음: {len(results_slice)}개)")
                continue

            stage_picks = self._generate_all_stage_picks(start_from=start)

            # 예측 픽 리스트 생성 (16~17~18 위치의 픽들)
            picks = []
            for local_pick_num in range(6, 18):  # 픽 번호 6~17까지
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

        # 후보별 비교 기준 길이 맞추기 (스코어 비교 위해 패딩)
        if candidates:
            max_len = max(len(c["scoring_picks"]) for c in candidates.values())
            for c in candidates.values():
                while len(c["scoring_picks"]) < max_len:
                    c["scoring_picks"].append("N")

        # 각 후보에 대해 점수 및 방향 계산
        for idx, candidate in candidates.items():
            picks = candidate["scoring_picks"]
            actual_results = self.results[4 + idx:]  # 후보별 비교 시작 위치 다름
            compare_len = min(len(picks), len(actual_results))
            picks_to_compare = picks[:compare_len]

            # 비교할 데이터가 너무 적으면 무효
            if compare_len < 3:
                candidate["score"] = -999
                candidate["pattern"] = ""
                candidate["betting_direction"] = "normal"
                continue

            # 승패 패턴 계산
            win_loss_pattern = []
            wins = 0
            for i in range(compare_len):
                if picks_to_compare[i] == actual_results[i]:
                    win_loss_pattern.append("W")
                    wins += 1
                else:
                    win_loss_pattern.append("L")

            pattern_str = "".join(win_loss_pattern)

            # 연속 승/패 3번 이상이면 무효 처리
            if 'WWW' in pattern_str or 'LLL' in pattern_str:
                candidate["score"] = -999
                candidate["pattern"] = pattern_str
                candidate["betting_direction"] = "normal"
                self.logger.info(f"[후보 {idx}] 무효 패턴 감지: {pattern_str} → 제외 (score=-999)")
                continue

            # 방향 및 점수 계산 (마지막 2개 기준)
            last_two = pattern_str[-2:]
            if last_two == "WL":
                direction = "normal"
                score = wins - (compare_len - wins)
            elif last_two == "LW":
                direction = "reverse"
                score = (compare_len - wins) - wins
            else:
                direction = "normal"
                score = -999  # 무효 점수

            # 최종 저장 및 로그
            candidate["score"] = score
            candidate["pattern"] = pattern_str
            candidate["betting_direction"] = direction

            self.logger.info(f"[후보 {idx}] W/L 패턴: {pattern_str}, 스코어: {score}, 방향: {direction}")

        return candidates

    def generate_choice_pick(self):
        """
        정확히 15개일 때만 새로운 후보를 생성하고 고정합니다.
        이후 결과가 16, 17개로 늘어나더라도 고정된 후보의 17, 18번째 예상 PICK을 사용합니다.
        """
        # 게임 결과 캐싱 - 같은 게임에 대해 중복 호출 방지
        current_game_round = getattr(self, '_current_game_round', 0)
        if hasattr(self, '_last_pick_round') and self._last_pick_round == current_game_round:
            self.logger.info(f"[중복 방지] 게임 {current_game_round}에 대해 이미 PICK 생성함. 재사용: {self.current_pick}")
            return self.current_pick

        if self.wait_first_result:
            self.logger.info("[초이스픽] wait_first_result=True → PICK 생략: N 반환")
            self.current_pick = "N"
            self.skip_n_count = True
            return "N"
        
        # 정확히 15개인데 이미 고정 후보가 있으면 후보 생성을 막는다
        if len(self.results) == 15 and self.fixed_candidate is not None:
            self.logger.info("🚫 이미 고정 후보가 있는 상태에서 15개로 재호출 → 중복 생성 방지")
            return self.fixed_candidate.get('next_pick', 'N')

        # ✅ 0. 방 입장 직후 동일 라운드 체크 - entered_round와 current_game_round가 같으면 N 반환
        entered_round = getattr(self, '_entered_round', None)
        current_round = getattr(self, '_current_game_round', None)
        if entered_round is not None and current_round is not None and entered_round == current_round:
            self.logger.info(f"[방어 로직] 입장 라운드({entered_round})와 현재 라운드({current_round})가 동일 → PICK 생성 생략, 'N' 반환")
            return 'N'
        
        # ✅ 1. 자동 결과 동기화 및 누적
        if hasattr(self, 'main_window') and hasattr(self.main_window, 'trading_manager'):
            tm = self.main_window.trading_manager
            game_state = tm.game_monitoring_service.get_current_game_state()

            if game_state:
                tm.excel_trading_service.process_game_results(
                    game_state,
                    tm.game_count,
                    tm.current_room_name,
                    log_on_change=True
                )
                new_results = game_state.get("filtered_results", [])
                if new_results:
                    self.results += [r for r in new_results if r in ['P', 'B']]
                    self.results = self.results[-30:]  # 결과는 최대 30개까지만 유지
                self.logger.info(f"[자동 동기화] 누적된 결과 개수: {len(self.results)}")
            else:
                self.logger.warning("⚠️ 최신 게임 상태를 가져오지 못해 PICK 생성을 중단합니다.")
                return 'N'

        # ✅ 2. TIE 유지 처리
        if getattr(self, 'skip_pick_generation', False):
            self.logger.info("[TIE 후 유지] 기존 PICK 재사용 (새 PICK 생성 안함)")
            self.skip_pick_generation = False
            return self.current_pick

        # ✅ 3. 방 입장 직후 대기 모드
        entered_round = getattr(self, '_entered_round', 0)
        current_game_round = getattr(self, '_current_game_round', 0)
        wait_first_result = current_game_round <= entered_round
        if wait_first_result:
            self.logger.info(f"[대기 모드] 방 입장 직후라 PICK 생성 안함 (입장라운드={entered_round}, 현재라운드={current_game_round})")
            if not getattr(self, 'skip_n_count', False) and not getattr(self, 'just_changed_room', False):
                self.skip_n_count = True
            return 'N'
        # ✅ 3-2. 실시간 진입되었으면 skip 해제
        if self.skip_n_count:
            self.logger.info("[N카운트 스킵 해제] 실시간 분석 시작됨 → skip_n_count=False 전환")
            self.skip_n_count = False
        # ✅ 4. 데이터 부족 시
        if len(self.results) < 15:
            self.logger.warning("후보 생성 실패: 데이터 부족 (15개 미만)")
            if not getattr(self, 'skip_n_count', False) and not getattr(self, 'just_changed_room', False):
                self.consecutive_n_count += 1
            return 'N'

        # ✅ 5. 정확히 15개일 때만 새 후보 생성
        if len(self.results) == 15:
            self.logger.info("🎯 정확히 15개 결과 - 새로운 후보 생성 시작")
            self.logger.info(f"🎯 현재 결과 리스트 (15개): {self.results}")
            six_pick_candidates = self.generate_six_pick_candidates()
            if not six_pick_candidates:
                self.logger.warning("후보 생성 실패: 유효한 후보 없음")
                if not getattr(self, 'skip_n_count', False) and not getattr(self, 'just_changed_room', False):
                    self.consecutive_n_count += 1
                return 'N'

            # 최고 점수 후보 선택
            best_index, best_candidate = None, None
            best_score = float('-inf')
            for idx, candidate in six_pick_candidates.items():
                if 'score' in candidate and candidate['score'] > best_score:
                    best_score = candidate['score']
                    best_index = idx
                    best_candidate = candidate

            # 🔥 필터링 추가 (score가 -999 이상이어야 유효)
            if best_candidate is None or best_candidate.get("score", -999) <= -999:
                self.logger.warning("❌ 유효한 후보 없음 → PICK 생성 실패")
                if not getattr(self, 'skip_n_count', False) and not getattr(self, 'just_changed_room', False):
                    self.consecutive_n_count += 1
                return 'N'

            # 후보 고정
            self.fixed_candidate = {
                'next_pick': best_candidate.get('next_pick', 'N'),
                'betting_direction': best_candidate.get('betting_direction', 'normal')
            }
            self.current_candidate_index = best_index
            self.consecutive_loss_with_candidate = 0
            self.logger.info(f"✅ 새 고정 후보({best_index}) 생성 및 저장 완료")
            self.logger.info(f"✅ 고정 후보 PICK: {self.fixed_candidate['next_pick']}, 방향: {self.fixed_candidate['betting_direction']}")

        # ✅ 6. 고정 후보 사용
        if self.fixed_candidate:
            pick = self.fixed_candidate.get('next_pick', 'N')
            self.betting_direction = self.fixed_candidate.get('betting_direction', 'normal')

            # 🔽 결과가 16개 이상일 때만 로그 출력 (실패 이후 pick 재사용 상태)
            if len(self.results) >= 16:
                self.logger.info(f"🎯 현재 결과 리스트 ({len(self.results)}개): {self.results}")
                self.logger.info(f"🎯 고정 PICK 사용 중 - 후보 인덱스: {self.current_candidate_index}, PICK: {pick}, 방향: {self.betting_direction}")

            if pick in ['P', 'B']:
                self.current_pick = pick
                self.consecutive_n_count = 0
                # 해당 게임 라운드 기록
                self._last_pick_round = current_game_round
                return pick
            else:
                self.logger.warning(f"[고정 후보 오류] next_pick 유효하지 않음: {pick}")
                if not getattr(self, 'skip_n_count', False) and not getattr(self, 'just_changed_room', False):
                    self.consecutive_n_count += 1
                return 'N'

        # ✅ 7. fallback - 여기서 "고정 후보가 없어서 PICK 반환 실패" 로그가 출력되지 않도록 수정
        # N 카운트만 증가시키고 바로 'N' 반환
        if not getattr(self, 'skip_n_count', False) and not getattr(self, 'just_changed_room', False):
            self.consecutive_n_count += 1
            self.logger.info(f"[N카운트 증가] consecutive_n_count = {self.consecutive_n_count}")
        return 'N'

    def get_reverse_bet_pick(self, original_pick):
        """
        베팅 방향에 따라 실제 베팅할 픽을 결정합니다.
        """
        self.original_pick = original_pick
        
        if self.logger:
            self.logger.info(f"[최종 베팅 결정] 원래 PICK: {original_pick}, 방향: {self.betting_direction}, 후보: {self.current_candidate_index}")
            
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
