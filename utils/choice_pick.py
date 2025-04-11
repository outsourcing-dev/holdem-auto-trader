from typing import List, Dict, Optional, Tuple, Any
import logging
from utils.bet_logger import log_bet_to_file
from utils.online_ai_predictor import OnlineAIPredictor  # 별도 파일로 저장될 AI 예측기 임포트

class ChoicePickSystem:
    """
    초이스 픽 시스템 - AI 기반 예측 엔진 통합
    """
    def __init__(self, room_name: str, logger=None):
        """초기화"""
        self.room_name = room_name
        self.logger = logger
        self.results: List[str] = []  # 최근 게임 결과 (P/B만)
        self.current_pick: Optional[str] = None  # 현재 초이스 픽
        self.betting_direction: str = "normal"  # 'normal' 또는 'reverse'
        self.consecutive_failures: int = 0  # 연속 실패 횟수
        self.pick_scores: Dict[str, int] = {}  # 픽 후보들의 점수
        self.betting_attempts: int = 0  # 현재 픽으로 배팅 시도 횟수
        self.confidence: float = 0.0

        # 3마틴 배팅 관련 변수
        self.martin_step: int = 0  # 현재 마틴 단계 (0부터 시작)
        self.martin_amounts: List[int] = [1000, 2000, 4000]  # 기본 마틴 금액
        
        # 픽 생성 후 성공/실패 여부 추적
        self.pick_results: List[bool] = []  # True=성공, False=실패
        
        # 방 이동 카운터
        self.last_win_count: int = 0  # 마지막 승리 이후 판 수
        
        # 기존 변수 유지
        self.consecutive_n_count: int = 0  # 연속 N 발생 카운트
        self.original_pick: Optional[str] = None  # 원래 선택한 PICK 값
        self.current_direction = 'forward'  # 현재 방향 (forward / reverse)
        
        # 캐싱 관련 변수
        self.last_results: List[str] = []
        self.cached_pick: Optional[str] = None
        
        # AI 예측기 초기화
        self.ai_predictor = OnlineAIPredictor(logger=self.logger)
        
        # 게임 카운트 추적 변수 추가
        self.game_count = 0

        # 로그 메시지 (logger가 없을 경우 대비)
        if self.logger:
            self.logger.info("AI 기반 ChoicePickSystem 인스턴스 생성")
    
    def set_martin_amounts(self, amounts):
        """마틴 금액 설정"""
        self.martin_amounts = amounts
        if self.logger:
            self.logger.info(f"마틴 금액 업데이트: {amounts}")

    def has_sufficient_data(self) -> bool:
        """
        AI 예측을 위한 충분한 데이터가 있는지 확인
        최소 10개 필요 (AI predictor 기준)
        """
        return len(self.results) >= 10

    def add_result(self, result: str) -> None:
        """
        새 결과 추가 (TIE는 무시)
        
        Args:
            result: 'P', 'B', 또는 'T' (Player, Banker, Tie)
        """
        if result not in ['P', 'B']:
            return
            
        self.results.append(result)
        
        # 게임 카운트 증가
        self.game_count += 1
        
        # 60게임마다 모델 리셋
        if self.game_count > 0 and self.game_count % 80 == 0:
            if self.logger:
                self.logger.info(f"60게임 도달 ({self.game_count}회차) - AI 모델 초기화")
            self.ai_predictor.reset()
        
        # 로깅
        if self.logger:
            self.logger.info(f"결과 추가: {result} (현재 {len(self.results)} 판)")
            self.logger.debug(f"현재 결과 리스트: {self.results}")
        
        self.last_win_count += 1

        # 결과 추가 시 AI 모델 업데이트
        if len(self.results) > 10:  # 최소 10개 이상의 결과가 있을 때
            # 업데이트 - 가장 최근 결과의 이전 상태로 훈련
            self.ai_predictor.update(self.results[:-1], result)

    def add_multiple_results(self, results: List[str]) -> None:
        """
        여러 결과 한번에 추가 (TIE 제외)
        
        Args:
            results: 결과 목록 ['P', 'B', 'T', ...]
        """
        filtered_results = [r for r in results if r in ['P', 'B']]
        
        # 게임 카운트 초기화 및 업데이트
        self.game_count = len(filtered_results)
        
        self.results = filtered_results
        
        if self.logger:
            self.logger.info(f"다중 결과 추가: 총 {len(self.results)}판")
            self.logger.debug(f"현재 결과 리스트: {self.results}")
        
        # 초기 데이터로 AI 모델 학습
        if len(filtered_results) >= 20:  # 최소 20개 이상의 결과가 있을 때
            self.ai_predictor.bulk_train(filtered_results)

    def generate_choice_pick(self) -> str:
        """
        AI 기반 초이스 픽 생성
        
        Returns:
            str: 다음 베팅 픽 ('P', 'B', 또는 'N')
        """
        
        

        # 결과가 변경되지 않았다면 캐시된 값 반환
        if self.results == self.last_results and self.cached_pick is not None:
            if self.logger:
                self.logger.debug(f"결과 변경 없음, 캐시된 PICK 사용: {self.cached_pick}")
            return self.cached_pick
                
        # 결과가 변경된 경우에만 로그 출력
        if self.logger:
            self.logger.info(f"현재 저장된 결과 (총 {len(self.results)}개): {self.results}")
        
        # 충분한 데이터가 있는지 확인
        if len(self.results) < 10:  # AI는 최소 10개의 게임 결과가 필요
            if self.logger:
                self.logger.warning(f"초이스 픽 생성 실패: 데이터 부족 (현재 {len(self.results)}/10판)")
            return 'N'
        
        # AI 예측
        next_pick, confidence = self.ai_predictor.predict(self.results)
        self.confidence = confidence
        
        # N 값 처리
        if next_pick == 'N':
            self.consecutive_n_count += 1
            if self.logger:
                self.logger.warning(f"AI 예측 불확실 (N) - 연속 N 카운트: {self.consecutive_n_count}")
                
            # 연속 N 카운트가 3 이상이면 방 이동 신호
            if self.consecutive_n_count >= 5:
                self._n_consecutive_detected = True
            else:
                self._n_consecutive_detected = False
        else:
            # 유효한 예측이 나오면 N 카운트 초기화
            self.consecutive_n_count = 0
            
            # 배팅 방향 결정 (기존 로직 유지)
            # 여기서는 항상 'normal'로 설정
            self.betting_direction = 'normal'
            
            if self.logger:
                self.logger.info(f"🏆 AI 예측 결과: {next_pick} | 신뢰도: {confidence:.2f} | 방향: {self.betting_direction}")
        
        # 현재 결과를 캐시하고 예측 결과 저장
        self.last_results = self.results.copy()
        self.cached_pick = next_pick
        
        # 베팅할 때만 로그 기록
        if next_pick != 'N':
            bet_info = {
                'room': self.room_name,
                'pick': next_pick,
                'confidence': confidence,
                'accuracy': self.ai_predictor.get_accuracy(),
                'amount': self.get_current_bet_amount()
            }
            log_bet_to_file(bet_info)
            
        return next_pick

    def record_betting_result(self, is_win: bool, reset_after_win: bool = True) -> None:
        """
        베팅 결과 기록 및 처리
        
        Args:
            is_win: 베팅이 성공했는지 여부
            reset_after_win: 승리 시 카운터 리셋 여부
        """
        
        bet_info = {
            'room': self.room_name,
            'pick': self.current_pick,
            'confidence': self.confidence,  # 예측 시점의 confidence 값이 없으므로 0.0으로 설정
            'accuracy': self.ai_predictor.get_accuracy(),
            'amount': self.get_current_bet_amount(),
            'result': self.results[-1] if self.results else 'Unknown',
            'is_win': is_win
        }
        log_bet_to_file(bet_info)
        
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
            # 마틴 한도 확인
            max_martin_steps = len(self.martin_amounts) - 1
            if self.martin_step < max_martin_steps:
                self.martin_step += 1
                if self.logger:
                    self.logger.info(f"마틴 단계 증가: {self.martin_step+1}단계")
            else:
                self.consecutive_failures += 1
                self.martin_step = 0
                if self.logger:
                    self.logger.warning(f"{max_martin_steps + 1}마틴 모두 실패! 연속 실패: {self.consecutive_failures}회")
                    
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
        # 연속 N 발생 체크
        if self.consecutive_n_count >= 5:
            if self.logger:
                self.logger.info(f"3번 연속 유효한 픽 없음(N) 발생으로 방 이동 필요 (연속 카운트: {self.consecutive_n_count})")
            return True
                
        # 마틴 모두 실패한 경우
        if self.consecutive_failures >= 1 and self.martin_step == 0:
            if self.logger:
                self.logger.info("3마틴 모두 실패로 방 이동 필요")
            return True
        
        # 60게임 도달 시 방 이동
        if self.game_count >= 80:
            if self.logger:
                self.logger.info(f"현재 게임 판수가 60판 이상 → 방 이동 필요")
            return True
                
        return False
    
    def reset_after_room_change(self) -> None:
        """방 이동 후 초기화"""
        prev_failures = self.consecutive_failures
        prev_martin = self.martin_step
        prev_results = len(self.pick_results)
        prev_n_count = self.consecutive_n_count

        self.betting_attempts = 0

        # 조건 분기: N값 3회로 이동하는 경우 마틴 상태 유지
        if self.consecutive_n_count < 3:
            self.martin_step = 0
            self.consecutive_failures = 0
        else:
            if self.logger:
                self.logger.info("N값 3회로 방 이동: 마틴 상태 유지")

        # 무조건 초기화되는 항목
        self.consecutive_n_count = 0
        self.current_pick = None
        self.game_count = 0  # 게임 카운트 초기화

        # AI 모델 초기화
        self.ai_predictor.reset()

        if self.logger:
            self.logger.info(
                f"방 이동 후 초기화 완료 - 연속실패({prev_failures}→{self.consecutive_failures}), "
                f"마틴({prev_martin+1}→{self.martin_step+1}), 결과개수({prev_results})"
            )
    
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
        self.consecutive_n_count = 0
        self.game_count = 0

        # AI 예측기 초기화
        self.ai_predictor.reset()
    
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