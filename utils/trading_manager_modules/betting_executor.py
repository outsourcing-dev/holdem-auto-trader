# utils/trading_manager_modules/betting_executor.py
import logging
from utils.trading_manager_helpers import get_widget_position


class BettingExecutor:
    """베팅 실행 전담 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger

    def execute_betting(self, pick: str, round_number: int):
        """베팅 실행 - 추적 통합"""
        try:
            streak_info = ""
            if self.tm.current_target_room:
                streak_count = self.tm.current_target_room.get('streak_count', 0)
                streak_info = f" (연패: {streak_count})"
            
            # 현재 표시된 라운드에서 베팅하면 다음 라운드에 적용됨
            display_round = round_number  # 현재 표시된 라운드
            actual_betting_round = round_number + 1  # 실제 베팅이 적용될 라운드
            
            self.logger.info(f"🎯 베팅 실행: {pick} (표시 라운드: {display_round}, 적용 라운드: {actual_betting_round}){streak_info}")
            
            # 베팅 금액 계산
            widget_pos = get_widget_position(self.tm.main_window)
            bet_amount = self.tm.excel_trading_service.get_current_bet_amount(widget_position=widget_pos)
            
            # 베팅 추적 시작 - 실제 적용될 라운드로 설정
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                if not self.tm.game_processor.betting_tracker.is_waiting_for_result():
                    self.tm.game_processor.betting_tracker.start_betting_tracking(
                        bet_type=pick,
                        round_number=actual_betting_round,  # 실제 베팅이 적용될 라운드
                        bet_amount=bet_amount,
                        room_name=self.tm.current_room_name
                    )
            
            # 베팅 실행
            bet_success = self.tm.betting_service.place_bet(
                pick,
                self.tm.current_room_name,
                display_round,  # 현재 표시된 라운드 사용
                self.tm.is_trading_active,
                bet_amount
            )
            
            if bet_success:
                self.logger.info(f"✅ 베팅 성공: {pick}, 금액: {bet_amount:,}원 (적용 라운드: {actual_betting_round}){streak_info}")
                
                # 베팅 서비스에도 실제 적용 라운드 정보 저장
                if hasattr(self.tm.betting_service, 'last_bet_round'):
                    self.tm.betting_service.last_bet_round = actual_betting_round
                
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