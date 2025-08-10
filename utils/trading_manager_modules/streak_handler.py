import logging
import time
from PyQt6.QtCore import QTimer


class StreakHandler:
    """연패 감지 및 처리 전담 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger
        
    def start_streak_monitoring(self):
        """연패 모니터링 시작"""
        try:
            self.logger.info("🏠 연패 모니터링 시작")
            self.tm.main_window.update_betting_status(room_name="연패 방 감지 중...")  # 🔥 통일된 메시지
            self.logger.info("📡 WebSocket 연결 확인 및 연패 데이터 체크 시작")
        except Exception as e:
            self.logger.error(f"연패 모니터링 시작 오류: {e}")

    def on_streak_room_found(self, streak_data: dict):
        """연패 방 발견 시 처리"""
        try:
            room_id = streak_data.get('room_id', '')
            room_name = streak_data.get('room_name', '')
            streak_count = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🚨 연패 방 발견! {room_name} - {streak_count}연패")
            
            # 타겟 연패 방 리스트에 추가 (중복 체크)
            existing_room = next((room for room in self.tm.target_streak_rooms 
                                if room['room_id'] == room_id), None)
            
            if existing_room:
                existing_room.update(streak_data)
                self.logger.info(f"📝 연패 방 정보 업데이트: {room_name}")
            else:
                self.tm.target_streak_rooms.append(streak_data)
                self.logger.info(f"➕ 새 연패 방 추가: {room_name}")
            
            # 연패 수가 높은 순으로 정렬
            self.tm.target_streak_rooms.sort(key=lambda x: x.get('streak_count', 0), reverse=True)
            self.update_streak_room_display()
                
        except Exception as e:
            self.logger.error(f"연패 방 발견 처리 오류: {e}")

    def on_room_entry_requested(self, streak_data: dict):
        """방 입장 요청 처리"""
        try:
            # 🔥 자동 매매가 비활성화되었으면 무시
            if not self.tm.is_trading_active:
                self.logger.debug("자동 매매 비활성 - 방 입장 요청 무시")
                return
                
            if self.tm.room_entry_in_progress or self.tm.is_entering_room:
                self.logger.info(f"방 입장이 이미 진행 중입니다. 요청 무시: {streak_data.get('room_name', '')}")
                return
            
            room_name = streak_data.get('room_name', '')
            streak_count = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🚪 방 입장 요청 처리: {room_name} ({streak_count}연패)")
            
            # 방 입장 플래그 설정
            self.tm.room_entry_in_progress = True
            self.tm.is_entering_room = True
            self.tm.current_target_room = streak_data
            
            # UI 업데이트
            self.tm.main_window.update_betting_status(
                room_name=f"입장 중: {room_name}",
                status=f"{streak_count}연패 방 입장 시도"
            )
            
            # 실제 방 입장 실행
            self.tm.room_manager_handler.execute_room_entry(streak_data)
                
        except Exception as e:
            self.logger.error(f"방 입장 요청 처리 오류: {e}")
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False

    def update_streak_room_display(self):
        """연패 방 목록 UI 업데이트"""
        try:
            if self.tm.target_streak_rooms:
                top_room = self.tm.target_streak_rooms[0]
                room_name = top_room.get('room_name', '')
                streak_count = top_room.get('streak_count', 0)
                
                if not self.tm.room_entry_in_progress and not self.tm.current_target_room:
                    self.tm.main_window.update_betting_status(room_name=f"발견: {room_name}")
                    self.logger.info(f"연패 방 대기 중: {room_name} ({streak_count}연패)")
            else:
                if not self.tm.room_entry_in_progress and not self.tm.current_target_room:
                    self.tm.main_window.update_betting_status(room_name="연패 방 감지 중...")
        except Exception as e:
            self.logger.error(f"연패 방 표시 업데이트 오류: {e}")

    def remove_failed_room(self, room_id: str):
        """실패한 방을 목록에서 제거"""
        self.tm.target_streak_rooms = [room for room in self.tm.target_streak_rooms 
                                      if room['room_id'] != room_id]
        self.logger.info(f"방 {room_id} 제거 완료")

    # utils/trading_manager_modules/streak_handler.py - return_to_streak_monitoring 메서드 수정

    def return_to_streak_monitoring(self):
        """연패 모니터링 모드로 복귀 - 목표 금액까지 무한 루프"""
        try:
            self.logger.info("🔄 마틴 완료 후 연패 모니터링 모드로 복귀")
            
            # 🔥 목표 금액 달성 여부 확인
            if self._check_target_amount_reached():
                self.logger.info("🎯 목표 금액 달성! 자동 매매 중지")
                self.tm.stop_trading()
                return
            
            # 🔥 방 퇴장 전 최종 승패 기록 저장
            self._save_final_room_statistics()
            
            # 🔥 현재 방 정보 초기화 (모든 베팅 로직 중지를 위해)
            current_room_name = self.tm.current_room_name  # 로그용으로 보관
            self.tm.current_target_room = None
            self.tm.current_room_name = ""
            self.logger.info(f"🔄 방 '{current_room_name}' 퇴장 및 정보 초기화 완료")
            
            # 🔥 iframe 모니터링 완전 중지 (중요!)
            if hasattr(self.tm, 'room_manager_handler'):
                # iframe 타이머 완전 중지
                if hasattr(self.tm.room_manager_handler, 'iframe_timer') and self.tm.room_manager_handler.iframe_timer:
                    self.tm.room_manager_handler.iframe_timer.stop()
                    self.tm.room_manager_handler.iframe_timer = None
                    self.logger.info("🛑 iframe 타이머 완전 중지")
                
                # 추가 안전장치
                self.tm.room_manager_handler._stop_iframe_monitoring()
                self.logger.info("🛑 iframe 모니터링 중지")
            
            # 현재 방에서 나가기
            try:
                if hasattr(self.tm, 'game_monitoring_service'):
                    self.tm.game_monitoring_service.close_current_room()
                    self.logger.info("🚪 현재 방 나가기 완료")
            except Exception as e:
                self.logger.debug(f"방 나가기 중 오류 (무시): {e}")
            
            # 🔥 마틴 실패한 방이면 제외 리스트에 추가
            current_target_room_backup = self.tm.current_target_room
            is_martin_fail = False
            if current_target_room_backup and hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = self.tm.main_window.betting_widget.room_position_counter
                martin_stages = len(self.tm.martin_service.martin_amounts) if hasattr(self.tm, 'martin_service') else 7
                
                # 마지막 마틴 단계에서 실패한 경우
                if current_pos >= martin_stages:
                    is_martin_fail = True
                    room_id = current_target_room_backup.get('room_id')
                    if room_id:
                        self.tm.excluded_rooms[room_id] = {
                            'timestamp': time.time(),
                            'reason': 'martin_fail'
                        }
                        self.logger.info(f"🚫 마틴 실패한 방 제외 리스트에 추가: {room_id} (10분간)")
            
            
            # 상태 초기화 - 베팅 관련 상태도 모두 초기화
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False
            self.tm.wait_first_result = False
            
            # 🔥 위젯 카운터 초기화 - 마틴 실패 시에만!
            if hasattr(self.tm.main_window, 'betting_widget'):
                if is_martin_fail:
                    # 마틴 한계 도달로 실패한 경우만 1단계로 리셋
                    self.tm.main_window.betting_widget.room_position_counter = 0
                    self.tm.main_window.betting_widget.reset_step_markers()
                    self.logger.info("📊 베팅 위젯 1단계로 초기화 (마틴 한계 도달)")
                else:
                    # 그 외의 경우 (예: 성공)는 현재 상태 유지
                    self.logger.info("📊 베팅 위젯 현재 상태 유지 (연패 중)")
            
            # 🔥 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset()
                self.logger.info("🎰 마틴 서비스 초기화")
            
            # 🔥 베팅 상태 완전 초기화 및 진행 중인 베팅 강제 중지
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.has_bet_current_round = False
                self.tm.betting_service.current_bet_round = 0
                self.tm.betting_service.is_betting_in_progress = False
                
                # 🔥 진행 중인 베팅 요청들 강제 취소
                if hasattr(self.tm.betting_service, '_cancel_all_requests'):
                    self.tm.betting_service._cancel_all_requests()
                    self.logger.info("🛑 진행 중인 베팅 요청 모두 취소")
                
            # 🔥 게임 프로세서 상태 초기화
            if hasattr(self.tm, 'game_processor'):
                self.tm.game_processor.betting_cooldown = False
                self.tm.game_processor.consecutive_requests = 0
                self.tm.game_processor.last_bet_round = 0
                
                # 🔥 베팅 타이머 중지
                if hasattr(self.tm.game_processor, 'betting_timer') and self.tm.game_processor.betting_timer:
                    self.tm.game_processor.betting_timer.stop()
                    self.tm.game_processor.betting_timer = None
                    self.logger.info("🛑 베팅 타이머 중지")
                
                # 🔥 요청 상태 초기화
                if hasattr(self.tm.game_processor, '_is_requesting'):
                    self.tm.game_processor._is_requesting = False
                
                # 🔥 모든 QTimer 강제 중지
                self._stop_all_qtimers()
                
                # 🔥 서버 요청 중단
                if hasattr(self.tm, 'server_client'):
                    # 진행 중인 요청이 있으면 중단시킬 수 있는 플래그 설정
                    self.tm.server_client._cancel_current_requests = True
                    self.logger.info("🛑 서버 요청 중단 플래그 설정")
                
                # 베팅 추적기도 완전 초기화
                if hasattr(self.tm.game_processor, 'betting_tracker'):
                    self.tm.game_processor.betting_tracker.reset_tracking()
                    self.logger.info("🔄 베팅 추적기 상태 초기화 완료")
            
            # UI 업데이트
            self.tm.main_window.update_betting_status(
                room_name="연패 방 검색 중...",  # 🔥 통일된 메시지
                status="연속 자동 매매 진행 중"
            )
            
            # 🔥 로비 웹소켓 모니터링 재개 (새로운 연패 감지용)
            if hasattr(self.tm, 'websocket_manager'):
                try:
                    # 🔥 먼저 모니터링 플래그 강제 리셋 (에러 방지)
                    if hasattr(self.tm.websocket_manager, 'websocket_service') and self.tm.websocket_manager.websocket_service:
                        ws_service = self.tm.websocket_manager.websocket_service
                        # 플래그 강제 리셋
                        ws_service._pause_lobby_monitoring = False
                        ws_service._in_game_room = False
                        self.logger.info("🔄 WebSocket 플래그 강제 리셋 완료")
                        
                        # resume_lobby_monitoring 호출
                        ws_service.resume_lobby_monitoring()
                        self.logger.info("📡 로비 웹소켓 모니터링 재개 완료")
                        
                        # 타이머 재시작
                        try:
                            ws_service._start_message_collection()
                        except:
                            pass
                
                    # 웹소켓 상태 확인
                    ws_status = self.tm.websocket_manager.get_interceptor_status()
                    self.logger.info(f"📡 현재 웹소켓 상태: {ws_status}")
                    
                    if not ws_status.get('is_intercepting', False) or not ws_status.get('cdp_session_active', False):
                        self.logger.warning("⚠️ 웹소켓 연결이 끊어짐 - 재연결 시도")
                        success = self.tm.websocket_manager.force_reconnect_websocket()
                        if not success:
                            self.logger.error("❌ 웹소켓 재연결 실패")
                            # 10초 후 재시도
                            QTimer.singleShot(10000, self.tm.websocket_manager.force_reconnect_websocket)
                    
                    # 🔥 웹소켓 서비스 연패 기준도 최신 설정으로 업데이트
                    if hasattr(self.tm, 'settings_manager') and self.tm.websocket_manager.websocket_service:
                        min_streak = self.tm.settings_manager.get_min_streak()
                        self.tm.websocket_manager.websocket_service.update_streak_threshold(min_streak)
                        
                except Exception as ws_error:
                    self.logger.error(f"WebSocket 모니터링 재개 중 오류: {ws_error}")
                    # 에러 시에도 강제 플래그 리셋 시도
                    try:
                        if hasattr(self.tm.websocket_manager, 'websocket_service') and self.tm.websocket_manager.websocket_service:
                            self.tm.websocket_manager.websocket_service._pause_lobby_monitoring = False
                            self.tm.websocket_manager.websocket_service._in_game_room = False
                            self.logger.info("🔄 에러 후 WebSocket 플래그 강제 리셋")
                    except:
                        pass
                        self.logger.info(f"🎯 웹소켓 서비스 연패 기준 업데이트: {min_streak}")
                else:
                    self.logger.warning("⚠️ 웹소켓 서비스가 없음 - 재시작 필요")
            
            # 🔥 서버 요청 중단 플래그 해제
            if hasattr(self.tm, 'server_client'):
                self.tm.server_client._cancel_current_requests = False
                self.logger.info("✅ 서버 요청 중단 플래그 해제")
            
            # 🔥 첫 시작과 동일하게 웹소켓 모니터링만 시작
            self.logger.info("🔄 방 나가기 완료 - 연패 모니터링 재시작")
            
            # 첫 시작과 동일하게 처리
            self.start_streak_monitoring()
            
            self.logger.info("✅ 연패 모니터링 모드 복귀 완료 - 웹소켓으로 새로운 연패 방 대기")
            
        except Exception as e:
            self.logger.error(f"연패 모니터링 복귀 오류: {e}")

    def _check_target_amount_reached(self):
        """목표 금액 달성 여부 확인"""
        try:
            if hasattr(self.tm, 'balance_service') and self.tm.balance_service:
                # 현재 잔액 확인 (올바른 메서드명 사용)
                current_balance = self.tm.balance_service.get_lobby_balance()
                
                if current_balance is None or current_balance == 0:
                    self.logger.warning("잔액 조회 실패 - 목표 금액 체크 건너뜀")
                    return False
                
                # 잔액 서비스의 목표 금액 체크 활용
                if self.tm.balance_service.check_target_amount(current_balance, source="연패 방 복귀"):
                    return True
                        
            return False
        except Exception as e:
            self.logger.error(f"목표 금액 확인 오류: {e}")
            return False

    def _request_new_streak_rooms(self):
        """서버에서 새로운 연패 방 즉시 요청 - 현재는 사용하지 않음"""
        # 첫 시작과 동일하게 웹소켓 모니터링만 사용
        self.logger.info("📡 웹소켓으로 연패 방 감지 중...")
        return
        
        try:
            if not hasattr(self.tm, 'server_client') or not self.tm.server_client:
                self.logger.warning("서버 클라이언트가 없음 - 연패 방 요청 불가")
                return
            
            # 🔥 웹소켓 연결 상태 먼저 체크
            self._check_websocket_status_before_request()
            
            self.logger.info("🏠 서버에 새로운 연패 방 리스트 요청 중...")
            
            # 서버 연결 상태 체크
            server_status = self.tm.server_client.get_server_status()
            self.logger.info(f"📡 서버 연결 상태: {server_status}")
            
            if not server_status:
                self.logger.error("❌ 서버 연결이 끊어짐 - 재연결 필요")
                return
            
            # 서버에 연패 방 요청 (설정된 연패 조건 사용)
            min_streak = self.tm.settings_manager.get_min_streak() if hasattr(self.tm, 'settings_manager') else 3
            self.logger.info(f"📊 연패 조건: {min_streak}연패 이상 방 검색")
            self.logger.info(f"🔍 서버 요청 시작: find_streak_rooms(user_id='default', min_streak={min_streak})")
            
            server_response = self.tm.server_client.find_streak_rooms(user_id="default", min_streak=min_streak)
            
            self.logger.info(f"📥 서버 응답 수신: {server_response}")
            
            # 응답 구조 상세 로깅
            if server_response:
                self.logger.info(f"📋 응답 타입: {type(server_response)}")
                self.logger.info(f"📋 응답 키들: {list(server_response.keys()) if isinstance(server_response, dict) else 'Not a dict'}")
                
                # success 키 체크
                has_success = 'success' in server_response if isinstance(server_response, dict) else False
                self.logger.info(f"📋 'success' 키 존재: {has_success}")
                if has_success:
                    self.logger.info(f"📋 'success' 값: {server_response.get('success')}")
                
                # data 키 체크
                has_data = 'data' in server_response if isinstance(server_response, dict) else False
                self.logger.info(f"📋 'data' 키 존재: {has_data}")
                if has_data:
                    data = server_response.get('data')
                    self.logger.info(f"📋 'data' 타입: {type(data)}")
                    if isinstance(data, dict):
                        self.logger.info(f"📋 'data' 키들: {list(data.keys())}")
            
            if server_response and server_response.get('success'):
                new_streak_rooms = server_response.get('data', {}).get('rooms', [])
                
                if new_streak_rooms and isinstance(new_streak_rooms, list):
                    # 🔥 기존 리스트 완전 초기화 후 새로운 방들 추가
                    self.tm.target_streak_rooms = []
                    self.logger.info("🗑️ 기존 연패 방 리스트 초기화")
                    
                    # 🔥 제외 시간 경과한 방들은 제외 리스트에서 제거
                    current_time = time.time()
                    expired_rooms = []
                    for room_id, room_info in self.tm.excluded_rooms.items():
                        timestamp = room_info.get('timestamp', 0)
                        reason = room_info.get('reason', 'unknown')
                        
                        # 마틴 실패: 10분, 입장 실패: 10분, 조건 미충족: 5분
                        if reason == 'martin_fail':
                            timeout = 600  # 10분
                        elif reason == 'entry_fail':
                            timeout = 600  # 10분
                        else:  # condition_fail
                            timeout = 300  # 5분
                        
                        if current_time - timestamp > timeout:
                            expired_rooms.append(room_id)
                    
                    for room_id in expired_rooms:
                        reason = self.tm.excluded_rooms[room_id].get('reason', 'unknown')
                        del self.tm.excluded_rooms[room_id]
                        if reason == 'martin_fail':
                            timeout_min = 10
                        elif reason == 'entry_fail':
                            timeout_min = 10
                        else:  # condition_fail
                            timeout_min = 5
                        self.logger.info(f"✅ 제외 시간 경과한 방 복구: {room_id} ({reason}, {timeout_min}분)")
                    
                    for room_data in new_streak_rooms:
                        room_id = room_data.get('room_id')
                        # 🔥 제외 리스트에 없고 설정된 연패 이상인 방만 추가
                        min_streak = self.tm.settings_manager.get_min_streak() if hasattr(self.tm, 'settings_manager') else 3
                        if (room_data.get('streak_count', 0) >= min_streak and 
                            room_id not in self.tm.excluded_rooms):
                            self.tm.target_streak_rooms.append(room_data)
                        elif room_id in self.tm.excluded_rooms:
                            reason = self.tm.excluded_rooms[room_id].get('reason', 'unknown')
                            if reason == 'martin_fail':
                                reason_text = "마틴 실패"
                            elif reason == 'entry_fail':
                                reason_text = "입장 실패"
                            else:  # condition_fail
                                reason_text = "조건 미충족"
                            self.logger.info(f"🚫 제외된 방 스킵: {room_data.get('room_name')} ({room_id}, {reason_text})")
                    
                    # 연패 수가 높은 순으로 정렬
                    self.tm.target_streak_rooms.sort(key=lambda x: x.get('streak_count', 0), reverse=True)
                    
                    self.logger.info(f"✅ 새로운 연패 방 {len(self.tm.target_streak_rooms)}개 수신")
                    
                    # 첫 번째 방으로 즉시 입장 시도
                    if self.tm.target_streak_rooms:
                        best_room = self.tm.target_streak_rooms[0]
                        self.logger.info(f"🎯 최고 연패 방으로 입장 시도: {best_room.get('room_name')} ({best_room.get('streak_count')}연패)")
                        self.on_room_entry_requested(best_room)
                    else:
                        self.logger.info("📡 서버에서 연패 방 없음 - 웹소켓으로 새로운 연패 감지 대기")
                        # 웹소켓 모니터링 계속 진행
                else:
                    self.logger.info("📡 서버 응답에 연패 방 없음 - 웹소켓으로 새로운 연패 감지 대기")
                    # 🔥 빈 응답 시에도 기존 리스트 초기화
                    self.tm.target_streak_rooms = []
            else:
                self.logger.info("📡 서버 통신 지연 - 웹소켓으로 연패 감지 중")
                # 🔥 실패 시에도 기존 리스트 초기화  
                self.tm.target_streak_rooms = []
                
        except Exception as e:
            self.logger.error(f"새로운 연패 방 요청 오류: {e}")
            # 🔥 예외 발생 시에도 기존 리스트 초기화
            self.tm.target_streak_rooms = []
            # 서버 요청 실패 시 웹소켓 모니터링으로 대체
            self._fallback_to_websocket_monitoring()
            # 🔥 10초 후 다시 서버 요청
            QTimer.singleShot(10000, self._retry_server_request)

    def _fallback_to_websocket_monitoring(self):
        """서버 요청 실패 시 웹소켓 모니터링으로 대체"""
        try:
            self.logger.info("🔄 서버 요청 실패 - 웹소켓 모니터링으로 연패 방 감지")
            
            # 🔥 기존 연패 방 리스트 완전 초기화 (방금 나간 방이 포함되어 있을 수 있음)
            self.tm.target_streak_rooms = []
            self.logger.info("🗑️ 기존 연패 방 리스트 초기화 - 새로운 방만 감지")
            
            # 웹소켓 상태 확인 및 재연결
            if hasattr(self.tm, 'websocket_manager'):
                ws_status = self.tm.websocket_manager.get_interceptor_status()
                if not ws_status.get('is_intercepting', False):
                    self.logger.warning("⚠️ 웹소켓이 끊어짐 - 재연결 시도")
                    self.tm.websocket_manager.force_reconnect_websocket()
            
            # 새로운 연패 방을 웹소켓으로 대기 (🔥 통일된 메시지)
            self.tm.main_window.update_betting_status(
                room_name="연패 방 감지 중...",
                status="서버 연결 대기"
            )
            
            # 🔥 5초 후 다시 서버 요청 예약
            if self.tm.is_trading_active:
                QTimer.singleShot(5000, self._retry_server_request)
                self.logger.info("⏰ 5초 후 서버 재요청 예약")
                
        except Exception as e:
            self.logger.error(f"대체 모니터링 설정 오류: {e}")
    
    def _stop_all_qtimers(self):
        """모든 QTimer 강제 중지"""
        try:
            # QTimer.singleShot으로 실행된 타이머들은 직접 중지할 수 없지만
            # 실행될 때 current_target_room이 None이면 실행되지 않도록 이미 처리됨
            
            # 혹시 남아있는 타이머들 확인
            timer_stopped_count = 0
            
            # 게임 프로세서의 모든 타이머 중지
            if hasattr(self.tm, 'game_processor'):
                for attr_name in dir(self.tm.game_processor):
                    attr = getattr(self.tm.game_processor, attr_name)
                    if isinstance(attr, QTimer) and attr.isActive():
                        attr.stop()
                        timer_stopped_count += 1
                        self.logger.info(f"🛑 {attr_name} 타이머 중지")
            
            # room_manager_handler의 모든 타이머 중지
            if hasattr(self.tm, 'room_manager_handler'):
                for attr_name in dir(self.tm.room_manager_handler):
                    attr = getattr(self.tm.room_manager_handler, attr_name)
                    if isinstance(attr, QTimer) and attr.isActive():
                        attr.stop()
                        timer_stopped_count += 1
                        self.logger.info(f"🛑 {attr_name} 타이머 중지")
            
            if timer_stopped_count > 0:
                self.logger.info(f"🛑 총 {timer_stopped_count}개 활성 타이머 중지")
            else:
                self.logger.debug("활성화된 타이머 없음")
                
        except Exception as e:
            self.logger.error(f"QTimer 중지 오류: {e}")
    
    def _check_websocket_status_before_request(self):
        """🔥 서버 요청 전 웹소켓 연결 상태 체크"""
        try:
            if hasattr(self.tm, 'websocket_manager') and self.tm.websocket_manager:
                ws_status = self.tm.websocket_manager.get_interceptor_status()
                
                # 상세 로그 출력
                self.logger.info(f"📡 웹소켓 상태 확인:")
                self.logger.info(f"  - 인터셉팅 활성: {ws_status.get('is_intercepting', False)}")
                self.logger.info(f"  - CDP 세션 활성: {ws_status.get('cdp_session_active', False)}")
                self.logger.info(f"  - 웹소켓 연결 수: {ws_status.get('websocket_connections', 0)}")
                self.logger.info(f"  - 처리된 메시지: {ws_status.get('processed_messages', 0)}")
                
                if ws_status.get('is_intercepting', False) and ws_status.get('cdp_session_active', False):
                    self.logger.info("✅ WebSocket 연결 상태: 정상")
                else:
                    self.logger.warning("⚠️ WebSocket 연결 끊김 - 재연결 시도")
                    # 웹소켓 재연결 시도
                    success = self.tm.websocket_manager.force_reconnect_websocket()
                    if success:
                        self.logger.info("✅ 웹소켓 재연결 성공")
                    else:
                        self.logger.error("❌ 웹소켓 재연결 실패")
            else:
                self.logger.warning("⚠️ 웹소켓 매니저가 없음 - 웹소켓 서비스 시작 필요")
                    
        except Exception as e:
            self.logger.error(f"웹소켓 상태 체크 오류: {e}")
    
    def _retry_server_request(self):
        """🔥 서버 재요청 시도"""
        try:
            if not self.tm.is_trading_active:
                self.logger.info("🛑 자동 매매 중지됨 - 서버 재요청 중단")
                return
            
            # 현재 방에 있지 않은 경우에만 재요청
            if not self.tm.current_target_room:
                self.logger.info("🔄 서버 연패 방 재요청 시도")
                
                # 웹소켓이 끊겼으면 먼저 재연결
                if hasattr(self.tm, 'websocket_manager') and self.tm.websocket_manager:
                    ws_status = self.tm.websocket_manager.get_interceptor_status()
                    if not ws_status.get('is_intercepting', False):
                        self.logger.warning("⚠️ 웹소켓 연결 끊김 - 재연결 후 서버 요청")
                        success = self.tm.websocket_manager.force_reconnect_websocket()
                        if not success:
                            # 재연결 실패 시 10초 후 재시도
                            QTimer.singleShot(10000, self._retry_server_request)
                            return
                
                self._request_new_streak_rooms()
            else:
                self.logger.debug(f"현재 방({self.tm.current_target_room})에 있으므로 서버 재요청 건너뛰기")
                
        except Exception as e:
            self.logger.error(f"서버 재요청 오류: {e}")
            # 오류 시 10초 후 재시도
            if self.tm.is_trading_active:
                QTimer.singleShot(10000, self._retry_server_request)
            
    def _save_final_room_statistics(self):
        """방 퇴장 시 최종 승패 통계 저장"""
        try:
            if not self.tm.current_room_name:
                self.logger.debug("현재 방 정보가 없어 최종 통계 저장 생략")
                return
            
            room_name = self.tm.current_room_name
            self.logger.info(f"📊 방 '{room_name}' 최종 승패 통계 저장 시작")
            
            # 베팅 추적기에서 통계 가져오기
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                tracker = self.tm.game_processor.betting_tracker
                stats = {
                    'room_name': room_name,
                    'total_bets': tracker.total_bets,
                    'wins': tracker.wins,
                    'losses': tracker.losses,
                    'ties': tracker.ties,
                    'win_rate': tracker.get_win_rate(),
                    'current_streak': tracker.current_streak,
                    'max_win_streak': tracker.max_win_streak,
                    'max_lose_streak': tracker.max_lose_streak
                }
                
                self.logger.info(f"📈 방 '{room_name}' 최종 통계:")
                self.logger.info(f"  - 총 베팅: {stats['total_bets']}회")
                self.logger.info(f"  - 승리: {stats['wins']}회, 패배: {stats['losses']}회, 무승부: {stats['ties']}회")
                self.logger.info(f"  - 승률: {stats['win_rate']:.1f}%")
                
                # 방 로그 위젯에 최종 업데이트
                if hasattr(self.tm.main_window, 'room_log_widget'):
                    self.tm.main_window.room_log_widget.update_room_stats(room_name, stats)
                    self.logger.info(f"✅ 방 로그 위젯에 '{room_name}' 최종 통계 업데이트 완료")
                
                # ExcelTradingService에 최종 기록
                if hasattr(self.tm, 'excel_trading_service'):
                    self.tm.excel_trading_service.record_room_final_stats(room_name, stats)
                    self.logger.info(f"✅ Excel 서비스에 '{room_name}' 최종 통계 기록 완료")
                
            else:
                self.logger.warning("베팅 추적기가 없어 최종 통계 저장 불가")
                
        except Exception as e:
            self.logger.error(f"최종 승패 통계 저장 오류: {e}")

    def get_streak_room_info(self):
        """연패 방 정보 반환"""
        try:
            return {
                'target_streak_rooms': self.tm.target_streak_rooms,
                'current_target_room': self.tm.current_target_room,
                'room_entry_in_progress': self.tm.room_entry_in_progress,
                'is_entering_room': self.tm.is_entering_room,
                'room_count': len(self.tm.target_streak_rooms)
            }
        except Exception as e:
            self.logger.error(f"연패 방 정보 확인 오류: {e}")
            return {'error': str(e)}