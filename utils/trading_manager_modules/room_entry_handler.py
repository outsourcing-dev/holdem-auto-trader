# utils/trading_manager_modules/room_entry_handler.py
import time
import logging
from PyQt6.QtCore import QTimer


class RoomEntryHandler:
    """방 입장 및 관리 전담 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger
        self.iframe_timer = None

    def execute_room_entry(self, streak_data: dict):
        """방 입장 후 웹소켓 일시정지 및 iframe 기반 베팅"""
        try:
            room_name = streak_data.get('room_name', '')
            room_id = streak_data.get('room_id', '')
            expected_streak = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🚪 방 입장 실행: {room_name} ({expected_streak}연패)")
            
            # 1. 웹소켓 일시정지
            self._pause_websocket_monitoring()
            
            # 2. 방 입장 시도
            if hasattr(self.tm.room_entry_service, 'enter_room_by_name'):
                success = self.tm.room_entry_service.enter_room_by_name(room_name)
            else:
                success = self._fallback_room_entry(room_name)
            
            if success:
                self.logger.info(f"✅ 방 입장 성공: {room_name}")
                
                # 3. 방 로딩 대기
                time.sleep(3)
                
                # 🔥 게임 수 조건 확인
                if not self._check_game_count_condition(room_id, room_name):
                    self.logger.warning(f"⚠️ 게임 수 조건 미충족 - 방 나가기")
                    
                    # 🔥 조건 미충족 방을 제외 리스트에 추가 (5분간)
                    if room_id:
                        self.tm.excluded_rooms[room_id] = {
                            'timestamp': time.time(),
                            'reason': 'condition_fail'
                        }
                        self.logger.info(f"🚫 조건 미충족 방 제외 리스트에 추가: {room_id} (5분간)")
                    
                    # 방 나가기
                    if hasattr(self.tm, 'game_monitoring_service'):
                        self.tm.game_monitoring_service.close_current_room()
                    # 웹소켓 재개
                    self._resume_websocket_monitoring()
                    self.tm.room_entry_in_progress = False
                    self.tm.is_entering_room = False
                    # 다시 연패 방 찾기
                    self.tm.streak_handler.return_to_streak_monitoring()
                    return
                
                # 4. 현재 방 정보 설정
                self.tm.current_room_name = room_name
                self.tm.current_target_room = streak_data
                self.tm.room_entry_in_progress = False
                
                # 5. iframe 기반 게임 모니터링 시작
                self._start_iframe_game_monitoring(streak_data)
                
            else:
                self.logger.warning(f"❌ 방 입장 실패: {room_name}")
                # 실패 시 웹소켓 재개
                self._resume_websocket_monitoring()
                self.tm.room_entry_in_progress = False
                self.tm.is_entering_room = False
                
        except Exception as e:
            self.logger.error(f"방 입장 실행 오류: {e}")
            self._resume_websocket_monitoring()
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False

    def _pause_websocket_monitoring(self):
        """웹소켓 모니터링 일시정지"""
        try:
            if hasattr(self.tm, 'websocket_manager') and self.tm.websocket_manager.websocket_service:
                # 메시지 수집 타이머만 정지 (연결은 유지)
                if hasattr(self.tm.websocket_manager.websocket_service, 'message_collection_timer'):
                    self.tm.websocket_manager.websocket_service.message_collection_timer.stop()
                    self.logger.info("⏸️ 웹소켓 메시지 수집 일시정지")
        except Exception as e:
            self.logger.error(f"웹소켓 일시정지 오류: {e}")

    def _resume_websocket_monitoring(self):
        """웹소켓 모니터링 재개"""
        try:
            if hasattr(self.tm, 'websocket_manager') and self.tm.websocket_manager.websocket_service:
                # 메시지 수집 재시작
                self.tm.websocket_manager.websocket_service._start_message_collection()
                self.logger.info("▶️ 웹소켓 메시지 수집 재개")
        except Exception as e:
            self.logger.error(f"웹소켓 재개 오류: {e}")

    def _start_iframe_game_monitoring(self, streak_data: dict):
        """iframe 기반 게임 모니터링 시작"""
        try:
            # 게임 상태 초기화
            self.tm.game_count = 0
            self.tm.result_count = 0
            self.tm.processed_rounds = set()
            
            # 🔥 입장 직후 첫 베팅 플래그 설정
            self.tm.first_bet_after_entry = True
            
            # iframe 모니터링 타이머 생성
            self.iframe_timer = QTimer()
            self.iframe_timer.timeout.connect(self._monitor_game_from_iframe)  # 🔥 streak_data 제거
            self.iframe_timer.start(2000)  # 2초마다 확인
            
            self.logger.info("📊 iframe 기반 게임 모니터링 시작")
            
            # 첫 번째 체크 즉시 실행
            QTimer.singleShot(500, self._monitor_game_from_iframe)  # 🔥 streak_data 제거
            
        except Exception as e:
            self.logger.error(f"iframe 모니터링 시작 오류: {e}")

    def _monitor_game_from_iframe(self):
        """iframe에서 게임 상태 모니터링 및 베팅 처리"""
        try:
            if not self.tm.is_trading_active or not self.tm.current_target_room:
                self._stop_iframe_monitoring()
                return
            
            # 🔥 현재 타겟 방 정보에서 가져오기
            streak_data = self.tm.current_target_room
            if not streak_data:
                self.logger.debug("현재 타겟 방 정보 없음 - iframe 모니터링 중지")
                self._stop_iframe_monitoring()
                return
                
            room_id = streak_data.get('room_id', '')
            room_name = streak_data.get('room_name', '')
            
            # iframe에서 현재 게임 상태 가져오기
            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=room_name,
                log_always=False,
                desired_pb_count=15
            )
            
            if not game_state:
                return
            
            current_round = game_state.get('round', 0)
            current_game = game_state.get('current_game', 0)  # 🔥 현재 진행 중인 게임 번호
            latest_result = game_state.get('latest_result', '')
            filtered_results = game_state.get('filtered_results', [])
            
            # 새로운 라운드 감지
            if current_round > self.tm.game_count:
                self.logger.info(f"🎮 새 라운드 감지: 완료된 게임 {current_round}, 진행 중인 게임 {current_game}")
                
                # 게임 결과 처리 (GameProcessor의 _handle_game_result 호출)
                if latest_result and latest_result in ['P', 'B', 'T']:
                    game_data = {
                        'round_number': current_round,
                        'latest_result': latest_result,
                        'current_game': current_game  # 🔥 현재 진행 중인 게임 번호 추가
                    }
                    
                    # GameProcessor의 결과 처리 메서드 호출
                    if hasattr(self.tm, 'game_processor'):
                        self.tm.game_processor._handle_game_result(game_data)
                
                # 게임 카운트 업데이트
                self.tm.game_count = current_round
                
                # 베팅 기회 확인
                if not self.tm.betting_service.has_bet_current_round:
                    self._check_betting_opportunity(filtered_results, room_id, current_round, current_game)
                    
        except Exception as e:
            self.logger.error(f"iframe 모니터링 오류: {e}")

    def _check_betting_opportunity(self, filtered_results: list, room_id: str, current_round: int, current_game: int = None):
        """베팅 기회 확인 및 실행"""
        try:
            if len(filtered_results) < 10:
                return
            
            # 🔥 현재 타겟 방이 맞는지 다시 확인
            if not self.tm.current_target_room or self.tm.current_target_room.get('room_id') != room_id:
                self.logger.debug(f"타겟 방 불일치 - 베팅 취소 (요청: {room_id}, 현재: {self.tm.current_target_room})")
                return
                
            # 🔥 입장 직후 첫 베팅인 경우 추가 대기
            if hasattr(self.tm, 'first_bet_after_entry'):
                if self.tm.first_bet_after_entry:
                    self.logger.info("🕐 입장 직후 첫 베팅 - 1라운드 더 대기")
                    self.tm.first_bet_after_entry = False
                    return
                    
            # 서버에 예측값 요청
            next_pick = self.tm.server_client.get_next_prediction(room_id, filtered_results)
            
            if next_pick in ['P', 'B']:
                self.logger.info(f"🎯 서버 예측값: {next_pick}")
                
                # 🔥 현재 진행 중인 게임 번호를 전달 (없으면 current_round 사용)
                betting_round = current_game if current_game else current_round
                
                # 베팅 실행
                self.tm.betting_executor.execute_betting(next_pick, current_round, betting_round)
            else:
                self.logger.info(f"⏭️ 베팅 스킵: {next_pick}")
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")

    def _handle_martin_limit_reached(self):
        """마틴 한계 도달 처리"""
        try:
            # iframe 모니터링 중지
            self._stop_iframe_monitoring()
            
            # 방 나가기
            self.tm.game_monitoring_service.close_current_room()
            
            # 상태 초기화
            self.tm.current_target_room = None
            self.tm.current_room_name = ""
            
            # 웹소켓 모니터링 재개
            self._resume_websocket_monitoring()
            
            # 연패 모니터링 모드로 복귀
            self.tm.streak_handler.return_to_streak_monitoring()
            
        except Exception as e:
            self.logger.error(f"마틴 한계 처리 오류: {e}")

    def _stop_iframe_monitoring(self):
        """iframe 모니터링 중지"""
        try:
            if hasattr(self, 'iframe_timer') and self.iframe_timer:
                self.iframe_timer.stop()
                self.iframe_timer.deleteLater()  # 🔥 타이머 객체 완전 삭제
                self.iframe_timer = None
                self.logger.info("🛑 iframe 모니터링 중지")
                
            # 🔥 추가 안전장치 - 현재 타겟 방 정보도 클리어
            if hasattr(self.tm, 'current_target_room'):
                self.tm.current_target_room = None
                
        except Exception as e:
            self.logger.error(f"iframe 모니터링 중지 오류: {e}")

    def _check_game_count_condition(self, room_id: str, room_name: str) -> bool:
        """게임 수 조건 확인 (15게임 이상 65게임 미만)"""
        try:
            # iframe에서 현재 게임 상태 가져오기
            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=room_name,
                log_always=True,
                desired_pb_count=15
            )
            
            if not game_state:
                self.logger.warning("게임 상태를 가져올 수 없음")
                return False
            
            # 전체 게임 수 확인
            total_results = game_state.get('total_results', 0)
            current_round = game_state.get('round', 0)
            
            # 더 정확한 게임 수는 current_round 사용
            game_count = current_round if current_round > 0 else total_results
            
            self.logger.info(f"📊 현재 게임 수: {game_count}회")
            
            # 조건 체크: 15게임 이상 65게임 미만
            if game_count < 15:
                self.logger.warning(f"❌ 게임 수 부족: {game_count}회 < 15회")
                return False
            elif game_count >= 65:
                self.logger.warning(f"❌ 게임 수 초과: {game_count}회 >= 65회")
                return False
            else:
                self.logger.info(f"✅ 게임 수 조건 충족: {game_count}회 (15-64 범위)")
                return True
                
        except Exception as e:
            self.logger.error(f"게임 수 조건 확인 오류: {e}")
            return False
    
    def _fallback_room_entry(self, room_name: str) -> bool:
        """폴백 방 입장 로직"""
        try:
            self.logger.info(f"폴백 방 입장 시도: {room_name}")
            time.sleep(2)  # 입장 시뮬레이션
            return True
        except Exception as e:
            self.logger.error(f"폴백 방 입장 오류: {e}")
            return False

    def start_game_monitoring_in_room(self, streak_data: dict):
        """방 입장 후 게임 모니터링 시작 (기존 호환성)"""
        try:
            room_name = streak_data.get('room_name', '')
            self.logger.info(f"🎮 게임 모니터링 시작: {room_name}")
            
            # 게임 상태 초기화
            self.tm.game_count = 0
            self.tm.result_count = 0
            self.tm.wait_first_result = True
            self.tm.processed_rounds = set()
            
            # 현재 타겟 방 설정
            self.tm.current_target_room = streak_data
            
            self.logger.info(f"✅ 게임 모니터링 준비 완료: {room_name}")
            
        except Exception as e:
            self.logger.error(f"게임 모니터링 시작 오류: {e}")

    def handle_room_exit(self):
        """방 나가기 처리"""
        try:
            self.logger.info("🚪 방 나가기 처리")
            
            # iframe 모니터링 중지
            self._stop_iframe_monitoring()
            
            # 현재 방에서 나가기
            if hasattr(self.tm, 'game_monitoring_service'):
                self.tm.game_monitoring_service.close_current_room()
            
            # 상태 초기화
            self.tm.current_target_room = None
            self.tm.current_room_name = ""
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False
            
            # 웹소켓 모니터링 재개
            self._resume_websocket_monitoring()
            
            self.logger.info("✅ 방 나가기 완료")
            
        except Exception as e:
            self.logger.error(f"방 나가기 처리 오류: {e}")

    def debug_current_room_status(self):
        """현재 방 상태 디버그"""
        try:
            self.logger.info("=" * 50)
            self.logger.info("현재 방 상태")
            self.logger.info(f"현재 방: {self.tm.current_room_name}")
            self.logger.info(f"게임 카운트: {self.tm.game_count}")
            self.logger.info(f"iframe 모니터링: {'활성' if self.iframe_timer else '비활성'}")
            self.logger.info("=" * 50)
            
        except Exception as e:
            self.logger.error(f"방 상태 디버그 오류: {e}")