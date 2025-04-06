# utils/choice_pick.py
"""
초이스 픽 시스템 구현
- 15판의 결과를 바탕으로 초이스 픽 도출
- 5단계 픽 로직 적용
- 정배팅/역배팅 결정 및 승패 점수 계산
"""
import logging
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
        self.stage_picks: Dict[int, str] = {}  # 각 단계별 픽 결과
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
        # 15판 이상이면 가장 오래된 결과 제거
        if len(self.results) > 15:
            self.results.pop(0)
            
        self.logger.info(f"결과 추가: {result} (현재 {len(self.results)}/15판)")
        
        # 결과가 추가될 때마다 마지막 승리 이후 판 수 카운터 증가
        self.last_win_count += 1
    
    def add_multiple_results(self, results: List[str]) -> None:
        """
        여러 결과 한번에 추가 (TIE 제외)
        
        Args:
            results: 결과 목록 ['P', 'B', 'T', ...]
        """
        filtered_results = [r for r in results if r in ['P', 'B']]
        
        # 최근 15판만 유지
        if len(filtered_results) > 15:
            filtered_results = filtered_results[-15:]
            
        self.results = filtered_results
        self.logger.info(f"다중 결과 추가: 총 {len(self.results)}/15판")
    
    def has_sufficient_data(self) -> bool:
        """15판 데이터가 모두 있는지 확인"""
        return len(self.results) >= 15
    
    def get_opposite_pick(self, pick: str) -> str:
        """반대 픽 반환"""
        return 'B' if pick == 'P' else 'P'
    
    def generate_choice_pick(self) -> Optional[str]:
        """
        5단계 로직을 통해 초이스 픽 생성
        
        Returns:
            초이스 픽 ('P' 또는 'B') 또는 None (데이터 부족 시)
        """
        if not self.has_sufficient_data():
            self.logger.warning(f"데이터 부족: 현재 {len(self.results)}/15판")
            return None
            
        # 스테이지별 픽 계산 및 저장
        stage1_pick = self._calculate_stage1_pick()
        stage2_pick = self._calculate_stage2_pick(stage1_pick)
        stage3_pick = self._calculate_stage3_pick(stage2_pick)
        stage4_pick = self._calculate_stage4_pick(stage3_pick)
        stage5_pick = self._calculate_stage5_pick(stage4_pick)
        
        self.stage_picks = {
            1: stage1_pick,
            2: stage2_pick,
            3: stage3_pick,
            4: stage4_pick,
            5: stage5_pick
        }
        
        # 정배팅/역배팅 후보 및 점수 계산
        normal_candidates = self._find_normal_betting_candidates()
        reverse_candidates = self._find_reverse_betting_candidates()
        
        # 최종 픽과 방향 결정
        final_pick, direction, score = self._select_final_pick(normal_candidates, reverse_candidates)
        
        if final_pick:
            self.current_pick = final_pick
            self.betting_direction = direction
            self.logger.info(f"최종 초이스 픽: {final_pick} ({direction} 배팅), 점수: {score}")
            
            # 새 픽이 생성되면 배팅 시도 횟수와 마틴 단계 초기화
            self.betting_attempts = 0
            self.martin_step = 0
            
            return final_pick
        else:
            self.logger.warning("적합한 초이스 픽을 찾을 수 없음 (패스)")
            return None
    
    def _calculate_stage1_pick(self) -> str:
        """
        1단계 픽 계산:
        - 1, 2번 픽 비교
        - 같으면 4번 픽과 동일, 다르면 4번 픽의 반대
        """
        if len(self.results) < 4:
            return self.results[0]  # 안전장치
        
        pick1 = self.results[0]  # 첫 번째 결과
        pick2 = self.results[1]  # 두 번째 결과
        pick4 = self.results[3]  # 네 번째 결과
        
        if pick1 == pick2:
            return pick4
        else:
            return self.get_opposite_pick(pick4)
    
    def _calculate_stage2_pick(self, stage1_pick: str) -> str:
        """
        2단계 픽 계산:
        - 1단계의 4개 결과 중 2승 이상이면 1단계와 동일
        - 1승 이하이면 반대 픽
        """
        if len(self.results) < 4:
            return stage1_pick  # 안전장치
        
        # 1단계 픽과 실제 결과 비교 (첫 4판)
        wins = 0
        for i in range(4):
            if self.results[i] == stage1_pick:
                wins += 1
        
        if wins >= 2:
            return stage1_pick
        else:
            return self.get_opposite_pick(stage1_pick)
    
    def _calculate_stage3_pick(self, stage2_pick: str) -> str:
        """
        3단계 픽 계산:
        - 5~8번 픽은 2단계 픽과 동일
        - 9번부터 2단계 픽에서 1회 실패 후 반대 픽 성공시 이후는 동일
        """
        if len(self.results) < 9:
            return stage2_pick  # 안전장치
        
        # 5~8번은 2단계 픽 사용
        stage3_pick = stage2_pick
        
        # 9번부터는 특별 조건 확인
        # 8번째 결과가 2단계 픽과 다르고(실패), 반대 픽이 성공한 경우
        if (self.results[7] != stage2_pick) and (self.results[8] == self.get_opposite_pick(stage2_pick)):
            stage3_pick = self.get_opposite_pick(stage2_pick)
            
        return stage3_pick
    
    def _calculate_stage4_pick(self, stage3_pick: str) -> str:
        """
        4단계 픽 계산:
        - 5~10번 픽은 3단계 픽과 동일
        - 11번부터 3단계 픽에서 1회 실패 후 반대 픽 성공시 이후는 동일
        """
        if len(self.results) < 11:
            return stage3_pick  # 안전장치
        
        # 5~10번은 3단계 픽 사용
        stage4_pick = stage3_pick
        
        # 11번부터는 특별 조건 확인
        # 10번째 결과가 3단계 픽과 다르고(실패), 반대 픽이 성공한 경우
        if (self.results[9] != stage3_pick) and (self.results[10] == self.get_opposite_pick(stage3_pick)):
            stage4_pick = self.get_opposite_pick(stage3_pick)
            
        return stage4_pick
    
    def _calculate_stage5_pick(self, stage4_pick: str) -> str:
        """
        5단계 픽 계산:
        - 5~11번 픽은 1단계 픽과 동일
        - 12번부터 이전 4단계 최근 4판 결과 중 2승 이상이면 4단계 픽과 동일, 이하면 반대
        """
        if len(self.results) < 12:
            return stage4_pick  # 안전장치
        
        # 5~11번 결과는 원래 1단계 픽 사용하나, 
        # 여기서는 전체 15판을 사용하므로 바로 12번 이후 규칙 적용
        
        # 이전 4단계 픽으로 최근 4판(11~14번)을 예측했을 때 승 수 계산
        wins = 0
        for i in range(11, 15):
            if i < len(self.results) and self.results[i] == stage4_pick:
                wins += 1
        
        if wins >= 2:
            return stage4_pick
        else:
            return self.get_opposite_pick(stage4_pick)
    
    def _find_normal_betting_candidates(self) -> Dict[str, int]:
        """
        정배팅 후보 및 점수 계산
        - 최근 결과에 3연패 이상 없어야 함
        - 최근 2연패 이하이며 마지막 결과가 반드시 패여야 함
        - 점수: 승 - 패
        
        Returns:
            Dict[str, int]: 픽 후보와 점수 {픽: 점수}
        """
        candidates = {}
        
        for stage, pick in self.stage_picks.items():
            # 최근 결과에서 해당 픽의 승패 확인
            wins = 0
            losses = 0
            consecutive_losses = 0
            max_consecutive_losses = 0
            
            for result in self.results:
                if result == pick:
                    wins += 1
                    consecutive_losses = 0
                else:
                    losses += 1
                    consecutive_losses += 1
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            
            # 마지막 결과가 패배인지 확인
            last_is_loss = self.results[-1] != pick
            
            # 3연패 이상이 없고, 마지막 결과가 패배인 경우에만 후보
            if max_consecutive_losses < 3 and last_is_loss:
                score = wins - losses
                candidates[pick] = score
                self.logger.info(f"정배팅 후보: 스테이지 {stage}의 픽 {pick}, 점수: {score}")
        
        return candidates
    
    def _find_reverse_betting_candidates(self) -> Dict[str, int]:
        """
        역배팅 후보 및 점수 계산
        - 최근 결과에 3연승 이상 없어야 함
        - 최근 2연승 이하이며 마지막 결과가 반드시 승이어야 함
        - 점수: 패 - 승
        
        Returns:
            Dict[str, int]: 픽 후보와 점수 {픽: 점수}
        """
        candidates = {}
        
        for stage, pick in self.stage_picks.items():
            # 해당 픽의 반대 픽 가져오기
            opposite_pick = self.get_opposite_pick(pick)
            
            # 최근 결과에서 반대 픽의 승패 확인 (원래 픽 기준으로는 반대)
            wins = 0
            losses = 0
            consecutive_wins = 0
            max_consecutive_wins = 0
            
            for result in self.results:
                if result == pick:  # 원래 픽과 같으면 반대 픽 관점에서는 패배
                    losses += 1
                    consecutive_wins = 0
                else:  # 원래 픽과 다르면 반대 픽 관점에서는 승리
                    wins += 1
                    consecutive_wins += 1
                    max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            
            # 마지막 결과가 반대 픽의 승리인지 확인
            last_is_win = self.results[-1] != pick  # 원래 픽과 다르면 반대 픽은 승리
            
            # 3연승 이상이 없고, 마지막 결과가 승리인 경우에만 후보
            if max_consecutive_wins < 3 and last_is_win:
                score = losses - wins  # 패 - 승 (반대 픽 관점)
                candidates[opposite_pick] = score
                self.logger.info(f"역배팅 후보: 스테이지 {stage}의 픽 {pick}의 반대 {opposite_pick}, 점수: {score}")
        
        return candidates
    
    def _select_final_pick(self, normal_candidates: Dict[str, int], reverse_candidates: Dict[str, int]) -> Tuple[Optional[str], str, int]:
        """
        최종 초이스 픽 선택
        - 정배팅/역배팅 후보 중 점수가 가장 높은 픽 선택
        - 점수가 같은 경우 패스
        
        Args:
            normal_candidates: 정배팅 후보와 점수
            reverse_candidates: 역배팅 후보와 점수
            
        Returns:
            (선택된 픽, 배팅 방향, 점수) 또는 (None, "", 0) 적합한 픽이 없는 경우
        """
        best_pick = None
        best_direction = ""
        best_score = float('-inf')
        
        # 정배팅 후보 확인
        for pick, score in normal_candidates.items():
            if score > best_score:
                best_pick = pick
                best_direction = "normal"
                best_score = score
        
        # 역배팅 후보 확인
        for pick, score in reverse_candidates.items():
            if score > best_score:
                best_pick = pick
                best_direction = "reverse"
                best_score = score
        
        # 최종 픽 결정
        if best_pick is not None:
            # 마지막으로 점수 동일한 경우 체크
            normal_same_score = [p for p, s in normal_candidates.items() if s == best_score]
            reverse_same_score = [p for p, s in reverse_candidates.items() if s == best_score]
            
            if len(normal_same_score) + len(reverse_same_score) > 1:
                self.logger.warning(f"동일 점수 픽 발견: {normal_same_score + reverse_same_score}, 점수: {best_score} - 패스")
                return None, "", 0
                
            return best_pick, best_direction, best_score
        else:
            return None, "", 0
    
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
                self.last_win_count = 0  # 승리 시 마지막 승리 이후 판 수 리셋
                self.logger.info("베팅 성공으로 마틴 단계와 실패 카운터 초기화")
        else:
            self.logger.info(f"베팅 실패. 시도: {self.betting_attempts}번째, 마틴 단계: {self.martin_step+1}")
            
            # 실패 시 마틴 단계 증가 (최대 2까지)
            if self.martin_step < 2:  # 0부터 시작하므로 2가 최대값 (3단계)
                self.martin_step += 1
                self.logger.info(f"마틴 단계 증가: {self.martin_step+1}단계")
            else:
                # 3마틴까지 모두 실패한 경우
                self.consecutive_failures += 1
                self.martin_step = 0  # 마틴 단계 초기화
                self.logger.warning(f"3마틴 모두 실패! 연속 실패: {self.consecutive_failures}회")
    
    def get_current_bet_amount(self) -> int:
        """현재 마틴 단계에 따른 베팅 금액 반환"""
        if self.martin_step < len(self.martin_amounts):
            return self.martin_amounts[self.martin_step]
        return self.martin_amounts[-1]  # 안전장치
        
    def should_change_room(self) -> bool:
        """
        방 이동이 필요한지 확인
        
        Returns:
            bool: 방 이동 필요 여부
        """
        # 1. 3마틴까지 모두 실패 시 방 이동
        if self.consecutive_failures >= 1 and self.martin_step == 0:
            self.logger.info("3마틴 모두 실패로 방 이동 필요")
            return True
            
        # 2. 초이스 픽 2회 연속 실패 시 방 이동
        if len(self.pick_results) >= 2 and not any(self.pick_results[-2:]):
            self.logger.info("초이스 픽 2회 연속 실패로 방 이동 필요")
            return True
            
        # 3. 현재 게임 판수가 57판 이상이고 현재 베팅이 없는 상태일 때 방 이동
        if self.betting_attempts == 0 and self.martin_step == 0 and self.last_win_count >= 57:
            self.logger.info(f"현재 게임 판수가 57판 이상이고 배팅 중이 아님 → 방 이동 필요")
            return True
            
        return False
    
    def reset_after_room_change(self) -> None:
        """방 이동 후 초기화"""
        # 기존 상태 백업 (디버깅용)
        prev_failures = self.consecutive_failures
        prev_martin = self.martin_step
        prev_results = len(self.pick_results)
        
        # 필요한 항목만 초기화 (결과 데이터는 유지)
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
        self.stage_picks = {}
        self.pick_scores = {}
        self.betting_attempts = 0
        self.martin_step = 0
        self.pick_results = []
        self.last_win_count = 0
        self.logger.info("초이스 픽 시스템 전체 초기화 완료")

    def set_martin_amounts(self, amounts: List[int]) -> None:
        """마틴 금액 설정"""
        if len(amounts) >= 3:
            self.martin_amounts = amounts[:3]  # 3단계까지만 사용
            self.logger.info(f"마틴 금액 설정: {self.martin_amounts}")
        else:
            self.logger.warning(f"마틴 금액 설정 실패: 최소 3단계 필요 (현재 {len(amounts)}단계)")