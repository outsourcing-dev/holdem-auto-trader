import time
import logging


class RoomEntryHandler:
    """방 입장 및 관리 전담 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger

    def execute_room_entry(self, streak_data: dict):
        """방 입장 후 서버 검증 및 베팅 시작 - 테스트 버전"""
        try:
            room_name = streak_data.get('room_name', '')
            room_id = streak_data.get('room_id', '')
            expected_streak = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🧪 [테스트] 방 입장 실행: {room_name} ({room_id})")
            
            # 1. 방 입장 시도
            if hasattr(self.tm.room_entry_service, 'enter_room_by_name'):
                success = self.tm.room_entry_service.enter_room_by_name(room_name)
            else:
                success = self._fallback_room_entry(room_name)
            
            if success:
                self.logger.info(f"✅ [테스트] 방 입장 성공: {room_name}")
                
                # 2. iframe에서 현재 방 상태 확인
                time.sleep(3)  # 방 로딩 대기
                
                self.logger.info(f"🔍 [테스트] iframe에서 방 데이터 분석 시작: {room_name}")
                
                # 서버 전송 형태로 데이터 준비
                server_data = self.tm.game_monitoring_service.send_room_data_to_server_format(
                    room_id=room_id,
                    room_name=room_name
                )
                
                if server_data:
                    # 서버 예측값 기반 베팅 로직 복원
                    self.logger.info(f"🎯 서버 예측값 기반 베팅 로직 시작: {room_name}")
                    
                    # 현재 방 정보 설정
                    self.tm.current_room_name = room_name
                    self.tm.current_target_room = streak_data
                    
                    # 게임 상태 초기화
                    self.tm.game_count = server_data.get('round_number', 1)
                    self.tm.result_count = 0
                    self.tm.wait_first_result = False
                    self.tm.processed_rounds = set()
                    
                    # UI 업데이트
                    self.tm.main_window.update_betting_status(
                        room_name=room_name,
                        status=f"서버 예측값 기반 베팅 모드 시작"
                    )
                    
                    self.logger.info(f"🎯 [서버 예측] 게임 모니터링 준비 완료: {room_name}")
                    
                    # 서버 데이터를 기반으로 game_data 생성
                    fake_game_data = {
                        'room_id': room_id,
                        'room_name': room_name,
                        'game_results': [r for r in server_data.get('all_results', []) if r in ('P', 'B')],
                        'latest_result': server_data.get('latest_result', ''),
                        'round_number': server_data.get('round_number', 1),
                        'has_results': True
                    }
                    
                    # 서버에서 다음 예측값 요청
                    current_results = server_data.get('all_results', [])
                    # TIE('T')를 제외한 값만 서버로 전달 (이중 필터링)
                    filtered_results = [r for r in current_results if r in ('P', 'B')]
                    next_pick = self.tm.server_client.get_next_prediction(room_id, filtered_results)
                    self.logger.info(f"🎯 [서버 예측] 서버 예측 결과: {next_pick}")
                    
                    if next_pick in ['P', 'B']:
                        self.logger.info(f"🎯 [서버 예측] 베팅 실행: {next_pick}")
                        self.tm.betting_executor.execute_betting(next_pick, fake_game_data['round_number'])
                    else:
                        self.logger.info(f"🎯 [서버 예측] 베팅 안함: {next_pick}")
                    
                    return True
                else:
                    self.logger.error(f"❌ [테스트] 게임 상태 분석 실패: {room_name}")
                    
            else:
                self.logger.warning(f"❌ [테스트] 방 입장 실패: {room_name}")
            
            # 방 입장 플래그 해제
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False
                
        except Exception as e:
            self.logger.error(f"🧪 [테스트] 방 입장 실행 오류: {e}")
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False

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
        """방 입장 후 게임 모니터링 시작"""
        try:
            room_name = streak_data.get('room_name', '')
            room_id = streak_data.get('room_id', '')
            streak_count = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🎮 게임 모니터링 시작: {room_name} ({streak_count}연패 확인됨)")
            
            # 게임 상태 초기화
            self.tm.game_count = 0
            self.tm.result_count = 0
            self.tm.wait_first_result = True
            self.tm.processed_rounds = set()
            
            # 현재 타겟 방 설정
            self.tm.current_target_room = streak_data
            
            # 최신 게임 상태로 게임 카운트 설정
            try:
                game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                    room_id=room_id,
                    room_name=room_name,
                    log_always=True
                )
                
                if game_state:
                    current_round = game_state.get('round', 0)
                    self.tm.game_count = current_round
                    self.logger.info(f"🎯 현재 게임 라운드: {current_round}")
                    
                    # ChoicePickSystem 초기화
                    if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                        cps = self.tm.excel_trading_service.choice_pick_system
                        cps._entered_round = current_round
                        cps._current_game_round = current_round
                        cps.wait_first_result = True
                        self.logger.info(f"ChoicePickSystem 초기화: 라운드 {current_round}")
                        
            except Exception as e:
                self.logger.warning(f"게임 상태 설정 중 오류: {e}")
            
            self.logger.info(f"✅ 게임 모니터링 준비 완료: {room_name}")
            
        except Exception as e:
            self.logger.error(f"게임 모니터링 시작 오류: {e}")

    def debug_current_room_status(self):
        """현재 방 상태 디버그"""
        try:
            self.logger.info("🔍 현재 방 상태 디버그:")
            self.logger.info(f"  - 현재 방: {self.tm.current_room_name}")
            self.logger.info(f"  - 타겟 방: {self.tm.current_target_room}")
            self.logger.info(f"  - 방 입장 진행 중: {self.tm.room_entry_in_progress}")
            self.logger.info(f"  - 게임 카운트: {self.tm.game_count}")
            
            # 현재 방이 있으면 실시간 분석
            if self.tm.current_room_name and self.tm.current_target_room:
                room_id = self.tm.current_target_room.get('room_id', '')
                room_name = self.tm.current_target_room.get('room_name', '')
                
                self.logger.info(f"🎮 실시간 방 분석 시작: {room_name}")
                
                # 게임 모니터링 서비스로 현재 상태 분석
                server_data = self.tm.game_monitoring_service.send_room_data_to_server_format(
                    room_id=room_id,
                    room_name=room_name
                )
                
                if server_data:
                    self.logger.info("✅ 실시간 방 분석 완료")
                else:
                    self.logger.warning("❌ 실시간 방 분석 실패")
            
        except Exception as e:
            self.logger.error(f"방 상태 디버그 오류: {e}")