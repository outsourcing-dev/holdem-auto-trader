# utils/betting_worker.py
"""
베팅 실행 전용 워커 쓰레드
UI 블로킹 없이 베팅 로직 실행
"""

import time
import logging
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QTimer
from typing import Dict, Any


class BettingWorker(QThread):
    """베팅 실행 전용 워커 쓰레드 - UI 블로킹 방지"""
    
    # 시그널 정의
    betting_started = pyqtSignal(str, int, int)  # 베팅 시작 (pick, round, amount)
    betting_completed = pyqtSignal(bool, str, dict)  # 베팅 완료 (성공여부, 메시지, 결과)
    betting_progress = pyqtSignal(str)  # 베팅 진행 상황
    error_occurred = pyqtSignal(str)  # 에러 발생
    
    def __init__(self, trading_manager, logger=None):
        super().__init__()
        self.tm = trading_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # 베팅 큐 (단일 베팅만 처리)
        self.mutex = QMutex()
        self.current_bet_request = None
        self.is_processing = False
        
    def request_betting(self, pick: str, current_round: int, betting_round: int):
        """베팅 요청 추가"""
        try:
            self.mutex.lock()
            
            if self.is_processing:
                self.logger.warning("이미 베팅 처리 중 - 요청 무시")
                self.mutex.unlock()
                return False
            
            self.current_bet_request = {
                'pick': pick,
                'current_round': current_round,
                'betting_round': betting_round,
                'timestamp': time.time()
            }
            
            self.mutex.unlock()
            
            # 쓰레드가 실행 중이 아니면 시작
            if not self.isRunning():
                self.start()
            
            return True
            
        except Exception as e:
            self.mutex.unlock()
            self.logger.error(f"베팅 요청 오류: {e}")
            return False
    
    def run(self):
        """워커 쓰레드 메인 루프"""
        try:
            self.mutex.lock()
            
            if not self.current_bet_request or self.is_processing:
                self.mutex.unlock()
                return
            
            bet_request = self.current_bet_request.copy()
            self.current_bet_request = None
            self.is_processing = True
            
            self.mutex.unlock()
            
            # 베팅 실행
            self._execute_betting(bet_request)
            
        except Exception as e:
            self.logger.error(f"베팅 워커 실행 오류: {e}")
            self.error_occurred.emit(f"베팅 실행 중 오류: {e}")
        finally:
            self.mutex.lock()
            self.is_processing = False
            self.mutex.unlock()
    
    def _execute_betting(self, bet_request: dict):
        """베팅 실행 (별도 쓰레드에서)"""
        try:
            pick = bet_request['pick']
            current_round = bet_request['current_round']
            betting_round = bet_request['betting_round']
            
            self.logger.info(f"🎯 베팅 워커 실행: {pick} (라운드: {current_round} → {betting_round})")
            
            # 베팅 시작 시그널
            self.betting_started.emit(pick, current_round, betting_round)
            
            # 베팅 진행 상황 업데이트
            self.betting_progress.emit("베팅 조건 검증 중...")
            
            # 베팅 금액 계산
            bet_amount = self._get_bet_amount()
            
            self.betting_progress.emit(f"베팅 실행 중: {pick}, 금액: {bet_amount:,}원")
            
            # 실제 베팅 실행 (논블로킹 방식으로 호출)
            bet_success = self._place_bet_safe(pick, current_round, bet_amount)
            
            # 결과 처리
            if bet_success:
                result_data = {
                    'pick': pick,
                    'amount': bet_amount,
                    'round': betting_round,
                    'timestamp': time.time()
                }
                
                self.betting_completed.emit(True, f"베팅 성공: {pick}, {bet_amount:,}원", result_data)
                self.logger.info(f"✅ 베팅 성공: {pick} - {bet_amount:,}원")
                
                # 베팅 추적 시작
                self._start_result_tracking(pick, betting_round, bet_amount)
                
            else:
                self.betting_completed.emit(False, f"베팅 실패: {pick}", {})
                self.logger.warning(f"❌ 베팅 실패: {pick}")
                
        except Exception as e:
            self.logger.error(f"베팅 실행 오류: {e}")
            self.error_occurred.emit(f"베팅 실행 실패: {e}")
            self.betting_completed.emit(False, f"베팅 오류: {str(e)}", {})
    
    def _get_bet_amount(self) -> int:
        """베팅 금액 계산"""
        try:
            if hasattr(self.tm, 'excel_trading_service') and self.tm.excel_trading_service:
                from utils.trading_manager_helpers import get_widget_position
                widget_pos = get_widget_position(self.tm.main_window)
                return self.tm.excel_trading_service.get_current_bet_amount(widget_position=widget_pos)
            
            return 10000  # 기본값
            
        except Exception as e:
            self.logger.error(f"베팅 금액 계산 오류: {e}")
            return 10000
    
    def _place_bet_safe(self, pick: str, current_round: int, bet_amount: int) -> bool:
        """쓰레드 안전한 베팅 실행"""
        try:
            if not hasattr(self.tm, 'betting_service') or not self.tm.betting_service:
                self.logger.error("베팅 서비스가 초기화되지 않음")
                return False
            
            # 베팅 서비스 호출
            return self.tm.betting_service.place_bet(
                bet_type=pick,
                current_room_name=self.tm.current_room_name,
                game_count=current_round,
                is_trading_active=self.tm.is_trading_active,
                bet_amount=bet_amount
            )
            
        except Exception as e:
            self.logger.error(f"안전한 베팅 실행 오류: {e}")
            return False
    
    def _start_result_tracking(self, pick: str, betting_round: int, bet_amount: int):
        """베팅 결과 추적 시작"""
        try:
            # 게임 프로세서의 베팅 추적기에 등록
            if (hasattr(self.tm, 'game_processor') and 
                hasattr(self.tm.game_processor, 'betting_tracker')):
                
                betting_tracker = self.tm.game_processor.betting_tracker
                
                if not betting_tracker.is_waiting_for_result():
                    betting_tracker.start_betting_tracking(
                        bet_type=pick,
                        round_number=betting_round,
                        bet_amount=bet_amount,
                        room_name=self.tm.current_room_name
                    )
                    
                    self.logger.info(f"🎯 베팅 결과 추적 시작: {betting_round}번째 게임")
                    
        except Exception as e:
            self.logger.error(f"베팅 결과 추적 시작 오류: {e}")
    
    def is_betting_in_progress(self) -> bool:
        """베팅 진행 중인지 확인"""
        self.mutex.lock()
        result = self.is_processing
        self.mutex.unlock()
        return result


