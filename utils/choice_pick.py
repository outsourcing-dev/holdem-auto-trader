import logging
# 로깅 설정을 변경하여 메모장(텍스트 파일)에만 저장되도록 함
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('choice_pick_log.txt')  # 텍스트 파일로 로그 저장
    ]
)
from typing import List, Tuple, Dict, Optional, Union

class ChoicePickSystem:
    """
    초이스 픽 시스템 - 15판 기준의 베팅 전략 구현
    """
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
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
        self.logger.info(f"다중 결과 추가: 총 {len(self.results)}/15판")
        self.logger.debug(f"현재 결과 리스트: {self.results}")

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
        self.logger.info("초이스 픽 생성 시작")
        self.logger.debug(f"현재 결과 데이터: {self.results}")
        
        if not self.has_sufficient_data():
            self.logger.warning(f"데이터 부족: 현재 {len(self.results)}/15판, 최소 15판 필요")
            return None
        
        all_picks = self._generate_six_picks()
        if not all_picks:
            self.logger.warning(f"6개 픽 생성 실패: 현재 데이터 길이 {len(self.results)}")
            return None
        
        self.logger.info(f"생성된 6개 픽: {all_picks}")
        
        normal_candidates = self._find_normal_betting_candidates(all_picks)
        reverse_candidates = self._find_reverse_betting_candidates(all_picks)
        
        self.logger.info(f"정배팅 후보 수: {len(normal_candidates)}, 역배팅 후보 수: {len(reverse_candidates)}")
        self.logger.debug(f"정배팅 후보들: {normal_candidates}")
        self.logger.debug(f"역배팅 후보들: {reverse_candidates}")
        
        if not normal_candidates and not reverse_candidates:
            self.logger.warning("정배팅/역배팅 조건을 만족하는 후보가 없음 (패스)")
            return None
        
        final_pick, direction, score = self._select_final_pick(normal_candidates, reverse_candidates)
        if final_pick:
            self.current_pick = final_pick
            self.betting_direction = direction
            self.logger.info(f"최종 초이스 픽: {final_pick} ({direction} 배팅), 점수: {score}")
            self.betting_attempts = 0
            self.martin_step = 0
            return final_pick
        else:
            self.logger.warning("적합한 초이스 픽을 찾을 수 없음 (패스) - 동점 또는 기타 조건 미충족")
            return None

    def _generate_six_picks(self) -> Dict[int, str]:
        """
        6개의 픽 생성 (시작 위치만 다른 동일한 알고리즘)
        
        Returns:
            Dict[int, str]: 각 시작 위치별 최종 픽 값 {1: 'P', 2: 'B', ...}
        """
        self.logger.info("6개 픽 생성 시작")
        
        if not self.has_sufficient_data():
            self.logger.warning(f"6개 픽 생성 실패: 데이터 부족 (현재 {len(self.results)}/15판)")
            return {}
        
        picks = {}
        for start_pos in range(1, 7):
            self.logger.debug(f"픽 {start_pos}번 생성 시작 (시작 위치: {start_pos})")
            final_pick = self._apply_five_stage_algorithm(start_pos)
            picks[start_pos] = final_pick
            self.logger.info(f"픽 {start_pos}번 생성 완료: {final_pick} (시작 위치 {start_pos})")
        
        p_count = sum(1 for p in picks.values() if p == 'P')
        b_count = sum(1 for p in picks.values() if p == 'B')
        self.logger.info(f"6개 픽 생성 완료: P={p_count}개, B={b_count}개")
        self.logger.debug(f"6개 픽 전체: {picks}")
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
            self.logger.debug(f"[픽 {start_pos}] 데이터 부족: 사용 데이터 {self.results[:pos+4]} 반환값: {self.results[0] if self.results else 'P'}")
            return self.results[0] if self.results else 'P'
        pick1 = self.results[pos]
        pick2 = self.results[pos + 1]
        pick4 = self.results[pos + 3]
        stage1_pick = pick4 if pick1 == pick2 else self.get_opposite_pick(pick4)
        self.logger.debug(f"[픽 {start_pos} - 1단계] pick1={pick1}, pick2={pick2}, pick4={pick4} -> stage1_pick={stage1_pick}")
        
        # 2단계: 1단계 중 최근 4판의 승이 2개 이상이면 유지, 아니면 반대
        recent_four = self.results[pos:pos+4]
        wins = sum(1 for r in recent_four if r == stage1_pick)
        stage2_pick = stage1_pick if wins >= 2 else self.get_opposite_pick(stage1_pick)
        self.logger.debug(f"[픽 {start_pos} - 2단계] 최근4={recent_four}, wins={wins} -> stage2_pick={stage2_pick}")
        
        # 3단계: 5번부터 8번까지는 2단계 결과 그대로 유지, 이후는 2단계 픽이 실패하면 반대로, 성공하면 유지
        eighth_pos = pos + 7
        if len(self.results) <= eighth_pos:
            stage3_pick = stage2_pick
            self.logger.debug(f"[픽 {start_pos} - 3단계] 8번 인덱스 미존재 -> stage3_pick={stage3_pick}")
        else:
            eighth_result = self.results[eighth_pos]
            if eighth_result != stage2_pick:  # 2단계 픽 실패
                if len(self.results) > eighth_pos + 1:
                    ninth_result = self.results[eighth_pos + 1]
                    stage3_pick = self.get_opposite_pick(stage2_pick) if ninth_result == self.get_opposite_pick(stage2_pick) else stage2_pick
                    self.logger.debug(f"[픽 {start_pos} - 3단계] 8번={eighth_result}, 9번={ninth_result} -> stage3_pick={stage3_pick}")
                else:
                    stage3_pick = stage2_pick
                    self.logger.debug(f"[픽 {start_pos} - 3단계] 8번 실패, 9번 미존재 -> stage3_pick={stage3_pick}")
            else:
                stage3_pick = stage2_pick
                self.logger.debug(f"[픽 {start_pos} - 3단계] 8번 일치 -> stage3_pick={stage3_pick}")
        
        # 4단계: 5번부터 10번까지는 3단계 결과 그대로 유지, 이후는 3단계와 동일한 방식으로 반응
        tenth_pos = pos + 9
        if len(self.results) <= tenth_pos:
            stage4_pick = stage3_pick
            self.logger.debug(f"[픽 {start_pos} - 4단계] 10번 인덱스 미존재 -> stage4_pick={stage4_pick}")
        else:
            tenth_result = self.results[tenth_pos]
            if tenth_result != stage3_pick:  # 3단계 픽 실패
                if len(self.results) > tenth_pos + 1:
                    eleventh_result = self.results[tenth_pos + 1]
                    stage4_pick = self.get_opposite_pick(stage3_pick) if eleventh_result == self.get_opposite_pick(stage3_pick) else stage3_pick
                    self.logger.debug(f"[픽 {start_pos} - 4단계] 10번={tenth_result}, 11번={eleventh_result} -> stage4_pick={stage4_pick}")
                else:
                    stage4_pick = stage3_pick
                    self.logger.debug(f"[픽 {start_pos} - 4단계] 10번 실패, 11번 미존재 -> stage4_pick={stage4_pick}")
            else:
                stage4_pick = stage3_pick
                self.logger.debug(f"[픽 {start_pos} - 4단계] 10번 일치 -> stage4_pick={stage4_pick}")
        
        # 5단계: 5~11번은 1단계 유지, 이후 4판 중 승 2개 이상이면 유지, 아니면 반대
        start_idx = pos + 10
        end_idx = pos + 14
        if len(self.results) <= start_idx:
            stage5_pick = stage4_pick
            self.logger.debug(f"[픽 {start_pos} - 5단계] 11번 미존재 -> stage5_pick={stage5_pick}")
        else:
            end_idx = min(end_idx, len(self.results))
            recent_results = self.results[start_idx:end_idx]
            wins = sum(1 for r in recent_results if r == stage4_pick)
            stage5_pick = stage4_pick if wins >= 2 else self.get_opposite_pick(stage4_pick)
            self.logger.debug(f"[픽 {start_pos} - 5단계] 결과[{start_idx}:{end_idx}]={recent_results}, wins={wins} -> stage5_pick={stage5_pick}")
        
        return stage5_pick


    def _find_normal_betting_candidates(self, all_picks: Dict[int, str]) -> Dict[str, Dict[str, any]]:
        """
        정배팅 후보 및 점수 계산
        설명서 기준: 최근 2판 결과가 "승 → 패"이며, 패의 3연패 이상이 없어야 함
        점수: 승 - 패
        """
        candidates = {}
        if len(self.results) < 2:
            self.logger.warning("정배팅 후보 검색: 데이터 부족 (최소 2판 필요)")
            return candidates
            
        self.logger.info(f"정배팅 후보 검색 시작 (데이터 {len(self.results)}판)")
        
        for pos, pick in all_picks.items():
            self.logger.debug(f"정배팅 후보 분석 - 픽 {pick} (시작 위치 {pos})")
            
            # 최근 2판 결과가 "승 → 패"인지 확인
            if len(self.results) >= 2:
                recent_win_lose = (self.results[-2] == pick and self.results[-1] != pick)
                self.logger.debug(f"  최근 2판 [승→패] 조건: {self.results[-2]} → {self.results[-1]}, " +
                                f"기대값 [{pick} → not {pick}], 조건만족={recent_win_lose}")
                
                if not recent_win_lose:
                    self.logger.debug(f"  [승→패] 조건을 만족하지 않음 - 픽 {pick} (시작 위치 {pos}) 제외")
                    continue
                
                # 패의 3연패 이상이 없는지 확인
                has_long_losing_streak = False
                current_losing_streak = 0
                losing_streaks = []
                
                for i, r in enumerate(self.results):
                    if r != pick:  # 패배
                        current_losing_streak += 1
                        if current_losing_streak >= 3:  # 3연패 이상 발견
                            has_long_losing_streak = True
                            losing_streaks.append((i-current_losing_streak+1, i, current_losing_streak))
                    else:  # 승리
                        if current_losing_streak > 0:
                            losing_streaks.append((i-current_losing_streak, i-1, current_losing_streak))
                        current_losing_streak = 0
                
                # 마지막 구간에 패배 연속이 있다면 추가
                if current_losing_streak > 0:
                    losing_streaks.append((len(self.results)-current_losing_streak, len(self.results)-1, current_losing_streak))
                
                no_long_losing_streak = not has_long_losing_streak
                self.logger.debug(f"  패의 3연패 이상 조건: 없어야 함, 실제={losing_streaks}, 조건만족={no_long_losing_streak}")
                
                if not no_long_losing_streak:
                    self.logger.debug(f"  패의 3연패 이상 발견 - 픽 {pick} (시작 위치 {pos}) 제외")
                    continue
                
                # 모든 조건이 만족되면 점수 계산
                wins = sum(1 for r in self.results if r == pick)
                losses = len(self.results) - wins
                score = wins - losses
                key = f"{pick}-{pos}"
                candidates[key] = {'pick': pick, 'pos': pos, 'score': score}
                self.logger.info(f"정배팅 후보 확정: 픽 {pick} (시작 위치 {pos}), 승={wins}, 패={losses}, 점수={score}")
            
        self.logger.info(f"정배팅 후보 검색 완료: {len(candidates)}개 발견")
        return candidates

    def _find_reverse_betting_candidates(self, all_picks: Dict[int, str]) -> Dict[str, Dict[str, any]]:
        """
        역배팅 후보 및 점수 계산
        설명서 기준: 최근 2판 결과가 "패 → 승"이며, 승의 3연승 이상이 없어야 함
        점수: 패 - 승
        """
        candidates = {}
        if len(self.results) < 2:
            self.logger.warning("역배팅 후보 검색: 데이터 부족 (최소 2판 필요)")
            return candidates
            
        self.logger.info(f"역배팅 후보 검색 시작 (데이터 {len(self.results)}판)")
        
        for pos, pick in all_picks.items():
            opposite_pick = self.get_opposite_pick(pick)
            self.logger.debug(f"역배팅 후보 분석 - 픽 {opposite_pick} (시작 위치 {pos}, 원픽 {pick}의 반대)")
            
            if len(self.results) >= 2:
                # 최근 2판 결과가 "패 → 승"인지 확인
                recent_lose_win = (self.results[-2] != opposite_pick and self.results[-1] == opposite_pick)
                self.logger.debug(f"  최근 2판 [패→승] 조건: {self.results[-2]} → {self.results[-1]}, " +
                                f"기대값 [not {opposite_pick} → {opposite_pick}], 조건만족={recent_lose_win}")
                
                if not recent_lose_win:
                    self.logger.debug(f"  [패→승] 조건을 만족하지 않음 - 픽 {opposite_pick} (시작 위치 {pos}) 제외")
                    continue
                
                # 승의 3연승 이상이 없는지 확인
                has_long_winning_streak = False
                current_winning_streak = 0
                winning_streaks = []
                
                for i, r in enumerate(self.results):
                    if r == opposite_pick:  # 승리
                        current_winning_streak += 1
                        if current_winning_streak >= 3:  # 3연승 이상 발견
                            has_long_winning_streak = True
                            winning_streaks.append((i-current_winning_streak+1, i, current_winning_streak))
                    else:  # 패배
                        if current_winning_streak > 0:
                            winning_streaks.append((i-current_winning_streak, i-1, current_winning_streak))
                        current_winning_streak = 0
                
                # 마지막 구간에 승리 연속이 있다면 추가
                if current_winning_streak > 0:
                    winning_streaks.append((len(self.results)-current_winning_streak, len(self.results)-1, current_winning_streak))
                
                no_long_winning_streak = not has_long_winning_streak
                self.logger.debug(f"  승의 3연승 이상 조건: 없어야 함, 실제={winning_streaks}, 조건만족={no_long_winning_streak}")
                
                if not no_long_winning_streak:
                    self.logger.debug(f"  승의 3연승 이상 발견 - 픽 {opposite_pick} (시작 위치 {pos}) 제외")
                    continue
                
                # 모든 조건이 만족되면 점수 계산
                wins = sum(1 for r in self.results if r == opposite_pick)
                losses = len(self.results) - wins
                score = losses - wins
                key = f"{opposite_pick}-{pos}"
                candidates[key] = {'pick': opposite_pick, 'pos': pos, 'score': score}
                self.logger.info(f"역배팅 후보 확정: 픽 {opposite_pick} (시작 위치 {pos}), 승={wins}, 패={losses}, 점수={score}")
        
        self.logger.info(f"역배팅 후보 검색 완료: {len(candidates)}개 발견")
        return candidates

    def _select_final_pick(self, normal_candidates, reverse_candidates):
        """
        최종 초이스 픽 선택
        설명서 기준: 
        - 정배팅/역배팅 후보 중 점수가 가장 높은 픽 선택
        - 점수가 같은 경우, 승패 차이가 큰 픽 선택
        - 그래도 같으면 패스
        """
        self.logger.info("최종 초이스 픽 선택 시작")
        
        best_pick = None
        best_direction = ""
        best_score = float('-inf')
        all_candidates = {}
        
        # 정배팅 후보 처리
        for key, candidate in normal_candidates.items():
            score = candidate['score']
            pick = candidate['pick']
            diff = self._calculate_win_loss_diff(pick)
            all_candidates[key] = {'pick': pick, 'direction': 'normal', 'score': score, 'diff': diff}
            self.logger.debug(f"정배팅 후보 처리: 키={key}, 픽={pick}, 점수={score}, 승패차={diff}")
        
        # 역배팅 후보 처리
        for key, candidate in reverse_candidates.items():
            score = candidate['score']
            pick = candidate['pick']
            diff = self._calculate_win_loss_diff(pick)
            all_candidates[key] = {'pick': pick, 'direction': 'reverse', 'score': score, 'diff': diff}
            self.logger.debug(f"역배팅 후보 처리: 키={key}, 픽={pick}, 점수={score}, 승패차={diff}")
        
        self.logger.debug(f"최종 후보 전체 ({len(all_candidates)}개): {all_candidates}")
        
        # 가장 높은 점수의 후보 찾기
        for key, candidate in all_candidates.items():
            score = candidate['score']
            if score > best_score:
                best_pick = candidate['pick']
                best_direction = candidate['direction']
                best_score = score
                self.logger.debug(f"새로운 최고 점수 발견: 픽={best_pick}, 방향={best_direction}, 점수={best_score}")
        
        if best_pick is not None:
            self.logger.info(f"최고 점수 후보: 픽={best_pick}, 방향={best_direction}, 점수={best_score}")
            
            # 동일 점수 후보 확인
            same_score_candidates = [c for c in all_candidates.values() if c['score'] == best_score]
            self.logger.debug(f"동일 최고 점수 후보들 ({len(same_score_candidates)}개): {same_score_candidates}")
            
            if len(same_score_candidates) > 1:
                self.logger.info(f"동일 점수({best_score}) 후보 발견: {len(same_score_candidates)}개")
                
                # 승패 차이로 정렬
                same_score_candidates.sort(key=lambda x: abs(x['diff']), reverse=True)
                self.logger.debug(f"승패 차이 기준 정렬 후: {[(c['pick'], c['direction'], abs(c['diff'])) for c in same_score_candidates]}")
                
                # 동일 승패 차이 확인
                if len(same_score_candidates) >= 2 and abs(same_score_candidates[0]['diff']) == abs(same_score_candidates[1]['diff']):
                    self.logger.warning(f"동일 점수({best_score}) 및 동일 승패 차이({abs(same_score_candidates[0]['diff'])}) 픽 발견: " +
                                      f"{[c['pick'] for c in same_score_candidates[:2]]} - 패스")
                    return None, "", 0
                
                best_pick = same_score_candidates[0]['pick']
                best_direction = same_score_candidates[0]['direction']
                best_diff = abs(same_score_candidates[0]['diff'])
                self.logger.info(f"동일 점수 후보 중 승패 차이({best_diff})가 가장 큰 픽 {best_pick} 선택")
            
            self.logger.info(f"최종 초이스 픽 선택 완료: {best_pick} ({best_direction} 배팅), 점수: {best_score}")
            return best_pick, best_direction, best_score
        else:
            self.logger.warning("적합한 후보가 없음: 모든 후보의 점수가 음수이거나 후보가 없음")
            return None, "", 0

    def _calculate_win_loss_diff(self, pick: str) -> int:
        """픽에 대한 승패 차이 계산"""
        wins = sum(1 for r in self.results if r == pick)
        losses = len(self.results) - wins
        diff = wins - losses
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
            self.logger.info(f"베팅 성공! 시도: {self.betting_attempts}번째, 마틴 단계: {self.martin_step+1}")
            if reset_after_win:
                self.consecutive_failures = 0
                self.martin_step = 0
                self.last_win_count = 0
                self.logger.info("베팅 성공으로 마틴 단계와 실패 카운터 초기화")
        else:
            self.logger.info(f"베팅 실패. 시도: {self.betting_attempts}번째, 마틴 단계: {self.martin_step+1}")
            if self.martin_step < 2:
                self.martin_step += 1
                self.logger.info(f"마틴 단계 증가: {self.martin_step+1}단계")
            else:
                self.consecutive_failures += 1
                self.martin_step = 0
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
            self.logger.info("3마틴 모두 실패로 방 이동 필요")
            return True
            
        if len(self.pick_results) >= 2 and not any(self.pick_results[-2:]):
            self.logger.info("초이스 픽 2회 연속 실패로 방 이동 필요")
            return True
            
        if self.betting_attempts == 0 and self.martin_step == 0 and self.last_win_count >= 57:
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
        self.logger.info("초이스 픽 시스템 전체 초기화 완료")

    def set_martin_amounts(self, amounts: List[int]) -> None:
        """마틴 금액 설정"""
        if len(amounts) >= 3:
            self.martin_amounts = amounts[:3]
            self.logger.info(f"마틴 금액 설정: {self.martin_amounts}")
        else:
            self.logger.warning(f"마틴 금액 설정 실패: 최소 3단계 필요 (현재 {len(amounts)}단계)")