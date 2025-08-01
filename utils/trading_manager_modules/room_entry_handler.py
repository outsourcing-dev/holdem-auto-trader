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
            
            # iframe 모니터링 타이머 생성
            self.iframe_timer = QTimer()
            self.iframe_timer.timeout.connect(lambda: self._monitor_game_from_iframe(streak_data))
            self.iframe_timer.start(2000)  # 2초마다 확인
            
            self.logger.info("📊 iframe 기반 게임 모니터링 시작")
            
            # 첫 번째 체크 즉시 실행
            QTimer.singleShot(500, lambda: self._monitor_game_from_iframe(streak_data))
            
        except Exception as e:
            self.logger.error(f"iframe 모니터링 시작 오류: {e}")

    def _monitor_game_from_iframe(self, streak_data: dict):
        """iframe에서 게임 상태 모니터링 및 베팅 처리"""
        try:
            if not self.tm.is_trading_active or not self.tm.current_target_room:
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
            latest_result = game_state.get('latest_result', '')
            filtered_results = game_state.get('filtered_results', [])
            
            # 새로운 라운드 감지
            if current_round > self.tm.game_count:
                self.logger.info(f"🎮 새 라운드 감지: {current_round}")
                
                # 베팅 결과 확인
                if hasattr(self.tm.betting_service, 'has_pending_bet') and self.tm.betting_service.has_pending_bet():
                    self._check_betting_result(latest_result, current_round)
                
                # 게임 카운트 업데이트
                self.tm.game_count = current_round
                
                # 베팅 기회 확인
                if not self.tm.betting_service.has_bet_current_round:
                    self._check_betting_opportunity(filtered_results, room_id, current_round)
                    
        except Exception as e:
            self.logger.error(f"iframe 모니터링 오류: {e}")

    def _check_betting_result(self, latest_result: str, current_round: int):
        """베팅 결과 확인 및 처리"""
        try:
            if not latest_result:
                return
                
            # 베팅 서비스에서 대기 중인 베팅 정보 가져오기
            pending_bet_info = self.tm.betting_service.get_pending_bet_info()
            if not pending_bet_info:
                return
                
            bet_type = pending_bet_info['type']
            bet_round = pending_bet_info['round']
            
            # 베팅한 라운드의 결과인지 확인
            if current_round > bet_round:
                # 베팅 결과 확인
                result = self.tm.betting_service.check_pending_bet_result(current_round, latest_result)
                
                if result:
                    result_status = result['status']
                    self.logger.info(f"🎲 베팅 결과: {result_status}")
                    
                    if result_status == 'win':
                        self._handle_win_result()
                    elif result_status == 'lose':
                        self._handle_lose_result()
                    elif result_status == 'tie':
                        self._handle_tie_result()
                        
        except Exception as e:
            self.logger.error(f"베팅 결과 확인 오류: {e}")

    def _check_betting_opportunity(self, filtered_results: list, room_id: str, current_round: int):
        """베팅 기회 확인 및 실행"""
        try:
            if len(filtered_results) < 10:
                return
                
            # 서버에 예측값 요청
            next_pick = self.tm.server_client.get_next_prediction(room_id, filtered_results)
            
            if next_pick in ['P', 'B']:
                self.logger.info(f"🎯 서버 예측값: {next_pick}")
                
                # 베팅 실행
                bet_amount = self.tm.excel_trading_service.get_current_bet_amount()
                self.tm.betting_executor.execute_betting(next_pick, current_round)
            else:
                self.logger.info(f"⏭️ 베팅 스킵: {next_pick}")
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")

    def _handle_win_result(self):
        """승리 처리 - 방 나가고 웹소켓 재개"""
        try:
            self.logger.info("🎉 베팅 승리 - 방 나가기")
            
            # iframe 모니터링 중지
            self._stop_iframe_monitoring()
            
            # 위젯 초기화
            if hasattr(self.tm.main_window, 'betting_widget'):
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.tm.main_window.betting_widget.reset_step_markers()
            
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
            self.logger.error(f"승리 처리 오류: {e}")

    def _handle_lose_result(self):
        """패배 처리 - 마틴 단계 확인"""
        try:
            self.logger.info("❌ 베팅 패배")
            
            # 위젯 카운터 증가
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = self.tm.main_window.betting_widget.room_position_counter
                self.tm.main_window.betting_widget.room_position_counter = current_pos + 1
                
                # 마틴 단계 확인
                martin_stages = len(self.tm.martin_service.martin_amounts)
                if current_pos + 1 >= martin_stages:
                    self.logger.info("📈 마틴 단계 한계 도달 - 방 나가기")
                    self._handle_martin_limit_reached()
                    
        except Exception as e:
            self.logger.error(f"패배 처리 오류: {e}")

    def _handle_tie_result(self):
        """무승부 처리"""
        try:
            self.logger.info("🤝 무승부 - 동일 베팅 유지")
            # 베팅 상태만 초기화
            self.tm.betting_service.has_bet_current_round = False
            
        except Exception as e:
            self.logger.error(f"무승부 처리 오류: {e}")

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
                self.iframe_timer = None
                self.logger.info("🛑 iframe 모니터링 중지")
        except Exception as e:
            self.logger.error(f"iframe 모니터링 중지 오류: {e}")

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

    def debug_current_room_status(self):
        """현재 방 상태 디버그"""
        try:
            self.logger.info("🔍 현재 방 상태:")
            self.logger.info(f"  - 현재 방: {self.tm.current_room_name}")
            self.logger.info(f"  - 게임 카운트: {self.tm.game_count}")
            
        except Exception as e:
            self.logger.error(f"방 상태 디버그 오류: {e}")