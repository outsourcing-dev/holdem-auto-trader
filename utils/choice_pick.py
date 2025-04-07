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
        self.stage4_picks = []
        self.stage5_picks = []
        if self.logger:
            self.stage4_picks = []
        self.stage5_picks = []
        if self.logger:
            self.logger.info("초이스 픽 시스템 전체 초기화 완료")
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

    def _generate_all_stage_picks(self) -> Dict[int, Dict[str, str]]:
        """
        현재 결과 데이터를 기반으로 5~18번 모든 픽의 단계별 픽 생성
        
        Returns:
            Dict[int, Dict[str, str]]: 각 픽 번호별 단계별 픽 정보
        """
        if len(self.results) < 15:
            if self.logger:
                self.logger.warning(f"데이터 부족: 현재 {len(self.results)}/15판, 모든 단계 픽 생성 불가")
            return {}
        
        # 픽 생성 가능 범위: 5번부터 18번까지
        min_pick = 5
        max_pick = 18
        
        # 각 단계별 픽 리스트 초기화
        self._initialize_stage_picks(max_pick)
        
        # 모든 픽 저장용 딕셔너리
        all_picks = {}
        
        # 픽 번호별로 5단계 알고리즘 적용하여 픽 생성
        for pick_number in range(min_pick, max_pick + 1):
            # 5단계 알고리즘 적용
            stage1, stage2, stage3, stage4, stage5 = self._apply_five_stage_algorithm(pick_number)
            
            # 각 단계별 픽 저장 (인덱스는 0부터 시작)
            idx = pick_number - 1
            self.stage1_picks[idx] = stage1
            self.stage2_picks[idx] = stage2
            self.stage3_picks[idx] = stage3
            self.stage4_picks[idx] = stage4
            self.stage5_picks[idx] = stage5
            
            # 결과 딕셔너리에 저장
            all_picks[pick_number] = {
                "1단계": stage1,
                "2단계": stage2,
                "3단계": stage3,
                "4단계": stage4,
                "5단계": stage5,
                "최종픽": stage5  # 5단계 픽이 최종 픽
            }
            
            if self.logger:
                self.logger.debug(f"{pick_number}번 픽 생성: "
                               f"1단계={stage1}, 2단계={stage2}, 3단계={stage3}, "
                               f"4단계={stage4}, 5단계={stage5}")
        
        return all_picks

    def _apply_five_stage_algorithm(self, pick_number: int) -> Tuple[str, str, str, str, str]:
        pos = pick_number - 1

        # ========= 1° =========
        pick1_idx = pos - 4
        pick2_idx = pos - 3
        pick4_idx = pos - 1

        if pick1_idx < 0 or pick2_idx < 0 or pick4_idx < 0 or pick4_idx >= len(self.results):
            default = 'N'
            return default, default, default, default, default

        pick1 = self.results[pick1_idx]
        pick2 = self.results[pick2_idx]
        pick4 = self.results[pick4_idx]
        stage1 = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4)

        # ========= 2° =========
        if pick_number < 6:
            stage2 = 'N'
        else:
            recent_results = self.results[pick_number - 5:pick_number - 1]
            recent_picks = self.stage1_picks[pick_number - 5:pick_number - 1]
            wins = sum(1 for r, p in zip(recent_results, recent_picks) if r == p)
            stage2 = stage1 if wins >= 2 else self.get_opposite_pick(stage1)

        # ========= 3° =========
        if pick_number < 6:
            stage3 = 'N'
        elif 6 <= pick_number <= 8:
            stage3 = stage2
        else:
            prev_idx = pick_number - 2
            result_at_prev = self.results[prev_idx] if prev_idx < len(self.results) else None
            prev_stage2 = self.stage2_picks[prev_idx] if prev_idx < len(self.stage2_picks) else None
            if result_at_prev is None or prev_stage2 is None:
                stage3 = stage2
            else:
                stage3 = stage2 if result_at_prev == prev_stage2 else self.get_opposite_pick(stage2)

        # ========= 4단계 =========
        if pick_number == 5:
            stage4 = 'N'
        elif 6 <= pick_number <= 10:
            stage4 = stage3
        else:
            prev_pick_idx = pick_number - 2  # 전판의 3단계 픽 (예: 11번 픽이면 9번 index)
            prev_result_idx = pick_number - 2  # 실제 결과 인덱스 (같음)

            if (
                prev_pick_idx < len(self.stage3_picks)
                and prev_result_idx < len(self.results)
            ):
                prev_pick = self.stage3_picks[prev_pick_idx]
                prev_result = self.results[prev_result_idx]

                if prev_pick == prev_result:
                    stage4 = stage3  # 성공 → 유지
                else:
                    stage4 = self.get_opposite_pick(stage3)  # 실패 → 반대픽
            else:
                stage4 = stage3  # 예외: 인덱스 벗어나면 유지

        # ========= 5단계 =========
        if pick_number == 5:
            stage5 = 'N'
        elif 6 <= pick_number <= 11:
            stage5 = stage1  # 1단계와 동일
        else:
            # 이전 4개의 4단계 픽과 결과 비교
            win_count = 0
            for offset in range(4):
                idx = pick_number - 2 - offset  # 1개 전부터 4개
                if (
                    0 <= idx < len(self.stage4_picks) and
                    idx < len(self.results)
                ):
                    pred = self.stage4_picks[idx]
                    actual = self.results[idx]
                    if pred == actual:
                        win_count += 1

            if win_count >= 2:
                stage5 = stage4  # 유지
            else:
                stage5 = self.get_opposite_pick(stage4)  # 반대


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
        
        # 요청받은 6개 픽 위치 (16, 17, 18번)
        pick_positions = [16, 17, 18]
        
        # 6개 픽에 해당하는 최종 값 추출
        picks = {}
        for pos in range(1, 7):
            pick_number = pick_positions[pos-1] if pos <= len(pick_positions) else pos  # 처음 3개는 16,17,18번, 나머지는 그대로
            
            if pick_number in all_stage_picks:
                final_pick = all_stage_picks[pick_number]["최종픽"]
                picks[pos] = final_pick
                if self.logger:
                    self.logger.info(f"픽 {pos}번 생성 완료: {final_pick} (위치 {pick_number}번)")
        
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
        self.stage4_picks
        
# import pandas as pd

# if __name__ == "__main__":
#     # 예시 결과 (15개)
#     # sample_results = ["","","","","","","","","","","","","","",""]
#     sample_results = ["B","B","P","B","B","P","B","B","P","B","P","B","B","P","P"]
#     # 시스템 인스턴스 생성
#     system = ChoicePickSystem()
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
