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

    def return_to_streak_monitoring(self):
        """연패 모니터링 모드로 복귀"""
        try:
            self.logger.info("🔄 연패 모니터링 모드로 복귀")
            
            # 현재 방 정보 초기화
            self.tm.current_target_room = None
            self.tm.current_room_name = ""
            self.tm.target_streak_rooms = []
            
            # 상태 초기화
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False
            self.tm.wait_first_result = False
            
            # UI 업데이트
            self.tm.main_window.update_betting_status(
                room_name="연패 방 감지 중...",
                status="새로운 연패 방 대기 중"
            )
            
            # 현재 방에서 나가기
            try:
                if hasattr(self.tm, 'game_monitoring_service'):
                    self.tm.game_monitoring_service.close_current_room()
            except Exception as e:
                self.logger.debug(f"방 나가기 중 오류 (무시): {e}")
            
            self.logger.info("✅ 연패 모니터링 모드 복귀 완료")
            
        except Exception as e:
            self.logger.error(f"연페 모니터링 복귀 오류: {e}")

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