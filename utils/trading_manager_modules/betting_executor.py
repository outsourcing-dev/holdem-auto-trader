# utils/trading_manager_modules/betting_executor.py - 베팅 추적 통합
import logging
from utils.trading_manager_helpers import get_widget_position


class BettingExecutor:
    """베팅 실행 전담 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger

    # utils/trading_manager_modules/betting_executor.py - execute_betting 메서드 수정

    def execute_betting(self, pick: str, round_number: int):
        """베팅 실행 - 추적 통합"""
        try:
            streak_info = ""
            if self.tm.current_target_room:
                streak_count = self.tm.current_target_room.get('streak_count', 0)
                streak_info = f" (연패: {streak_count})"
            
            # 🔥 실제 현재 라운드 확인
            try:
                actual_round = self.tm.game_monitoring_service._find_round_number()
                if actual_round > round_number:
                    self.logger.info(f"🔄 라운드 번호 업데이트: {round_number} → {actual_round}")
                    round_number = actual_round
            except:
                pass
            
            # 🔥 다음 라운드에 베팅 (현재 게임이 진행 중이므로)
            betting_round = round_number + 1
            
            self.logger.info(f"🎯 베팅 실행: {pick} (라운드 {betting_round}){streak_info}")
            
            # 베팅 금액 계산
            widget_pos = get_widget_position(self.tm.main_window)
            bet_amount = self.tm.excel_trading_service.get_current_bet_amount(widget_position=widget_pos)
            
            # 베팅 추적 시작 - 다음 라운드로 설정
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                if not self.tm.game_processor.betting_tracker.is_waiting_for_result():
                    self.tm.game_processor.betting_tracker.start_betting_tracking(
                        bet_type=pick,
                        round_number=betting_round,  # 🔥 다음 라운드로 설정
                        bet_amount=bet_amount,
                        room_name=self.tm.current_room_name
                    )
            
            # 베팅 실행 - 현재 게임 카운트 사용
            bet_success = self.tm.betting_service.place_bet(
                pick,
                self.tm.current_room_name,
                round_number,  # 현재 게임 카운트
                self.tm.is_trading_active,
                bet_amount
            )
            
            if bet_success:
                self.logger.info(f"✅ 베팅 성공: {pick}, 금액: {bet_amount:,}원 (라운드 {betting_round}){streak_info}")
                self.tm.main_window.update_betting_status(
                    pick=pick, 
                    bet_amount=bet_amount,
                    streak_info=streak_info
                )
            else:
                self.logger.warning(f"❌ 베팅 실패: {pick}")
                # 베팅 실패 시 추적 취소
                if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                    self.tm.game_processor.betting_tracker.reset_tracking()
                    
        except Exception as e:
            self.logger.error(f"베팅 실행 오류: {e}")
            # 오류 시 추적 취소
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                self.tm.game_processor.betting_tracker.reset_tracking()
                
    def generate_pick_for_streak_room(self) -> str:
        """연패 방을 위한 픽 생성"""
        try:
            if not self.tm.current_target_room:
                return 'P'
            
            # ExcelTradingService의 ChoicePickSystem 사용
            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                pick = self.tm.excel_trading_service.choice_pick_system.generate_choice_pick()
                if pick in ['P', 'B']:
                    return pick
            
            return 'P'  # 기본값
            
        except Exception as e:
            self.logger.error(f"픽 생성 오류: {e}")
            return 'P'