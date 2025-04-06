import logging
import os
import sys
from typing import List, Optional, Dict
from datetime import datetime

# 로그 파일 경로 결정
if getattr(sys, 'frozen', False):
    # PyInstaller로 패키징된 경우
    base_dir = os.path.dirname(sys.executable)
    log_path = os.path.join(base_dir, 'choice_pick_log.txt')
else:
    # 일반 Python으로 실행된 경우
    log_path = 'choice_pick_log.txt'

# 간단한 로깅 함수 (파일에 직접 기록)
def write_log(message, level="INFO"):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} - {level} - {message}\n")
    except Exception as e:
        print(f"로그 기록 실패: {e}")

# 시작 로그 기록
write_log(f"ChoicePickSystem 로그 시작 - 파일 경로: {log_path}")

class ChoicePickSystem:
    """
    초이스 픽 시스템 - 15판 기준의 베팅 전략 구현
    """
    def __init__(self, logger=None):
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
        
        # 초기화 로그
        write_log("ChoicePickSystem 인스턴스 생성")

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
            
        log_msg = f"결과 추가: {result} (현재 {len(self.results)}/15판)"
        write_log(log_msg)
        write_log(f"현재 결과 리스트: {self.results}", "DEBUG")
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
        write_log(f"다중 결과 추가: 총 {len(self.results)}/15판")
        write_log(f"현재 결과 리스트: {self.results}", "DEBUG")

    def has_sufficient_data(self) -> bool:
        """15판 데이터가 모두 있는지 확인"""
        return len(self.results) >= 15

    def get_opposite_pick(self, pick: str) -> str:
        """반대 픽 반환"""
        return 'B' if pick == 'P' else 'P'

    def generate_choice_pick(self) -> Optional[str]:
        """
        6개 픽 생성 및 5단계 로직을 통해 초이스 픽 생성
        
        Returns:
            초이스 픽 ('P' 또는 'B') 또는 None (데이터 부족 시)
        """
        write_log("초이스 픽 생성 시작")
        write_log(f"현재 결과 데이터: {self.results}", "DEBUG")
        
        if not self.has_sufficient_data():
            write_log(f"데이터 부족: 현재 {len(self.results)}/15판, 최소 15판 필요", "WARNING")
            return None
        
        all_picks = self._generate_six_picks()
        if not all_picks:
            write_log(f"6개 픽 생성 실패: 현재 데이터 길이 {len(self.results)}", "WARNING")
            return None
        
        write_log(f"생성된 6개 픽: {all_picks}")
        
        normal_candidates = self._find_normal_betting_candidates(all_picks)
        reverse_candidates = self._find_reverse_betting_candidates(all_picks)
        
        write_log(f"정배팅 후보 수: {len(normal_candidates)}, 역배팅 후보 수: {len(reverse_candidates)}")
        write_log(f"정배팅 후보들: {normal_candidates}", "DEBUG")
        write_log(f"역배팅 후보들: {reverse_candidates}", "DEBUG")
        
        if not normal_candidates and not reverse_candidates:
            write_log("정배팅/역배팅 조건을 만족하는 후보가 없음 (패스)", "WARNING")
            return None
        
        final_pick, direction, score = self._select_final_pick(normal_candidates, reverse_candidates)
        if final_pick:
            self.current_pick = final_pick
            self.betting_direction = direction
            write_log(f"최종 초이스 픽: {final_pick} ({direction} 배팅), 점수: {score}")
            self.betting_attempts = 0
            self.martin_step = 0
            return final_pick
        else:
            write_log("적합한 초이스 픽을 찾을 수 없음 (패스) - 동점 또는 기타 조건 미충족", "WARNING")
            return None

    def _generate_six_picks(self) -> Dict[int, str]:
        """
        6개의 픽 생성 (시작 위치만 다른 동일한 알고리즘)
        
        Returns:
            Dict[int, str]: 각 시작 위치별 최종 픽 값 {1: 'P', 2: 'B', ...}
        """
        write_log("6개 픽 생성 시작")
        
        if not self.has_sufficient_data():
            write_log(f"6개 픽 생성 실패: 데이터 부족 (현재 {len(self.results)}/15판)", "WARNING")
            return {}
        
        picks = {}
        for start_pos in range(1, 7):
            write_log(f"픽 {start_pos}번 생성 시작 (시작 위치: {start_pos})", "DEBUG")
            final_pick = self._apply_five_stage_algorithm(start_pos)
            picks[start_pos] = final_pick
            write_log(f"픽 {start_pos}번 생성 완료: {final_pick} (시작 위치 {start_pos})")
        
        p_count = sum(1 for p in picks.values() if p == 'P')
        b_count = sum(1 for p in picks.values() if p == 'B')
        write_log(f"6개 픽 생성 완료: P={p_count}개, B={b_count}개")
        write_log(f"6개 픽 전체: {picks}", "DEBUG")
        return picks

    def _apply_five_stage_algorithm(self, start_pos: int) -> str:
        """
        5단계 알고리즘을 적용하여 픽 생성
        
        Args:
            start_pos: 시작 위치 (1~6)
            
        Returns:
            str: 최종 픽 ('P' 또는 'B')
        """
        pos = start_pos - 1
        if len(self.results) <= pos + 3:
            write_log(f"[픽 {start_pos}] 데이터 부족: 사용 데이터 {self.results[:pos+4]} 반환값: {self.results[0] if self.results else 'P'}", "DEBUG")
            return self.results[0] if self.results else 'P'
            
        pick1 = self.results[pos]
        pick2 = self.results[pos + 1]
        pick4 = self.results[pos + 3]
        stage1_pick = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4)
        write_log(f"[픽 {start_pos} - 1단계] pick1={pick1}, pick2={pick2}, pick4={pick4} -> stage1_pick={stage1_pick}", "DEBUG")
        
        # 2단계: 1단계 중 최근 4판의 승이 2개 이상이면 유지, 아니면 반대
        recent_four = self.results[pos:pos+4]
        wins = sum(1 for r in recent_four if r == stage1_pick)
        stage2_pick = stage1_pick if wins >= 2 else self.get_opposite_pick(stage1_pick)
        write_log(f"[픽 {start_pos} - 2단계] 최근4={recent_four}, wins={wins} -> stage2_pick={stage2_pick}", "DEBUG")
        
        # 3단계: 수정된 로직 - 단순히 8번 결과와 2단계 픽을 비교하여 결정
        eighth_pos = pos + 7
        if len(self.results) <= eighth_pos:
            stage3_pick = stage2_pick
            write_log(f"[픽 {start_pos} - 3단계] 8번 인덱스 미존재 -> stage3_pick={stage3_pick}", "DEBUG")
        else:
            eighth_result = self.results[eighth_pos]
            # 단순화된 로직: 2단계 픽이 성공하면 유지, 실패하면 반대
            if eighth_result == stage2_pick:  # 2단계 픽 성공
                stage3_pick = stage2_pick
                write_log(f"[픽 {start_pos} - 3단계] 8번 일치(성공) -> 동일 픽 유지: stage3_pick={stage3_pick}", "DEBUG")
            else:  # 2단계 픽 실패
                stage3_pick = self.get_opposite_pick(stage2_pick)
                write_log(f"[픽 {start_pos} - 3단계] 8번 불일치(실패) -> 반대 픽으로 전환: stage3_pick={stage3_pick}", "DEBUG")
        
        # 4단계: 수정된 로직 - 단순히 10번 결과와 3단계 픽을 비교하여 결정
        tenth_pos = pos + 9
        if len(self.results) <= tenth_pos:
            stage4_pick = stage3_pick
            write_log(f"[픽 {start_pos} - 4단계] 10번 인덱스 미존재 -> stage4_pick={stage4_pick}", "DEBUG")
        else:
            tenth_result = self.results[tenth_pos]
            # 단순화된 로직: 3단계 픽이 성공하면 유지, 실패하면 반대
            if tenth_result == stage3_pick:  # 3단계 픽 성공
                stage4_pick = stage3_pick
                write_log(f"[픽 {start_pos} - 4단계] 10번 일치(성공) -> 동일 픽 유지: stage4_pick={stage4_pick}", "DEBUG")
            else:  # 3단계 픽 실패
                stage4_pick = self.get_opposite_pick(stage3_pick)
                write_log(f"[픽 {start_pos} - 4단계] 10번 불일치(실패) -> 반대 픽으로 전환: stage4_pick={stage4_pick}", "DEBUG")
        
        # 5단계: 수정된 로직 - 시작 인덱스를 사용해 4단계 픽과 비교
        # 12번 결과부터 분석 (11번 이후 모든 결과)
        twelfth_pos = pos + 11
        if len(self.results) <= twelfth_pos:
            stage5_pick = stage4_pick
            write_log(f"[픽 {start_pos} - 5단계] 12번 인덱스 미존재 -> stage5_pick={stage5_pick}", "DEBUG")
        else:
            # 기존의 승률 기반 로직 대신 가장 최근 결과(11번)와 4단계 픽 비교
            eleventh_result = self.results[twelfth_pos-1]  # 11번 결과
            if eleventh_result == stage4_pick:  # 4단계 픽 성공
                stage5_pick = stage4_pick
                write_log(f"[픽 {start_pos} - 5단계] 11번 일치(성공) -> 동일 픽 유지: stage5_pick={stage5_pick}", "DEBUG")
            else:  # 4단계 픽 실패
                stage5_pick = self.get_opposite_pick(stage4_pick)
                write_log(f"[픽 {start_pos} - 5단계] 11번 불일치(실패) -> 반대 픽으로 전환: stage5_pick={stage5_pick}", "DEBUG")
        
        return stage5_pick

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

    def _find_normal_betting_candidates(self, all_picks: Dict[int, str]) -> Dict[str, Dict[str, any]]:
        """
        정배팅 후보 및 점수 계산
        수정된 기준: 
        1. 해당 픽 기준 3연패가 없어야 함
        2. 마지막 판이 승 또는 패일 것 (Tie만 아니면 OK)
        점수: 승 - 패
        """
        candidates = {}
        if not self.results:
            write_log("정배팅 후보 검색: 데이터 없음", "WARNING")
            return candidates
            
        write_log(f"정배팅 후보 검색 시작 (데이터 {len(self.results)}판)")
        
        for pos, pick in all_picks.items():
            write_log(f"정배팅 후보 분석 - 픽 {pick} (시작 위치 {pos})", "DEBUG")
            
            # 마지막 판이 존재하는지 확인 (Tie가 아니어야 함)
            # 이 조건은 사실 항상 True임 (add_result에서 P, B만 필터링하고 있음)
            if len(self.results) > 0:
                # 해당 픽 기준 3연패가 없는지 확인
                losing_streaks = self._find_streaks(self.results, lambda r: r != pick, 3)
                has_long_losing_streak = len(losing_streaks) > 0
                
                if has_long_losing_streak:
                    write_log(f"  패의 3연패 발견 - 픽 {pick} (시작 위치 {pos}) 제외", "DEBUG")
                    write_log(f"  패 연속 구간: {losing_streaks}", "DEBUG")
                    continue
                
                # 모든 조건이 만족되면 점수 계산
                wins = sum(1 for r in self.results if r == pick)
                losses = len(self.results) - wins
                score = wins - losses
                key = f"{pick}-{pos}"
                candidates[key] = {'pick': pick, 'pos': pos, 'score': score, 'direction': 'normal'}
                write_log(f"정배팅 후보 확정: 픽 {pick} (시작 위치 {pos}), 승={wins}, 패={losses}, 점수={score}")
        
        write_log(f"정배팅 후보 검색 완료: {len(candidates)}개 발견")
        return candidates

    def _find_reverse_betting_candidates(self, all_picks: Dict[int, str]) -> Dict[str, Dict[str, any]]:
        """
        역배팅 후보 및 점수 계산
        수정된 기준: 
        1. 해당 픽 기준 3연승이 없어야 함 
        2. 마지막 판이 패 또는 승일 것 (Tie만 아니면 OK)
        점수: 패 - 승
        """
        candidates = {}
        if not self.results:
            write_log("역배팅 후보 검색: 데이터 없음", "WARNING")
            return candidates
            
        write_log(f"역배팅 후보 검색 시작 (데이터 {len(self.results)}판)")
        
        for pos, pick in all_picks.items():
            opposite_pick = self.get_opposite_pick(pick)
            write_log(f"역배팅 후보 분석 - 픽 {opposite_pick} (시작 위치 {pos}, 원픽 {pick}의 반대)", "DEBUG")
            
            # 마지막 판이 존재하는지 확인 (Tie가 아니어야 함)
            # 이 조건은 사실 항상 True임 (add_result에서 P, B만 필터링하고 있음)
            if len(self.results) > 0:
                # 해당 픽 기준 3연승이 없는지 확인
                winning_streaks = self._find_streaks(self.results, lambda r: r == opposite_pick, 3)
                has_long_winning_streak = len(winning_streaks) > 0
                
                if has_long_winning_streak:
                    write_log(f"  승의 3연승 발견 - 픽 {opposite_pick} (시작 위치 {pos}) 제외", "DEBUG")
                    write_log(f"  승 연속 구간: {winning_streaks}", "DEBUG")
                    continue
                
                # 모든 조건이 만족되면 점수 계산
                wins = sum(1 for r in self.results if r == opposite_pick)
                losses = len(self.results) - wins
                score = losses - wins
                key = f"{opposite_pick}-{pos}"
                candidates[key] = {'pick': opposite_pick, 'pos': pos, 'score': score, 'direction': 'reverse'}
                write_log(f"역배팅 후보 확정: 픽 {opposite_pick} (시작 위치 {pos}), 승={wins}, 패={losses}, 점수={score}")
        
        write_log(f"역배팅 후보 검색 완료: {len(candidates)}개 발견")
        return candidates

    def _select_final_pick(self, normal_candidates, reverse_candidates):
        """
        최종 초이스 픽 선택
        수정된 기준:
        1. 정배팅/역배팅 후보 중 점수가 가장 높은 픽 선택
        2. 동점 시 처리 규칙:
           - 동점인 후보들의 픽이 모두 같으면 -> 해당 픽 선택
           - 동점인 후보들의 픽이 다르면 -> PASS
        """
        write_log("최종 초이스 픽 선택 시작")
        
        # 모든 후보 합치기
        all_candidates = {}
        all_candidates.update(normal_candidates)
        all_candidates.update(reverse_candidates)
        
        if not all_candidates:
            write_log("적합한 후보가 없음: 모든 조건을 만족하는 후보가 없음", "WARNING")
            return None, "", 0
        
        # 모든 후보의 점수 계산하여 가장 높은 점수 찾기
        best_score = max(candidate['score'] for candidate in all_candidates.values())
        write_log(f"최고 점수: {best_score}")
        
        # 가장 높은 점수를 가진 후보들만 추출
        best_candidates = {key: candidate for key, candidate in all_candidates.items() 
                          if candidate['score'] == best_score}
        
        write_log(f"최고 점수({best_score}) 후보 {len(best_candidates)}개: {list(best_candidates.keys())}")
        
        # 후보들의 픽 추출 및 중복 제거
        unique_picks = set(candidate['pick'] for candidate in best_candidates.values())
        write_log(f"최고 점수 후보들의 유니크 픽: {unique_picks}")
        
        if len(unique_picks) == 1:
            # 모든 최고 점수 후보가 같은 픽을 가진 경우
            sample_candidate = next(iter(best_candidates.values()))
            best_pick = sample_candidate['pick']
            best_direction = sample_candidate['direction']
            write_log(f"최종 초이스 픽 선택 완료: {best_pick} ({best_direction} 배팅), 점수: {best_score}")
            return best_pick, best_direction, best_score
        else:
            # 최고 점수 후보들이 서로 다른 픽을 가진 경우
            write_log(f"최고 점수({best_score}) 후보들이 서로 다른 픽을 가짐 - PASS", "WARNING")
            return None, "", 0

    def _calculate_win_loss_diff(self, pick: str) -> int:
        """픽에 대한 승패 차이 계산"""
        wins = sum(1 for r in self.results if r == pick)
        losses = len(self.results) - wins
        diff = wins - losses
        write_log(f"승패 차이 계산: pick={pick}, wins={wins}, losses={losses}, diff={diff}", "DEBUG")
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
            write_log(f"베팅 성공! 시도: {self.betting_attempts}번째, 마틴 단계: {self.martin_step+1}")
            if reset_after_win:
                self.consecutive_failures = 0
                self.martin_step = 0
                self.last_win_count = 0
                write_log("베팅 성공으로 마틴 단계와 실패 카운터 초기화")
        else:
            write_log(f"베팅 실패. 시도: {self.betting_attempts}번째, 마틴 단계: {self.martin_step+1}")
            if self.martin_step < 2:
                self.martin_step += 1
                write_log(f"마틴 단계 증가: {self.martin_step+1}단계")
            else:
                self.consecutive_failures += 1
                self.martin_step = 0
                write_log(f"3마틴 모두 실패! 연속 실패: {self.consecutive_failures}회", "WARNING")
    
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
            write_log("3마틴 모두 실패로 방 이동 필요")
            return True
            
        if len(self.pick_results) >= 2 and not any(self.pick_results[-2:]):
            write_log("초이스 픽 2회 연속 실패로 방 이동 필요")
            return True
            
        if self.betting_attempts == 0 and self.martin_step == 0 and self.last_win_count >= 57:
            write_log(f"현재 게임 판수가 57판 이상이고 배팅 중이 아님 → 방 이동 필요")
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
        write_log(f"방 이동 후 초기화: 연속실패({prev_failures}→{self.consecutive_failures}), "
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
        write_log("초이스 픽 시스템 전체 초기화 완료")

    def set_martin_amounts(self, amounts: List[int]) -> None:
        """마틴 금액 설정"""
        if len(amounts) >= 3:
            self.martin_amounts = amounts[:3]
            write_log(f"마틴 금액 설정: {self.martin_amounts}")
        else:
            write_log(f"마틴 금액 설정 실패: 최소 3단계 필요 (현재 {len(amounts)}단계)", "WARNING")