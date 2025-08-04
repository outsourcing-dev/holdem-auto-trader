# utils/game_monitoring_worker.py
"""
게임 모니터링 전용 워커 쓰레드
UI 블로킹 없이 iframe 체크 및 베팅 로직 실행
"""

import time
import logging
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition
from typing import Dict, Any, Optional


class GameMonitoringWorker(QThread):
    """게임 모니터링 전용 워커 쓰레드 - UI 블로킹 방지"""
    
    # 시그널 정의 (메인 쓰레드와 통신)
    game_state_updated = pyqtSignal(dict)  # 게임 상태 업데이트
    betting_requested = pyqtSignal(str, int, int)  # 베팅 요청 (pick, round, betting_round)
    betting_completed = pyqtSignal(bool, str)  # 베팅 완료 (성공여부, 메시지)
    game_result_received = pyqtSignal(dict)  # 게임 결과 수신
    room_exit_requested = pyqtSignal(str)  # 방 나가기 요청
    error_occurred = pyqtSignal(str)  # 에러 발생
    status_updated = pyqtSignal(str)  # 상태 업데이트
    
    def __init__(self, trading_manager, logger=None):
        super().__init__()
        self.tm = trading_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # 쓰레드 제어 변수
        self._is_running = False
        self._is_paused = False
        self.monitoring_interval = 5.0  # 5초 간격 (게임 진행 시간 고려)
        
        # 쓰레드 동기화
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        
        # 상태 변수
        self.current_room_id = None
        self.current_room_name = None
        self.last_game_count = 0
        self.last_check_time = 0
        
        # 베팅 관련 플래그
        self.betting_in_progress = False
        self.first_check_after_entry = True
        
        # 캐싱 변수 (중복 파싱 방지)
        self.last_game_state = None
        self.last_game_state_time = 0
        self.cache_timeout = 3.0  # 3초간 캐시 유지
        
    def start_monitoring(self, room_data: dict):
        """모니터링 시작"""
        try:
            self.mutex.lock()
            
            self.current_room_id = room_data.get('room_id')
            self.current_room_name = room_data.get('room_name')
            self.last_game_count = 0
            self.first_check_after_entry = True
            self.betting_in_progress = False
            
            self._is_running = True
            self._is_paused = False
            
            self.mutex.unlock()
            
            if not self.isRunning():
                self.start()
            else:
                self.condition.wakeAll()
                
            self.logger.info(f"🔍 게임 모니터링 워커 시작: {self.current_room_name}")
            
        except Exception as e:
            self.mutex.unlock()
            self.logger.error(f"모니터링 시작 오류: {e}")
            self.error_occurred.emit(f"모니터링 시작 실패: {e}")
    
    def pause_monitoring(self):
        """모니터링 일시정지"""
        self.mutex.lock()
        self._is_paused = True
        self.mutex.unlock()
        self.logger.info("⏸️ 게임 모니터링 일시정지")
    
    def resume_monitoring(self):
        """모니터링 재개"""
        self.mutex.lock()
        self._is_paused = False
        self.condition.wakeAll()
        self.mutex.unlock()
        self.logger.info("▶️ 게임 모니터링 재개")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        try:
            self.mutex.lock()
            self._is_running = False
            self._is_paused = False
            self.condition.wakeAll()
            self.mutex.unlock()
            
            # 쓰레드가 실행 중이면 종료 대기
            if self.isRunning():
                if not self.wait(3000):  # 3초 대기
                    self.terminate()  # 강제 종료
                    if not self.wait(1000):  # 1초 더 대기
                        self.logger.warning("워커 쓰레드 강제 종료됨")
            
            self.logger.info("🛑 게임 모니터링 워커 중지")
            
        except Exception as e:
            self.logger.error(f"모니터링 중지 오류: {e}")
    
    def run(self):
        """워커 쓰레드 메인 루프"""
        self.logger.info("🚀 게임 모니터링 워커 쓰레드 시작")
        
        try:
            while True:
                self.mutex.lock()
                
                # 중지 요청 확인
                if not self._is_running:
                    self.mutex.unlock()
                    break
                
                # 일시정지 상태 확인
                if self._is_paused:
                    self.condition.wait(self.mutex, 1000)  # 1초 대기
                    self.mutex.unlock()
                    continue
                
                self.mutex.unlock()
                
                # 게임 모니터링 실행
                self._monitor_game_state()
                
                # 다음 체크까지 대기 (논블로킹)
                self.msleep(int(self.monitoring_interval * 1000))
                
        except Exception as e:
            self.logger.error(f"워커 쓰레드 실행 오류: {e}")
            self.error_occurred.emit(f"모니터링 중 오류: {e}")
        
        self.logger.info("🏁 게임 모니터링 워커 쓰레드 종료")
    
    def _monitor_game_state(self):
        """게임 상태 모니터링 (별도 쓰레드에서 실행)"""
        try:
            # 현재 타겟 방 확인
            if not self.tm.current_target_room or not self.tm.is_trading_active:
                return
            
            # 베팅 진행 중이면 건너뜀 (단, 베팅 결과 대기 중인 경우는 계속 모니터링)
            betting_tracker_waiting = (hasattr(self.tm.game_processor, 'betting_tracker') and 
                                     self.tm.game_processor.betting_tracker.is_waiting_for_result())
            
            if self.betting_in_progress and not betting_tracker_waiting:
                self.logger.debug("베팅 진행 중 - 모니터링 건너뜀")
                return
            
            current_time = time.time()
            
            # 너무 빠른 연속 체크 방지
            if current_time - self.last_check_time < self.monitoring_interval:
                return
            
            self.last_check_time = current_time
            
            # 🔥 iframe에서 게임 상태 가져오기 (별도 쓰레드에서 안전하게) - 충분한 데이터 요청
            game_state = self._get_game_state_safe()
            
            if not game_state:
                return
            
            # 게임 상태 업데이트 시그널 발송
            self.game_state_updated.emit(game_state)
            
            current_round = game_state.get('round', 0)
            current_game = game_state.get('current_game', 0)
            latest_result = game_state.get('latest_result', '')
            filtered_results = game_state.get('filtered_results', [])
            
            # 🔍 디버깅: 게임 상태 값 확인 (매번 로그 기록)
            self.logger.info(f"🎯 [워커] 게임 상태 체크 #{self.last_check_time:.0f}:")
            self.logger.info(f"  - 방 이름: {self.current_room_name}")
            self.logger.info(f"  - 완료된 라운드: {current_round}")
            self.logger.info(f"  - 진행 중인 게임: {current_game}")
            self.logger.info(f"  - 마지막 체크 라운드: {self.last_game_count}")
            self.logger.info(f"  - 최신 결과: {latest_result}")
            self.logger.info(f"  - 베팅 진행 중: {self.betting_in_progress}")
            self.logger.info(f"  - 베팅 추적기 대기 중: {self.tm.game_processor.betting_tracker.is_waiting_for_result() if hasattr(self.tm.game_processor, 'betting_tracker') else 'N/A'}")
            
            # 🔥 게임 결과 처리와 베팅 기회 분리
            # 1. 새로운 라운드 결과 처리 (베팅 결과 추적을 위해)
            if current_round > self.last_game_count:
                self.logger.info(f"🆕 새로운 라운드 감지: {self.last_game_count} → {current_round}")
                
                # 게임 결과 처리 - 베팅 추적기가 대기 중일 수 있으므로 항상 발송
                if latest_result and latest_result in ['P', 'B', 'T']:
                    result_data = {
                        'round_number': current_round,
                        'latest_result': latest_result,
                        'current_game': current_game
                    }
                    self.logger.info(f"🎲 게임 결과 발송: 라운드 {current_round}, 결과 {latest_result}")
                    self.game_result_received.emit(result_data)
                
                self.last_game_count = current_round
            
            # 2. 베팅 추적기 대기 중인 결과도 추가로 발송
            elif (latest_result and latest_result in ['P', 'B', 'T'] and 
                  hasattr(self.tm.game_processor, 'betting_tracker') and 
                  self.tm.game_processor.betting_tracker.is_waiting_for_result()):
                
                # 베팅 대기 중이면 현재 라운드 결과도 처리
                result_data = {
                    'round_number': current_round,
                    'latest_result': latest_result,
                    'current_game': current_game
                }
                self.logger.info(f"🎯 베팅 대기 중 - 현재 라운드 결과 재발송: 라운드 {current_round}, 결과 {latest_result}")
                self.game_result_received.emit(result_data)
            
            # 3. 베팅 기회 확인 (current_game 기반)
            if current_game > 0 and not self.betting_in_progress:
                self.logger.info(f"🎯 current_game 기반 베팅 기회: {current_game}")
                betting_round = current_game
                self._check_betting_opportunity_async(filtered_results, current_round, betting_round)
            elif current_round > 0 and not self.betting_in_progress and current_game == 0:
                # current_game이 없으면 다음 라운드 베팅 시도
                betting_round = current_round + 1
                self._check_betting_opportunity_async(filtered_results, current_round, betting_round)
            
        except Exception as e:
            self.logger.error(f"게임 상태 모니터링 오류: {e}")
            self.error_occurred.emit(f"게임 모니터링 오류: {e}")
    
    def _get_game_state_safe(self) -> Optional[Dict[str, Any]]:
        """쓰레드 안전한 게임 상태 조회 (캐싱 포함)"""
        try:
            current_time = time.time()
            
            # 캐시가 유효한 경우 캐시된 데이터 반환
            if (self.last_game_state and 
                self.last_game_state_time and 
                current_time - self.last_game_state_time < self.cache_timeout):
                self.logger.debug(f"캐시된 게임 상태 사용 (경과: {current_time - self.last_game_state_time:.1f}초)")
                return self.last_game_state
            
            if not hasattr(self.tm, 'game_monitoring_service') or not self.tm.game_monitoring_service:
                return None
            
            # 메인 쓰레드가 아닌 곳에서 안전하게 호출 - 서버 요구사항: 최소 15개 데이터
            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=self.current_room_id,
                room_name=self.current_room_name,
                log_always=False,
                desired_pb_count=15  # 서버 요구사항: 15개 데이터 필요
            )
            
            # 캐시 업데이트
            if game_state:
                self.last_game_state = game_state
                self.last_game_state_time = current_time
            
            return game_state
            
        except Exception as e:
            self.logger.debug(f"게임 상태 조회 오류: {e}")
            return None
    
    def _check_betting_opportunity_async(self, filtered_results: list, current_round: int, betting_round: int):
        """비동기 베팅 기회 확인"""
        try:
            # 🔍 베팅 조건 상세 로깅
            self.logger.info(f"🎯 베팅 조건 확인:")
            self.logger.info(f"  - filtered_results 개수: {len(filtered_results)}")
            self.logger.info(f"  - current_round: {current_round}")
            self.logger.info(f"  - betting_round: {betting_round}")
            self.logger.info(f"  - first_check_after_entry: {self.first_check_after_entry}")
            self.logger.info(f"  - betting_in_progress: {self.betting_in_progress}")
            
            # 기본 조건 확인 - 서버 요구사항: 최소 15개 데이터
            if len(filtered_results) < 15:
                self.logger.info(f"❌ 베팅 조건 미충족: 결과 데이터 부족 ({len(filtered_results)}/15)")
                return
            
            if self.first_check_after_entry:
                self.first_check_after_entry = False
                self.status_updated.emit("방 입장 직후 - 다음 라운드 대기")
                self.logger.info("❌ 베팅 조건 미충족: 방 입장 직후")
                return
            
            if betting_round <= 0:
                self.logger.info(f"❌ 베팅 조건 미충족: betting_round가 0 이하 ({betting_round})")
                return
            
            self.logger.info("✅ 모든 베팅 조건 충족 - 서버 예측값 요청")
            
            # 서버 예측값 요청 (논블로킹)
            self._request_prediction_async(filtered_results, current_round, betting_round)
            
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")
    
    def _request_prediction_async(self, filtered_results: list, current_round: int, betting_round: int):
        """비동기 예측값 요청"""
        try:
            start_time = time.time()
            
            # 서버 예측값 요청 (상세 로깅)
            self.logger.info(f"🔮 워커 예측값 요청:")
            self.logger.info(f"  - 방 ID: {self.current_room_id}")
            self.logger.info(f"  - 결과 개수: {len(filtered_results)}개")
            self.logger.info(f"  - 최근 결과: {filtered_results[-10:] if len(filtered_results) >= 10 else filtered_results}")
            self.logger.info(f"  - current_round: {current_round}")
            self.logger.info(f"  - betting_round: {betting_round}")
            
            next_pick = self.tm.server_client.get_next_prediction(
                self.current_room_id, 
                filtered_results
            )
            
            request_time = time.time() - start_time
            
            self.logger.info(f"🔮 워커 서버 응답: {next_pick} ({request_time:.2f}초)")
            self.status_updated.emit(f"서버 응답: {next_pick} ({request_time:.2f}초)")
            
            if next_pick in ['P', 'B']:
                self.logger.info(f"✅ 베팅 예측: {next_pick} - 베팅 요청 시그널 발송")
                
                # 베팅 요청 시그널 발송 (메인 쓰레드에서 처리)
                self.betting_requested.emit(next_pick, current_round, betting_round)
                self.betting_in_progress = True
            else:
                self.logger.info(f"❌ 베팅 안함: 예측값 '{next_pick}'는 P, B가 아님")
                
        except Exception as e:
            self.logger.error(f"예측값 요청 오류: {e}")
            self.error_occurred.emit(f"서버 예측 실패: {e}")
    
    def on_betting_completed(self, success: bool, message: str):
        """베팅 완료 처리 (메인 쓰레드에서 호출)"""
        self.betting_in_progress = False
        self.status_updated.emit(f"베팅 완료: {message}")
        
        if not success:
            self.logger.warning(f"베팅 실패: {message}")
    
    def update_room_info(self, room_data: dict):
        """방 정보 업데이트"""
        self.mutex.lock()
        self.current_room_id = room_data.get('room_id')
        self.current_room_name = room_data.get('room_name')
        self.mutex.unlock()
    
    def is_monitoring(self) -> bool:
        """모니터링 중인지 확인"""
        self.mutex.lock()
        result = self._is_running and not self._is_paused
        self.mutex.unlock()
        return result