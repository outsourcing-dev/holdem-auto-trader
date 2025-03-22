# utils/analysis_thread.py
from PyQt6.QtCore import QThread, pyqtSignal
import logging

class GameAnalysisThread(QThread):
    """게임 분석 작업을 위한 스레드"""
    # 결과 전달용 신호 정의
    analysis_complete = pyqtSignal(dict)  # 게임 상태 결과를 담은 신호
    analysis_error = pyqtSignal(str)      # 오류 메시지를 담은 신호
    room_change_needed = pyqtSignal()     # 방 이동이 필요할 때 발생하는 신호
    
    def __init__(self, trading_manager):
        super().__init__()
        self.tm = trading_manager
        self.logger = trading_manager.logger or logging.getLogger(__name__)
        self.should_move_to_next_room = trading_manager.should_move_to_next_room
        self.game_count = trading_manager.game_count
        self.current_room_name = trading_manager.current_room_name
        
    # utils/analysis_thread.py에서 Excel 관련 코드 수정
    def run(self):
        """스레드의 메인 실행 메서드"""
        try:
            # 방 이동이 필요한지 먼저 확인
            if self.should_move_to_next_room:
                self.logger.info("방 이동 필요 감지 (스레드)")
                self.room_change_needed.emit()
                return
                    
            # 게임 상태 가져오기만 스레드에서 수행
            game_state = self.tm.game_monitoring_service.get_current_game_state(log_always=True)
            
            if not game_state:
                self.logger.error("게임 상태를 가져올 수 없습니다. (스레드)")
                self.analysis_error.emit("게임 상태를 가져올 수 없습니다.")
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
            