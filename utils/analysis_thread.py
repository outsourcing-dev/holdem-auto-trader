from PyQt6.QtCore import QThread, pyqtSignal
import logging

class GameAnalysisThread(QThread):
    """게임 분석 작업을 위한 스레드 - 중지 가능, 결과 업데이트 추적 기능 추가"""
    analysis_complete = pyqtSignal(dict)
    analysis_error = pyqtSignal(str)
    room_change_needed = pyqtSignal()
    consecutive_n_detected = pyqtSignal()

    def __init__(self, trading_manager):
        super().__init__()
        self.tm = trading_manager
        self.logger = trading_manager.logger or logging.getLogger(__name__)
        self.game_count = trading_manager.game_count
        self.current_room_name = trading_manager.current_room_name
        self.should_stop = False

    def run(self):
        """스레드의 메인 실행 메서드"""
        try:
            if hasattr(self.tm, 'stop_all_processes') and self.tm.stop_all_processes:
                return

            if hasattr(self.tm.balance_service, '_target_amount_reached') and self.tm.balance_service._target_amount_reached:
                return

            if not self.tm.is_trading_active:
                return

            if self.should_stop:
                return

            if self.tm.should_move_to_next_room:
                if hasattr(self.tm, 'stop_all_processes') and self.tm.stop_all_processes:
                    return

                consecutive_n = False
                if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                    consecutive_n = self.tm.excel_trading_service.choice_pick_system.consecutive_n_count >= 3

                if consecutive_n:
                    self.consecutive_n_detected.emit()
                else:
                    self.room_change_needed.emit()
                return

            failure_count = 0
            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                failure_count = getattr(
                    self.tm.excel_trading_service.choice_pick_system,
                    'failure_count',
                    0
                )

            desired_pb_count = min(17, 15 + failure_count)

            game_state = self.tm.game_monitoring_service.get_current_game_state(
                log_always=False,
                desired_pb_count=desired_pb_count
            )

            if not game_state:
                self.logger.error("게임 상태를 가져올 수 없습니다.")
                self.analysis_error.emit("게임 상태를 가져올 수 없습니다.")
                return

            current_game_count = game_state.get('round', 0)

            if current_game_count == self.game_count and self.game_count > 0:
                analysis_result = {
                    'game_state': game_state,
                    'previous_game_count': self.game_count,
                    'new_result': False
                }
                self.analysis_complete.emit(analysis_result)
                return

            if hasattr(self.tm, 'stop_all_processes') and self.tm.stop_all_processes:
                return

            analysis_result = {
                'game_state': game_state,
                'previous_game_count': self.game_count,
                'new_result': True
            }
            self.analysis_complete.emit(analysis_result)

        except Exception as e:
            self.logger.error(f"게임 상태 분석 스레드 오류: {e}", exc_info=True)
            self.analysis_error.emit(f"게임 상태 분석 오류: {str(e)}")

    def stop(self):
        """스레드 중지 요청"""
        self.should_stop = True
