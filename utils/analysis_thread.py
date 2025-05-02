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
            # 중지 관련 플래그들 먼저 체크
            if hasattr(self.tm, 'stop_all_processes') and self.tm.stop_all_processes:
                return

            if hasattr(self.tm.balance_service, '_target_amount_reached') and self.tm.balance_service._target_amount_reached:
                return

            if not self.tm.is_trading_active:
                return

            if self.should_stop:
                return

            # 방 이동 필요 조건 체크
            if self.tm.should_move_to_next_room:
                consecutive_n = False
                if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                    consecutive_n = self.tm.excel_trading_service.choice_pick_system.consecutive_n_count >= 8

                if consecutive_n:
                    self.consecutive_n_detected.emit()
                else:
                    self.room_change_needed.emit()
                return

            # 실패 카운트 고려하여 필터링 개수 결정
            failure_count = 0
            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                failure_count = getattr(
                    self.tm.excel_trading_service.choice_pick_system,
                    'failure_count',
                    0
                )
            desired_pb_count = min(17, 15 + failure_count)

            # ✅ 0. Fix to prevent "same round" detection after enough time
            entered_round = getattr(self.tm, 'entered_round', None)
            current_round = getattr(self.tm, '_current_game_round', None)
            
            # If we've been detecting the same round for too long, force new result processing
            force_new_result = False
            if hasattr(self.tm, 'same_round_count'):
                if entered_round == current_round:
                    self.tm.same_round_count += 1
                    if self.tm.same_round_count > 10:  # After 10 checks (about 20 seconds)
                        force_new_result = True
                        self.logger.info(f"10회 이상 동일 라운드 감지: 강제 결과 처리 모드")
            else:
                self.tm.same_round_count = 0

            # 게임 상태 분석
            game_state = self.tm.game_monitoring_service.get_current_game_state(
                log_always=False,
                desired_pb_count=desired_pb_count
            )

            if not game_state:
                self.logger.error("게임 상태를 가져올 수 없습니다.")
                self.analysis_error.emit("게임 상태를 가져올 수 없습니다.")
                return

            current_game_count = game_state.get('round', 0)
            
            # ✅ Important fix: If we've been stuck on the same round for too long,
            if force_new_result:
                self.logger.info("동일 게임 10회 이상 감지로 강제 진행")
                # Reset the counter
                self.tm.same_round_count = 0
                # Turn off wait flag
                if hasattr(self.tm, 'wait_first_result'):
                    self.tm.wait_first_result = False
                # 추가: 다음 라운드 예측 설정으로 새 결과 인식되도록 함
                self.tm.entered_round = current_game_count + 1
                # 초이스픽 시스템에도 동일하게 설정
                if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                    cps = self.tm.excel_trading_service.choice_pick_system
                    cps._entered_round = self.tm.entered_round
                    cps._current_game_round = current_game_count
                    cps.skip_n_count = False
                    self.logger.info(f"[강제 진행] 초이스픽 시스템 업데이트: _entered_round={self.tm.entered_round}")
                self.analysis_complete.emit({
                    'game_state': game_state,
                    'previous_game_count': self.tm.game_count,
                    'new_result': True,  # Force new result processing
                    'force_process': True  # 새로운 플래그 추가
                })
                return
            
            # 게임 라운드가 변하지 않은 경우 (입장 후 첫 분석)
            entered_round = getattr(self.tm, 'entered_round', -1)
            if current_game_count == entered_round:
                # 게임 상태 체크 카운트 증가 처리
                if hasattr(self.tm, 'game_state_check_count'):
                    self.tm.game_state_check_count += 1
                    if self.tm.game_state_check_count > 15:  # 약 30초 이상 동일한 라운드를 감지하면
                        self.logger.info(f"[게임 결과 대기 초과] 15회({self.tm.game_state_check_count}회) 이상 동일 라운드 감지")
                else:
                    self.tm.game_state_check_count = 1
                
                self.logger.info(f"[GameAnalysisThread] 방 입장 직후 동일 라운드({current_game_count}={entered_round}) → new_result=False 처리")
                # consecutive_n_count 증가 방지를 위한 플래그 설정
                if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                    self.tm.excel_trading_service.choice_pick_system.skip_n_count = True
                    self.logger.info("[N카운트 증가 방지] 입장 직후 첫 게임은 N카운트 증가하지 않음")
                
                self.analysis_complete.emit({
                    'game_state': game_state,
                    'previous_game_count': self.tm.game_count,
                    'new_result': False
                })
                return
            elif current_game_count > entered_round:
                # 실제 새 결과가 들어왔을 때 플래그 해제
                self.logger.info(f"[새 결과 감지] 이전={entered_round}, 현재={current_game_count} → wait_first_result 해제")
                if hasattr(self.tm, 'wait_first_result'):
                    self.tm.wait_first_result = False
                if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                    self.tm.excel_trading_service.choice_pick_system.skip_n_count = False
                    if hasattr(self.tm.excel_trading_service.choice_pick_system, 'wait_first_result'):
                        self.tm.excel_trading_service.choice_pick_system.wait_first_result = False
                
                # 게임 대기 카운트 초기화
                if hasattr(self.tm, 'game_state_check_count'):
                    self.tm.game_state_check_count = 0

            # ✅ 기존 게임 카운트와 동일하면 새 결과 아님
            if current_game_count == self.tm.game_count and self.tm.game_count > 0:
                self.analysis_complete.emit({
                    'game_state': game_state,
                    'previous_game_count': self.tm.game_count,
                    'new_result': False
                })
                return

            # ✅ 새 결과가 있는 경우
            self.analysis_complete.emit({
                'game_state': game_state,
                'previous_game_count': self.tm.game_count,
                'new_result': True
            })

        except Exception as e:
            self.logger.error(f"게임 상태 분석 스레드 오류: {e}", exc_info=True)
            self.analysis_error.emit(f"게임 상태 분석 오류: {str(e)}")
            
    def stop(self):
        """스레드 중지 요청"""
        self.should_stop = True
