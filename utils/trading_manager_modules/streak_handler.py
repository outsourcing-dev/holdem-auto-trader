import logging


class StreakHandler:
    """연패 감지 및 처리 전담 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger
        
    def start_streak_monitoring(self):
        """연패 모니터링 시작"""
        try:
            self.logger.info("🏠 연패 모니터링 시작")
            self.tm.main_window.update_betting_status(room_name="연패 방 감지 중...")
            self.logger.info("✅ 연패 모니터링 활성화")
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
            
            # 현재 방에서 나가기
            try:
                if hasattr(self.tm, 'game_monitoring_service'):
                    self.tm.game_monitoring_service.close_current_room()
                    self.logger.info("🚪 현재 방 나가기 완료")
            except Exception as e:
                self.logger.debug(f"방 나가기 중 오류 (무시): {e}")
            
            # 현재 방 정보만 초기화 (연패 방 리스트는 유지)
            self.tm.current_target_room = None
            self.tm.current_room_name = ""
            
            # 상태 초기화 - 베팅 관련 상태도 모두 초기화
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False
            self.tm.wait_first_result = False
            
            # 🔥 베팅 상태 완전 초기화
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.has_bet_current_round = False
                self.tm.betting_service.current_bet_round = 0
                self.tm.betting_service.is_betting_in_progress = False
                
            # 🔥 게임 프로세서 상태 초기화
            if hasattr(self.tm, 'game_processor'):
                self.tm.game_processor.betting_cooldown = False
                self.tm.game_processor.consecutive_requests = 0
                self.tm.game_processor.last_bet_round = 0
                
                # 베팅 추적기도 완전 초기화
                if hasattr(self.tm.game_processor, 'betting_tracker'):
                    self.tm.game_processor.betting_tracker.reset_tracking()
                    self.logger.info("🔄 베팅 추적기 상태 초기화 완료")
            
            # UI 업데이트
            self.tm.main_window.update_betting_status(
                room_name="새 연패 방 검색 중...",
                status="연속 자동 매매 진행 중"
            )
            
            # 🔥 로비 웹소켓 모니터링 재개 (새로운 연패 감지용)
            if hasattr(self.tm, 'websocket_manager') and hasattr(self.tm.websocket_manager, 'websocket_service'):
                self.logger.info("📡 로비 웹소켓 모니터링 재개")
                self.tm.websocket_manager.websocket_service.resume_lobby_monitoring()
            
            # 🔥 서버에서 새로운 연패 방 즉시 요청 (웹소켓 재개 후)
            self._request_new_streak_rooms()
            
            self.logger.info("✅ 연패 모니터링 모드 복귀 완료 - 무한 루프 계속")
            
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
        """서버에서 새로운 연패 방 즉시 요청"""
        try:
            if not hasattr(self.tm, 'server_client') or not self.tm.server_client:
                self.logger.warning("서버 클라이언트가 없음 - 연패 방 요청 불가")
                return
            
            self.logger.info("🏠 서버에 새로운 연패 방 리스트 요청 중...")
            
            # 서버에 연패 방 요청 (올바른 메서드명 사용)
            server_response = self.tm.server_client.find_streak_rooms(user_id="default", min_streak=3)
            
            if server_response and server_response.get('success'):
                new_streak_rooms = server_response.get('data', {}).get('rooms', [])
                
                if new_streak_rooms and isinstance(new_streak_rooms, list):
                    # 기존 리스트 초기화 후 새로운 방들 추가
                    self.tm.target_streak_rooms = []
                    
                    for room_data in new_streak_rooms:
                        if room_data.get('streak_count', 0) >= 3:  # 최소 3연패
                            self.tm.target_streak_rooms.append(room_data)
                    
                    # 연패 수가 높은 순으로 정렬
                    self.tm.target_streak_rooms.sort(key=lambda x: x.get('streak_count', 0), reverse=True)
                    
                    self.logger.info(f"✅ 새로운 연패 방 {len(self.tm.target_streak_rooms)}개 수신")
                    
                    # 첫 번째 방으로 즉시 입장 시도
                    if self.tm.target_streak_rooms:
                        best_room = self.tm.target_streak_rooms[0]
                        self.logger.info(f"🎯 최고 연패 방으로 입장 시도: {best_room.get('room_name')} ({best_room.get('streak_count')}연패)")
                        self.on_room_entry_requested(best_room)
                    else:
                        self.logger.warning("서버에서 연패 방 없음 - 웹소켓 모니터링으로 대기")
                        self._fallback_to_websocket_monitoring()
                else:
                    self.logger.warning("서버 응답에 연패 방 데이터 없음")
                    self._fallback_to_websocket_monitoring()
            else:
                self.logger.warning("서버 요청 실패 - 웹소켓 모니터링으로 대기")  
                self._fallback_to_websocket_monitoring()
                
        except Exception as e:
            self.logger.error(f"새로운 연패 방 요청 오류: {e}")
            # 서버 요청 실패 시 웹소켓 모니터링으로 대체
            self._fallback_to_websocket_monitoring()

    def _fallback_to_websocket_monitoring(self):
        """서버 요청 실패 시 웹소켓 모니터링으로 대체"""
        try:
            self.logger.info("🔄 서버 요청 실패 - 웹소켓 모니터링으로 연패 방 감지")
            
            # 기존 연패 방 리스트 유지 (있는 경우)
            if self.tm.target_streak_rooms:
                self.logger.info(f"📋 기존 연패 방 {len(self.tm.target_streak_rooms)}개 유지")
                
                # 첫 번째 방으로 입장 시도
                best_room = self.tm.target_streak_rooms[0]
                self.logger.info(f"🎯 기존 연패 방으로 입장 시도: {best_room.get('room_name')} ({best_room.get('streak_count')}연패)")
                self.on_room_entry_requested(best_room)
            else:
                # 새로운 연패 방을 웹소켓으로 대기
                self.tm.main_window.update_betting_status(
                    room_name="연패 방 웹소켓 감지 중...",
                    status="서버 연결 대기"
                )
                
        except Exception as e:
            self.logger.error(f"대체 모니터링 설정 오류: {e}")
            
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