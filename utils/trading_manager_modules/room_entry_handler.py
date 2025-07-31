# utils/trading_manager_modules/room_entry_handler.py - 베팅 추적 통합 버전

import time
import logging


class RoomEntryHandler:
    """방 입장 및 관리 전담 클래스 - 베팅 추적 통합"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger

    def execute_room_entry(self, streak_data: dict):
        """방 입장 후 서버 검증 및 베팅 시작 - 베팅 추적 통합"""
        try:
            room_name = streak_data.get('room_name', '')
            room_id = streak_data.get('room_id', '')
            expected_streak = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🎯 방 입장 실행: {room_name} ({room_id})")
            
            # 방 입장 전 베팅 추적기 초기화
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                self.tm.game_processor.betting_tracker.reset_tracking()
                self.logger.info("방 입장 전 베팅 추적기 초기화")
            
            # 1. 방 입장 시도
            if hasattr(self.tm.room_entry_service, 'enter_room_by_name'):
                success = self.tm.room_entry_service.enter_room_by_name(room_name)
            else:
                success = self._fallback_room_entry(room_name)
            
            if success:
                self.logger.info(f"✅ 방 입장 성공: {room_name}")
                
                # 2. iframe에서 현재 방 상태 확인
                time.sleep(3)  # 방 로딩 대기
                
                self.logger.info(f"🔍 iframe에서 방 데이터 분석 시작: {room_name}")
                
                # 서버 전송 형태로 데이터 준비
                server_data = self.tm.game_monitoring_service.send_room_data_to_server_format(
                    room_id=room_id,
                    room_name=room_name
                )
                
                if server_data:
                    # 서버 예측값 기반 베팅 로직
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
                    
                    # 서버에서 다음 예측값 요청
                    current_results = server_data.get('all_results', [])
                    filtered_results = [r for r in current_results if r in ('P', 'B')]
                    next_pick = self.tm.server_client.get_next_prediction(room_id, filtered_results)
                    self.logger.info(f"🎯 [서버 예측] 서버 예측 결과: {next_pick}")
                    
                    if next_pick in ['P', 'B']:
                        # 베팅 실행 전 추적 시작
                        round_number = server_data.get('round_number', self.tm.game_count)
                        bet_amount = self.tm.excel_trading_service.get_current_bet_amount()
                        
                        # 베팅 추적 시작
                        if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                            self.tm.game_processor.betting_tracker.start_betting_tracking(
                                bet_type=next_pick,
                                round_number=round_number,
                                bet_amount=bet_amount,
                                room_name=room_name
                            )
                            self.logger.info(f"🎯 베팅 추적 시작: {next_pick} 라운드{round_number}")
                        
                        # 베팅 실행
                        self.logger.info(f"🎯 [서버 예측] 베팅 실행: {next_pick}")
                        self.tm.betting_executor.execute_betting(next_pick, round_number)
                    else:
                        self.logger.info(f"🎯 [서버 예측] 베팅 안함: {next_pick}")
                    
                    # 방 입장 성공 후 게임 모니터링 시작
                    self._start_game_monitoring_after_entry(streak_data)
                    
                    return True
                else:
                    self.logger.error(f"❌ 게임 상태 분석 실패: {room_name}")
                    # 실패 시 추적기 초기화
                    if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                        self.tm.game_processor.betting_tracker.reset_tracking()
                    
            else:
                self.logger.warning(f"❌ 방 입장 실패: {room_name}")
            
            # 방 입장 플래그 해제
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False
                
        except Exception as e:
            self.logger.error(f"방 입장 실행 오류: {e}")
            self.tm.room_entry_in_progress = False
            self.tm.is_entering_room = False
            
            # 오류 시 추적기 초기화
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                self.tm.game_processor.betting_tracker.reset_tracking()

    def _fallback_room_entry(self, room_name: str) -> bool:
        """폴백 방 입장 로직"""
        try:
            self.logger.info(f"폴백 방 입장 시도: {room_name}")
            time.sleep(2)  # 입장 시뮬레이션
            return True
        except Exception as e:
            self.logger.error(f"폴백 방 입장 오류: {e}")
            return False

    def _start_game_monitoring_after_entry(self, streak_data: dict):
        """방 입장 후 게임 모니터링 시작 - 베팅 추적 통합"""
        try:
            room_name = streak_data.get('room_name', '')
            room_id = streak_data.get('room_id', '')
            streak_count = streak_data.get('streak_count', 0)
            
            self.logger.info(f"🎮 게임 모니터링 시작: {room_name} ({streak_count}연패)")
            
            # 베팅 추적기 상태 확인
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                bet_info = self.tm.game_processor.betting_tracker.get_current_bet_info()
                self.logger.info(f"🎯 베팅 추적 상태: {bet_info.get('status', 'idle')}")
            
            # 게임 상태는 이미 execute_room_entry에서 초기화됨
            
            # 현재 타겟 방 확인
            self.tm.current_target_room = streak_data
            
            self.logger.info(f"✅ 게임 모니터링 준비 완료: {room_name}")
            
        except Exception as e:
            self.logger.error(f"게임 모니터링 시작 오류: {e}")

    def start_game_monitoring_in_room(self, streak_data: dict):
        """방 입장 후 게임 모니터링 시작 (호환성 유지)"""
        self._start_game_monitoring_after_entry(streak_data)

    def debug_current_room_status(self):
        """현재 방 상태 디버그 - 베팅 추적 정보 포함"""
        try:
            self.logger.info("🔍 현재 방 상태 디버그:")
            self.logger.info(f"  - 현재 방: {self.tm.current_room_name}")
            self.logger.info(f"  - 타겟 방: {self.tm.current_target_room}")
            self.logger.info(f"  - 방 입장 진행 중: {self.tm.room_entry_in_progress}")
            self.logger.info(f"  - 게임 카운트: {self.tm.game_count}")
            
            # 베팅 추적 상태 추가
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                tracker = self.tm.game_processor.betting_tracker
                bet_info = tracker.get_current_bet_info()
                
                self.logger.info(f"🎯 베팅 추적 상태:")
                self.logger.info(f"  - 상태: {bet_info.get('status', 'idle')}")
                self.logger.info(f"  - 베팅 대기 중: {tracker.is_waiting_for_result()}")
                
                if tracker.is_waiting_for_result():
                    self.logger.info(f"  - 베팅 타입: {tracker.get_bet_type()}")
                    self.logger.info(f"  - 베팅 라운드: {tracker.get_bet_round()}")
                
                # 베팅 통계
                stats = self.tm.game_processor.get_betting_statistics()
                self.logger.info(f"  - 총 게임 수: {stats.get('total_games', 0)}")
                self.logger.info(f"  - 승률(10게임): {stats.get('win_rate_10', 0)}%")
                self.logger.info(f"  - 연속 승/패: 승{stats.get('consecutive_results', {}).get('consecutive_wins', 0)}회, "
                               f"패{stats.get('consecutive_results', {}).get('consecutive_losses', 0)}회")
            
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
                    
                    # 현재 베팅 추적 상태와 비교
                    current_round = server_data.get('round_number', 0)
                    if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                        bet_round = self.tm.game_processor.betting_tracker.get_bet_round()
                        if bet_round and current_round > bet_round:
                            self.logger.info(f"🎲 베팅 결과 대기 중: 베팅 라운드 {bet_round} → 현재 라운드 {current_round}")
                else:
                    self.logger.warning("❌ 실시간 방 분석 실패")
            
        except Exception as e:
            self.logger.error(f"방 상태 디버그 오류: {e}")

    def handle_room_exit(self):
        """방 나가기 처리 - 베팅 추적 정리"""
        try:
            self.logger.info("🚪 방 나가기 처리 시작")
            
            # 베팅 추적기 상태 확인
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                tracker = self.tm.game_processor.betting_tracker
                
                # 아직 결과 대기 중인 베팅이 있는지 확인
                if tracker.is_waiting_for_result():
                    bet_info = tracker.get_current_bet_info()
                    self.logger.warning(f"⚠️ 미확인 베팅 결과: {bet_info}")
                    
                    # 강제로 패배 처리 (방 나가기 = 결과 확인 불가)
                    tracker.betting_result = 'lose'
                    tracker.bet_result_confirmed = True
                    
                    # 베팅 히스토리에 추가
                    tracker._add_to_history()
                
                # 추적기 초기화
                tracker.reset_tracking()
                self.logger.info("베팅 추적기 초기화 완료")
            
            # 게임 상태 초기화
            self.tm.current_room_name = ""
            self.tm.current_target_room = None
            self.tm.game_count = 0
            self.tm.result_count = 0
            self.tm.processed_rounds = set()
            
            self.logger.info("✅ 방 나가기 처리 완료")
            
        except Exception as e:
            self.logger.error(f"방 나가기 처리 오류: {e}")

    def verify_room_streak_before_betting(self, room_id: str, room_name: str, expected_streak: int) -> bool:
        """베팅 전 연패 상태 재확인 - 베팅 추적과 연동"""
        try:
            self.logger.info(f"🔍 베팅 전 연패 재확인: {room_name} (예상: {expected_streak}연패)")
            
            # 현재 베팅 대기 중이면 확인 생략
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                if self.tm.game_processor.betting_tracker.is_waiting_for_result():
                    self.logger.info("이미 베팅 결과 대기 중 - 연패 재확인 생략")
                    return True
            
            # iframe에서 현재 상태 확인
            game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=room_name,
                log_always=True,
                desired_pb_count=15
            )
            
            if not game_state:
                self.logger.error("게임 상태 확인 실패")
                return False
            
            # 연패 계산
            results = game_state.get('filtered_results', [])
            if len(results) < expected_streak:
                self.logger.warning(f"데이터 부족: {len(results)}개 < {expected_streak}연패")
                return False
            
            # 마지막 N개 결과 확인
            recent_results = results[-expected_streak:]
            last_result = recent_results[-1] if recent_results else None
            
            # 모두 같은 결과인지 확인
            is_streak = all(r == last_result for r in recent_results) if last_result else False
            
            if is_streak:
                self.logger.info(f"✅ 연패 확인: {last_result} {expected_streak}연패 유지")
                return True
            else:
                self.logger.warning(f"❌ 연패 깨짐: {recent_results}")
                return False
                
        except Exception as e:
            self.logger.error(f"연패 재확인 오류: {e}")
            return False