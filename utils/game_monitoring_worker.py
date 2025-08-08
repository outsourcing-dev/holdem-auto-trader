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
        
        # 🔥 방 입장 시점의 초기 결과 데이터 저장
        self.initial_room_results = []  # 방 입장 시 서버에 보낸 초기 데이터
        
    def start_monitoring(self, room_data: dict):
        """모니터링 시작"""
        try:
            self.mutex.lock()
            
            self.current_room_id = room_data.get('room_id')
            self.current_room_name = room_data.get('room_name')
            self.last_game_count = 0
            self.first_check_after_entry = False  # False로 초기화하여 첫 베팅 기회 놓치지 않음
            self.betting_in_progress = False
            
            # 방 입장 시간 기록 (안정화 대기용)
            self.room_entry_time = time.time()
            self.min_stabilization_time = 5.0  # 최소 5초 대기로 단축
            
            # 🔥 방 입장 후 첫 라운드 대기 플래그
            self.wait_for_first_new_result = True
            self.entry_round_number = 0  # 입장 시점의 라운드 번호 저장
            self.expected_streak = room_data.get('streak_count', 0)  # 예상 연패 수
            
            # 🔥 방 입장 시점의 초기 결과 데이터 저장 (서버에서 받은 원본 데이터)
            if 'recent_results' in room_data:
                # R/B를 P/B로 변환 (서버 형식과 동일하게)
                self.initial_room_results = []
                for result in room_data['recent_results']:
                    if result == 'R':  # Banker
                        self.initial_room_results.append('B')
                    elif result == 'B':  # Player
                        self.initial_room_results.append('P')
                self.logger.info(f"📝 초기 결과 데이터 저장: {len(self.initial_room_results)}개")
            else:
                self.initial_room_results = []
            
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
            self.logger.debug(f"🎯 [워커] 게임 상태 체크 #{self.last_check_time:.0f}:")
            self.logger.debug(f"  - 방 이름: {self.current_room_name}")
            self.logger.debug(f"  - 완료된 라운드: {current_round}")
            self.logger.debug(f"  - 진행 중인 게임: {current_game}")
            self.logger.debug(f"  - 마지막 체크 라운드: {self.last_game_count}")
            self.logger.debug(f"  - 최신 결과: {latest_result}")
            self.logger.debug(f"  - 베팅 진행 중: {self.betting_in_progress}")
            self.logger.debug(f"  - 베팅 추적기 대기 중: {self.tm.game_processor.betting_tracker.is_waiting_for_result() if hasattr(self.tm.game_processor, 'betting_tracker') else 'N/A'}")
            
            # 🔥 방 입장 후 첫 라운드 대기 처리
            if self.wait_for_first_new_result:
                if self.entry_round_number == 0:
                    # 입장 시점 라운드 번호 저장
                    self.entry_round_number = current_round
                    self.logger.info(f"📝 방 입장 시점 라운드: {self.entry_round_number}")
                    self.logger.info(f"📝 예상 연패 수: {self.expected_streak}")
                    self.logger.info(f"📝 현재 결과 데이터: {filtered_results[-10:] if len(filtered_results) >= 10 else filtered_results}")
                    
                    # 🔥 초기 데이터가 없으면 현재 데이터 저장 (추가 안전장치)
                    if not self.initial_room_results and filtered_results:
                        self.initial_room_results = filtered_results.copy()
                        self.logger.info(f"🔥 방 입장 시점 데이터 저장: {len(self.initial_room_results)}개")
                    
                    return
                elif current_round > self.entry_round_number:
                    # 새로운 라운드 발생 - 연패 체크 시작
                    self.logger.info(f"🆕 방 입장 후 첫 새로운 라운드 감지: {self.entry_round_number} → {current_round}")
                    self.logger.info(f"📊 연패 체크 시작 - 예상: {self.expected_streak}연패")
                    self.logger.info(f"📊 현재 결과: {filtered_results[-10:] if len(filtered_results) >= 10 else filtered_results}")
                    self.wait_for_first_new_result = False
                    
                    # 🔥 연패 체크는 GameProcessor의 베팅 전에 수행
                    # 여기서는 체크하지 않고 베팅 기회로 넘어감
                    self.logger.info(f"✅ 새 라운드 시작 - 연패 검증은 베팅 시점에 GameProcessor에서 수행")
                    self.logger.info(f"📊 예상 연패: {self.expected_streak}, 현재 결과: {len(filtered_results)}개")
                else:
                    # 아직 새 라운드 안 나옴 - 대기
                    self.logger.debug(f"⏳ 새 라운드 대기 중... (현재: {current_round}, 입장: {self.entry_round_number})")
                    return
            
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
                # 🔥 베팅 추적기가 대기 중이고 결과가 없는 경우
                elif (hasattr(self.tm.game_processor, 'betting_tracker') and 
                      self.tm.game_processor.betting_tracker.is_waiting_for_result()):
                    # 베팅한 라운드 확인
                    bet_round = self.tm.game_processor.betting_tracker.get_bet_round()
                    
                    # 현재 라운드가 베팅한 라운드와 일치하는지 확인
                    if bet_round and current_round == bet_round:
                        # latest_result가 없으면 다시 파싱 시도
                        if not latest_result:
                            self.logger.warning(f"⚠️ 라운드 {current_round} 결과 없음 - 재파싱 시도")
                            # 게임 상태 다시 가져오기 (캐시 무시)
                            self.last_game_state = None
                            self.last_game_state_time = 0
                            refreshed_state = self._get_game_state_safe()
                            if refreshed_state:
                                latest_result = refreshed_state.get('latest_result', '')
                                if latest_result and latest_result in ['P', 'B', 'T']:
                                    result_data = {
                                        'round_number': current_round,
                                        'latest_result': latest_result,
                                        'current_game': current_game
                                    }
                                    self.logger.info(f"🎲 재파싱 성공 - 게임 결과 발송: 라운드 {current_round}, 결과 {latest_result}")
                                    self.game_result_received.emit(result_data)
                                    return
                        return  # 결과 대기
                    elif bet_round and current_round > bet_round:
                        # 베팅한 라운드를 지나쳤으면 타임아웃으로 처리
                        self.logger.error(f"❌ 베팅 라운드 {bet_round} 결과 누락 - 현재 {current_round}")
                        # 빈 결과로 처리하여 타임아웃 유도
                        result_data = {
                            'round_number': bet_round,
                            'latest_result': '',  # 빈 결과
                            'current_game': current_game
                        }
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
            
            # 메인 쓰레드가 아닌 곳에서 안전하게 호출
            # 🔥 더 많은 데이터 요청 (연패 추적을 위해)
            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=self.current_room_id,
                room_name=self.current_room_name,
                log_always=False,
                desired_pb_count=None  # 🔥 전체 데이터 요청 (None = 모든 데이터)
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
            
            # 방 입장 후 안정화 시간 체크 (5초로 단축)
            if hasattr(self, 'room_entry_time'):
                time_since_entry = time.time() - self.room_entry_time
                min_wait_time = 5.0  # 10초에서 5초로 단축
                if time_since_entry < min_wait_time:
                    remaining = min_wait_time - time_since_entry
                    self.status_updated.emit(f"방 안정화 대기 중... ({remaining:.1f}초)")
                    self.logger.info(f"⏳ 방 입장 후 안정화 대기 ({time_since_entry:.1f}/{min_wait_time}초)")
                    return
            
            # first_check_after_entry 플래그 제거 - 첫 베팅 기회를 놓치지 않도록
            # 대신 방 입장 후 최소 대기 시간만 체크
            
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
        
        # 베팅 플래그 리셋 확인 로그
        self.logger.info(f"✅ betting_in_progress 플래그 리셋 완료: {self.betting_in_progress}")
    
    def reset_betting_flag(self):
        """베팅 플래그 강제 리셋 (타임아웃 등의 경우)"""
        was_in_progress = self.betting_in_progress
        self.betting_in_progress = False
        if was_in_progress:
            self.logger.info("🔄 betting_in_progress 플래그 강제 리셋")
    
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
    
    def _check_streak_maintenance(self, filtered_results: list) -> bool:
        """초이스픽 예측 시스템 기반 연패 유지 여부 체크"""
        try:
            # 🔥 초기 데이터와 현재 데이터 합치기
            combined_results = []
            if self.initial_room_results:
                # 초기 데이터가 있으면 사용
                combined_results = self.initial_room_results.copy()
                # 새로운 결과가 있으면 추가 (중복 제거)
                current_data_start = len(self.initial_room_results)
                if len(filtered_results) > 15:  # 현재 데이터가 15개보다 많으면
                    # 초기 데이터 이후의 새 결과만 추가
                    new_results = filtered_results[current_data_start:]
                    if new_results:
                        combined_results.extend(new_results)
                        self.logger.info(f"🔄 초기 {len(self.initial_room_results)}개 + 새 결과 {len(new_results)}개 = 총 {len(combined_results)}개")
                    else:
                        # 새 결과가 없으면 현재 데이터 사용
                        combined_results = filtered_results
                else:
                    # 현재 데이터가 15개 이하면 초기 데이터만 사용
                    self.logger.info(f"📝 초기 데이터 {len(combined_results)}개 사용")
            else:
                # 초기 데이터가 없으면 현재 데이터만 사용
                combined_results = filtered_results
                self.logger.info(f"⚠️ 초기 데이터 없음, 현재 데이터 {len(combined_results)}개만 사용")
            
            self.logger.info("🔍 초이스픽 연패 체크 시작:")
            self.logger.info(f"  - 예상 연패: {self.expected_streak}")
            self.logger.info(f"  - 전체 결과 데이터 수: {len(combined_results)}")
            self.logger.info(f"  - 최근 10개 결과: {combined_results[-10:] if len(combined_results) >= 10 else combined_results}")
            
            # 초이스픽 예측을 위해 최소 15개 데이터 필요
            if not combined_results or len(combined_results) < 15:
                self.logger.warning(f"초이스픽 연패 체크 불가: 데이터 부족 ({len(combined_results)}개, 최소 15개 필요)")
                return True  # 데이터 부족 시 일단 유지로 간주
            
            # 서버의 초이스픽 연패 체크 사용
            if hasattr(self.tm, 'server_client'):
                self.logger.info(f"📤 서버 초이스픽 연패 계산 요청:")
                self.logger.info(f"  - room_id: {self.current_room_id}")
                self.logger.info(f"  - room_name: {self.current_room_name}")
                self.logger.info(f"  - 전체 결과 개수: {len(combined_results)}")
                
                streak_data = self.tm.server_client.calculate_streak(
                    self.current_room_id,
                    self.current_room_name,
                    combined_results  # 합쳐진 전체 데이터 전송
                )
                
                if streak_data:
                    server_streak = streak_data.get('current_streak', 0)
                    self.logger.info(f"📊 초이스픽 예측 실패 연패: {server_streak}회")
                    
                    # 서버가 0을 반환 = 예측 성공 = 연패 끊김
                    if server_streak == 0:
                        self.logger.warning(f"❌ 초이스픽 예측 성공 - 연패 끊김 (방 나가기)")
                        return False  # 방 나가기
                    
                    # 연패가 유지되는지 확인
                    if server_streak >= self.expected_streak:
                        self.logger.info(f"✅ 초이스픽 연패 유지 중: {server_streak}연패 >= {self.expected_streak}연패")
                        return True
                    else:
                        self.logger.warning(f"❌ 초이스픽 연패 부족: {server_streak}연패 < {self.expected_streak}연패")
                        return False
                else:
                    self.logger.warning("서버 응답 없음 - 일단 유지")
                    return True
            else:
                self.logger.warning("서버 클라이언트 없음 - 일단 유지")
                return True
                
        except Exception as e:
            self.logger.error(f"초이스픽 연패 체크 오류: {e}")
            return True  # 오류 시 일단 유지로 간주