class AsyncBettingManager:
    """비동기 베팅 관리자 - 메인 쓰레드에서 사용"""
    
    def __init__(self, trading_manager, logger=None):
        self.tm = trading_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # 베팅 워커 생성
        self.betting_worker = BettingWorker(trading_manager, logger)
        
        # 시그널 연결
        self.betting_worker.betting_started.connect(self._on_betting_started)
        self.betting_worker.betting_completed.connect(self._on_betting_completed)
        self.betting_worker.betting_progress.connect(self._on_betting_progress)
        self.betting_worker.error_occurred.connect(self._on_betting_error)
        
        # 베팅 결과 대기 타이머
        self.result_timeout_timer = QTimer()
        self.result_timeout_timer.setSingleShot(True)
        self.result_timeout_timer.timeout.connect(self._on_result_timeout)
        
    def request_betting(self, pick: str, current_round: int, betting_round: int) -> bool:
        """베팅 요청"""
        try:
            if self.betting_worker.is_betting_in_progress():
                self.logger.warning("이미 베팅 진행 중")
                return False
            
            return self.betting_worker.request_betting(pick, current_round, betting_round)
            
        except Exception as e:
            self.logger.error(f"베팅 요청 오류: {e}")
            return False
    
    def _on_betting_started(self, pick: str, current_round: int, betting_round: int):
        """베팅 시작 처리"""
        self.logger.info(f"🎯 베팅 시작: {pick} (라운드 {betting_round})")
        
        # UI 업데이트
        if hasattr(self.tm.main_window, 'update_betting_status'):
            self.tm.main_window.update_betting_status(
                pick=pick,
                status="베팅 진행 중..."
            )
    
    def _on_betting_completed(self, success: bool, message: str, result_data: dict):
        """베팅 완료 처리"""
        self.logger.info(f"베팅 완료: {message}")
        
        if success:
            # 베팅 성공 - 결과 대기 타이머 시작 (60초)
            self.result_timeout_timer.start(60000)
            
            # UI 업데이트
            if hasattr(self.tm.main_window, 'update_betting_status'):
                self.tm.main_window.update_betting_status(
                    pick=result_data.get('pick', ''),
                    bet_amount=result_data.get('amount', 0),
                    status="결과 대기 중..."
                )
        else:
            # 베팅 실패 처리
            self._handle_betting_failure(message)
    
    def _on_betting_progress(self, message: str):
        """베팅 진행 상황 업데이트"""
        self.logger.debug(f"베팅 진행: {message}")
        
        # UI 상태 표시
        if hasattr(self.tm.main_window, 'update_status'):
            self.tm.main_window.update_status(message)
    
    def _on_betting_error(self, error_message: str):
        """베팅 오류 처리"""
        self.logger.error(f"베팅 오류: {error_message}")
        
        # UI 오류 표시
        if hasattr(self.tm.main_window, 'show_error'):
            self.tm.main_window.show_error(f"베팅 실패: {error_message}")
    
    def _on_result_timeout(self):
        """베팅 결과 타임아웃 처리"""
        self.logger.warning("베팅 결과 타임아웃 - 다음 기회 대기")
        
        # 베팅 상태 초기화
        if hasattr(self.tm, 'betting_service'):
            self.tm.betting_service.clear_pending_bet()
    
    def _handle_betting_failure(self, message: str):
        """베팅 실패 처리"""
        self.logger.warning(f"베팅 실패 처리: {message}")
        
        # 베팅 추적기 초기화
        if (hasattr(self.tm, 'game_processor') and 
            hasattr(self.tm.game_processor, 'betting_tracker')):
            self.tm.game_processor.betting_tracker.reset_tracking()
    
    def cleanup(self):
        """리소스 정리"""
        try:
            self.result_timeout_timer.stop()
            
            if self.betting_worker.isRunning():
                self.betting_worker.quit()
                if not self.betting_worker.wait(3000):
                    self.betting_worker.terminate()
                    
        except Exception as e:
            self.logger.error(f"베팅 매니저 정리 오류: {e}")