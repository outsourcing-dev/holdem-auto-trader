# utils/betting_result_tracker.py - 새로운 파일
import logging
import time
from typing import Optional, Dict, Any
from enum import Enum

class BettingStatus(Enum):
    """베팅 상태 열거형"""
    IDLE = "idle"                    # 대기 중
    BETTING = "betting"              # 베팅 중
    WAITING_RESULT = "waiting"       # 결과 대기 중
    RESULT_CONFIRMED = "confirmed"   # 결과 확인됨

class BettingResult(Enum):
    """베팅 결과 열거형"""
    WIN = "win"      # 승리
    LOSE = "lose"    # 패배
    TIE = "tie"      # 무승부

class BettingResultTracker:
    """베팅 결과 추적 및 검증 클래스"""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        
        # 베팅 추적 상태
        self.status = BettingStatus.IDLE
        self.bet_info = {}
        self.result_info = {}
        
        # 베팅 히스토리
        self.betting_history = []
        self.max_history = 50  # 최대 50개까지 기록
        
        self.logger.info("베팅 결과 추적기 초기화 완료")

    def start_betting_tracking(self, bet_type: str, round_number: int, bet_amount: int, room_name: str):
        """베팅 추적 시작 - 중복 방지 강화"""
        try:
            # 🔥 이전 베팅이 완료되지 않았으면 시작 거부
            if self.status != BettingStatus.IDLE:
                self.logger.warning(f"❌ 베팅 추적 시작 거부: 이전 베팅이 완료되지 않음 ({self.status.value})")
                return False
            
            # 동일한 라운드의 중복 베팅 방지
            if (hasattr(self, 'bet_info') and 
                self.bet_info.get('round_number') == round_number and
                time.time() - self.bet_info.get('bet_time', 0) < 30):  # 30초 이내 동일 라운드 중복 방지
                self.logger.warning(f"❌ 동일 라운드 중복 베팅 방지: 라운드 {round_number}")
                return False
            
            # 베팅 정보 저장
            self.bet_info = {
                'bet_type': bet_type,
                'round_number': round_number,
                'bet_amount': bet_amount,
                'room_name': room_name,
                'bet_time': time.time(),
                'bet_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.status = BettingStatus.WAITING_RESULT
            self.result_info = {}
            
            self.logger.info(f"🎯 베팅 추적 시작: {bet_type} 라운드{round_number} {bet_amount:,}원")
            return True
            
        except Exception as e:
            self.logger.error(f"베팅 추적 시작 오류: {e}")
            return False

    def check_result(self, round_number: int, game_result: str) -> Optional[BettingResult]:
        """베팅 결과 확인"""
        try:
            # 베팅 결과 대기 중이 아니면 무시
            if self.status != BettingStatus.WAITING_RESULT:
                return None
            
            # 베팅한 라운드 이후의 결과인지 확인
            if round_number <= self.bet_info.get('round_number', 0):
                return None
            
            bet_type = self.bet_info.get('bet_type')
            
            # 결과 판정
            if game_result == 'T':
                result = BettingResult.TIE
            elif bet_type == game_result:
                result = BettingResult.WIN
            else:
                result = BettingResult.LOSE
            
            # 결과 정보 저장
            self.result_info = {
                'game_result': game_result,
                'betting_result': result,
                'result_round': round_number,
                'result_time': time.time(),
                'result_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            self.status = BettingStatus.RESULT_CONFIRMED
            
            self.logger.info(f"🎲 베팅 결과 확인: {bet_type} vs {game_result} = {result.value}")
            
            # 히스토리에 추가
            self._add_to_history()
            
            return result
            
        except Exception as e:
            self.logger.error(f"베팅 결과 확인 오류: {e}")
            return None

    def get_current_bet_info(self) -> Dict[str, Any]:
        """현재 베팅 정보 반환"""
        return {
            'status': self.status.value,
            'bet_info': self.bet_info.copy(),
            'result_info': self.result_info.copy()
        }

    def is_waiting_for_result(self) -> bool:
        """베팅 결과 대기 중인지 확인"""
        return self.status == BettingStatus.WAITING_RESULT

    def get_bet_round(self) -> Optional[int]:
        """베팅한 라운드 번호 반환"""
        return self.bet_info.get('round_number')

    def get_bet_type(self) -> Optional[str]:
        """베팅한 타입 반환"""
        return self.bet_info.get('bet_type')

    def reset_tracking(self):
        """추적 상태 초기화"""
        try:
            self.status = BettingStatus.IDLE
            self.bet_info = {}
            self.result_info = {}
            
            self.logger.info("베팅 추적 상태 초기화")
            
        except Exception as e:
            self.logger.error(f"추적 상태 초기화 오류: {e}")

    def _add_to_history(self):
        """히스토리에 베팅 기록 추가"""
        try:
            history_record = {
                **self.bet_info,
                **self.result_info,
                'profit_loss': self._calculate_profit_loss()
            }
            
            self.betting_history.append(history_record)
            
            # 최대 개수 초과 시 오래된 기록 제거
            if len(self.betting_history) > self.max_history:
                self.betting_history = self.betting_history[-self.max_history:]
            
            self.logger.debug(f"베팅 히스토리 추가: 총 {len(self.betting_history)}개 기록")
            
        except Exception as e:
            self.logger.error(f"히스토리 추가 오류: {e}")

    def _calculate_profit_loss(self) -> int:
        """손익 계산"""
        try:
            bet_amount = self.bet_info.get('bet_amount', 0)
            result = self.result_info.get('betting_result')
            
            if result == BettingResult.WIN:
                # 승리 시 배당 (일반적으로 1:1)
                return bet_amount
            elif result == BettingResult.LOSE:
                # 패배 시 베팅 금액 손실
                return -bet_amount
            else:  # TIE
                # 무승부 시 손익 없음
                return 0
                
        except Exception as e:
            self.logger.error(f"손익 계산 오류: {e}")
            return 0

    def get_recent_results(self, count: int = 10) -> list:
        """최근 베팅 결과 반환"""
        try:
            recent = self.betting_history[-count:] if count > 0 else self.betting_history
            return recent
            
        except Exception as e:
            self.logger.error(f"최근 결과 조회 오류: {e}")
            return []

    def get_win_rate(self, count: int = 10) -> float:
        """승률 계산"""
        try:
            recent_results = self.get_recent_results(count)
            
            if not recent_results:
                return 0.0
            
            wins = sum(1 for r in recent_results 
                      if r.get('betting_result') == BettingResult.WIN)
            
            # 무승부는 제외하고 계산
            valid_games = sum(1 for r in recent_results 
                            if r.get('betting_result') in [BettingResult.WIN, BettingResult.LOSE])
            
            if valid_games == 0:
                return 0.0
            
            win_rate = (wins / valid_games) * 100
            return round(win_rate, 2)
            
        except Exception as e:
            self.logger.error(f"승률 계산 오류: {e}")
            return 0.0

    def get_consecutive_results(self) -> Dict[str, int]:
        """연속 결과 분석"""
        try:
            if not self.betting_history:
                return {'consecutive_wins': 0, 'consecutive_losses': 0}
            
            consecutive_wins = 0
            consecutive_losses = 0
            
            # 최근 결과부터 역순으로 확인
            for record in reversed(self.betting_history):
                result = record.get('betting_result')
                
                if result == BettingResult.WIN:
                    if consecutive_losses == 0:  # 연속 승리 중
                        consecutive_wins += 1
                    else:  # 연속 패배가 끝남
                        break
                elif result == BettingResult.LOSE:
                    if consecutive_wins == 0:  # 연속 패배 중
                        consecutive_losses += 1
                    else:  # 연속 승리가 끝남
                        break
                # TIE는 연속성을 끊지 않음
            
            return {
                'consecutive_wins': consecutive_wins,
                'consecutive_losses': consecutive_losses
            }
            
        except Exception as e:
            self.logger.error(f"연속 결과 분석 오류: {e}")
            return {'consecutive_wins': 0, 'consecutive_losses': 0}

    def should_change_room(self, max_consecutive_losses: int = 3) -> bool:
        """방 이동 필요 여부 판단"""
        try:
            consecutive_results = self.get_consecutive_results()
            consecutive_losses = consecutive_results['consecutive_losses']
            
            if consecutive_losses >= max_consecutive_losses:
                self.logger.info(f"연속 패배 {consecutive_losses}회로 방 이동 필요")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"방 이동 판단 오류: {e}")
            return False

    def get_total_profit_loss(self, count: int = None) -> int:
        """총 수익/손실 계산"""
        try:
            results = self.get_recent_results(count) if count else self.betting_history
            
            total = sum(r.get('profit_loss', 0) for r in results)
            return total
            
        except Exception as e:
            self.logger.error(f"총 손익 계산 오류: {e}")
            return 0

    def debug_status(self):
        """디버그용 상태 출력"""
        try:
            self.logger.info("🔍 베팅 추적기 상태:")
            self.logger.info(f"  - 현재 상태: {self.status.value}")
            self.logger.info(f"  - 베팅 정보: {self.bet_info}")
            self.logger.info(f"  - 결과 정보: {self.result_info}")
            self.logger.info(f"  - 히스토리 개수: {len(self.betting_history)}")
            
            if self.betting_history:
                win_rate = self.get_win_rate(10)
                consecutive = self.get_consecutive_results()
                total_pnl = self.get_total_profit_loss(10)
                
                self.logger.info(f"  - 최근 10게임 승률: {win_rate}%")
                self.logger.info(f"  - 연속 승리: {consecutive['consecutive_wins']}")
                self.logger.info(f"  - 연속 패배: {consecutive['consecutive_losses']}")
                self.logger.info(f"  - 최근 10게임 손익: {total_pnl:,}원")
            
        except Exception as e:
            self.logger.error(f"디버그 상태 출력 오류: {e}")