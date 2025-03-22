# utils/analysis_thread.py
from PyQt6.QtCore import QThread, pyqtSignal
import logging
# utils/analysis_thread.py의 GameAnalysisThread 클래스 수정

class GameAnalysisThread(QThread):
    """게임 분석 작업을 위한 스레드 - 중지 가능"""
    # 결과 전달용 신호 정의
    analysis_complete = pyqtSignal(dict)  # 게임 상태 결과를 담은 신호
    analysis_error = pyqtSignal(str)      # 오류 메시지를 담은 신호
    room_change_needed = pyqtSignal()     # 방 이동이 필요할 때 발생하는 신호
    
    def __init__(self, trading_manager):
        super().__init__()
        self.tm = trading_manager  # TradingManager 객체 참조
        self.logger = trading_manager.logger or logging.getLogger(__name__)
        self.should_move_to_next_room = trading_manager.should_move_to_next_room
        self.game_count = trading_manager.game_count
        self.current_room_name = trading_manager.current_room_name
        
        # 중지 플래그 추가
        self.should_stop = False
    
    def run(self):
        """스레드의 메인 실행 메서드 - 중지 확인 기능 추가"""
        try:
            # 중요: 매 단계마다 중지 요청 확인
            # 1. TradingManager의 중지 플래그 확인
            if hasattr(self.tm, 'stop_all_processes') and self.tm.stop_all_processes:
                self.logger.info("중지 명령으로 인해 분석 스레드가 실행을 중단합니다.")
                return
                
            # 2. 목표 금액 도달 확인 (추가)
            if hasattr(self.tm.balance_service, '_target_amount_reached') and self.tm.balance_service._target_amount_reached:
                self.logger.info("목표 금액 도달로 인해 분석 스레드가 실행을 중단합니다.")
                return
                
            # 3. 자동 매매 활성화 상태 확인
            if not self.tm.is_trading_active:
                self.logger.info("자동 매매가 비활성화되어 분석 스레드가 실행을 중단합니다.")
                return
                
            # 4. 스레드 자체의 중지 플래그 확인
            if self.should_stop:
                self.logger.info("스레드 중지 플래그로 인해 분석 스레드가 실행을 중단합니다.")
                return

            # 방 이동이 필요한지 먼저 확인
            if self.should_move_to_next_room:
                # 중지 요청 한번 더 확인
                if hasattr(self.tm, 'stop_all_processes') and self.tm.stop_all_processes:
                    self.logger.info("중지 명령으로 인해 방 이동 요청을 무시합니다.")
                    return
                
                self.logger.info("방 이동 필요 감지 (스레드)")
                self.room_change_needed.emit()
                return
                    
            # 게임 상태 가져오기만 스레드에서 수행
            game_state = self.tm.game_monitoring_service.get_current_game_state(log_always=True)
            
            if not game_state:
                self.logger.error("게임 상태를 가져올 수 없습니다. (스레드)")
                self.analysis_error.emit("게임 상태를 가져올 수 없습니다.")
                return
            
            # 중지 요청 한번 더 확인
            if hasattr(self.tm, 'stop_all_processes') and self.tm.stop_all_processes:
                self.logger.info("중지 명령으로 인해 분석 결과 전송을 중단합니다.")
                return
                
            # Excel 작업은 수행하지 않고 그냥 결과 전달
            # 메인 스레드에서 Excel 작업을 처리하도록 함
            analysis_result = {
                'game_state': game_state,
                'previous_game_count': self.game_count
            }
            
            # 결과를 메인 스레드로 전송
            self.analysis_complete.emit(analysis_result)
                    
        except Exception as e:
            self.logger.error(f"게임 상태 분석 스레드 오류: {e}", exc_info=True)
            self.analysis_error.emit(f"게임 상태 분석 오류: {str(e)}")
    
    def stop(self):
        """스레드 중지 요청"""
        self.should_stop = True
        self.logger.info("게임 분석 스레드 중지 요청됨")