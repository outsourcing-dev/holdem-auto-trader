import logging
import time


class GameProcessor:
    """게임 데이터 처리 전담 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger

    def on_game_data_received(self, game_data: dict):
        """게임 데이터 수신 처리"""
        try:
            self.tm.last_game_data = game_data
            self.tm.message_count += 1
            
            # 현재 방과 일치하는 데이터인지 확인
            room_name = game_data.get('room_name', '')
            if self.tm.current_target_room and room_name:
                target_room_name = self.tm.current_target_room.get('room_name', '')
                if target_room_name in room_name:
                    # 현재 방의 게임 데이터 처리
                    self._process_current_room_game_data(game_data)
                
        except Exception as e:
            self.logger.error(f"게임 데이터 수신 처리 오류: {e}")

    def _process_current_room_game_data(self, game_data: dict):
        """현재 방의 게임 데이터 처리"""
        try:
            round_number = game_data.get('round_number', 0)
            latest_result = game_data.get('latest_result', '')
            
            # 게임 카운트 업데이트
            if round_number > self.tm.game_count:
                self.tm.game_count = round_number
            
            # 새로운 결과가 있는 경우 처리
            if latest_result and latest_result in ['P', 'B', 'T']:
                self._handle_game_result(game_data)
            
            # 베팅 타이밍 확인
            if self.tm.current_target_room and not self.tm.room_entry_in_progress:
                self._check_betting_opportunity(game_data)
            
        except Exception as e:
            self.logger.error(f"현재 방 게임 데이터 처리 오류: {e}")

    def _handle_game_result(self, game_data: dict):
        """게임 결과 처리"""
        try:
            latest_result = game_data.get('latest_result', '')
            round_number = game_data.get('round_number', 0)
            
            # 중복 결과 방지
            result_id = f"{round_number}_{latest_result}"
            if result_id in self.tm.processed_rounds:
                return
            
            self.tm.processed_rounds.add(result_id)
            self.tm.result_count += 1
            
            self.logger.info(f"🎯 새로운 게임 결과: 라운드 {round_number}, 결과 {latest_result}")
            
            # 베팅 결과 확인
            if (hasattr(self.tm.betting_service, 'has_bet_current_round') and 
                self.tm.betting_service.has_bet_current_round):
                
                last_bet = self.tm.betting_service.get_last_bet()
                
                if last_bet and last_bet['type'] in ['P', 'B']:
                    result_status = self.tm.bet_helper.process_bet_result(
                        last_bet['type'], 
                        latest_result, 
                        round_number
                    )
                    
                    self.logger.info(f"베팅 결과 처리: {result_status}")
                    
                    if result_status == 'win':
                        self.tm.just_won = True
                        self._handle_win_result()
                    elif result_status == 'lose':
                        self._handle_lose_result()
                    elif result_status == 'tie':
                        self._handle_tie_result()
            
            # ExcelTradingService에 결과 추가
            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                if latest_result in ['P', 'B']:
                    self.tm.excel_trading_service.choice_pick_system.add_result(latest_result)
                    
        except Exception as e:
            self.logger.error(f"게임 결과 처리 오류: {e}")

    def _check_betting_opportunity(self, game_data: dict):
        """서버 기반 베팅 기회 확인"""
        try:
            # 이미 베팅했으면 베팅 안함
            if hasattr(self.tm.betting_service, 'has_bet_current_round') and self.tm.betting_service.has_bet_current_round:
                return
            
            # 첫 결과 대기 중이면서 새로운 결과가 왔을 때만 대기 해제
            if self.tm.wait_first_result:
                latest_result = game_data.get('latest_result')
                if latest_result and latest_result in ['P', 'B', 'T']:
                    self.tm.wait_first_result = False
                    self.logger.info(f"첫 결과 수신 - 대기 모드 해제: {latest_result}")
                    
                    # 타이가 아닌 경우에만 다음 베팅 진행
                    if latest_result in ['P', 'B']:
                        self._process_game_result_and_bet(game_data)
                return
            
            # 현재 타겟 방이 없으면 베팅 안함
            if not self.tm.current_target_room:
                return
            
            # 새로운 게임 결과가 있을 때만 베팅 진행
            latest_result = game_data.get('latest_result')
            if latest_result and latest_result in ['P', 'B']:
                self._process_game_result_and_bet(game_data)
                
        except Exception as e:
            self.logger.error(f"베팅 기회 확인 오류: {e}")

    def _process_game_result_and_bet(self, game_data: dict):
        """게임 결과 처리 후 다음 베팅 실행"""
        try:
            latest_result = game_data.get('latest_result')
            current_results = game_data.get('game_results', [])
            
            self.logger.info(f"🎮 게임 결과 처리: {latest_result}")
            
            # 1. 이전 베팅 결과 확인 및 처리
            if hasattr(self.tm.betting_service, 'has_bet_current_round') and self.tm.betting_service.has_bet_current_round:
                last_bet = self.tm.betting_service.get_last_bet()
                if last_bet and last_bet['type'] in ['P', 'B']:
                    # 베팅 결과 처리
                    result_status = self.tm.bet_helper.process_bet_result(
                        last_bet['type'], 
                        latest_result, 
                        game_data.get('round_number', self.tm.game_count)
                    )
                    self.logger.info(f"이전 베팅 결과: {result_status}")
                    
                    # 베팅 상태 초기화
                    self.tm.betting_service.has_bet_current_round = False
            
            # 2. 서버에 최신 결과 포함해서 다음 예측 요청
            room_id = self.tm.current_target_room.get('room_id', '')
            
            # 최신 결과를 포함한 결과 리스트 준비
            updated_results = current_results.copy() if current_results else []
            if latest_result not in updated_results:
                updated_results.append(latest_result)
            
            # TIE('T')를 제외한 값만 서버로 전달
            filtered_results = [r for r in updated_results if r in ['P', 'B']]
            
            self.logger.info(f"📡 서버 예측 요청: 최신 결과 {latest_result} 포함, 필터링된 결과: {filtered_results}")
            
            # 3. 서버에서 다음 예측값 요청
            next_pick = self.tm.server_client.get_next_prediction(room_id, filtered_results)
            self.logger.info(f"🎯 [서버 예측] 다음 베팅 예측: {next_pick}")
            
            # 4. 유효한 예측값이면 베팅 실행
            if next_pick in ['P', 'B']:
                # 잠시 대기 후 베팅 (게임 전환 시간 고려)
                time.sleep(1)
                round_number = game_data.get('round_number', self.tm.game_count + 1)
                self.tm.betting_executor.execute_betting(next_pick, round_number)
            else:
                self.logger.info(f"🎯 [서버 예측] 베팅 안함: {next_pick}")
                
        except Exception as e:
            self.logger.error(f"게임 결과 처리 및 베팅 오류: {e}")

    def _handle_win_result(self):
        """승리 결과 처리"""
        try:
            self.logger.info("🎉 승리 처리 - 새로운 연패 방 검색")
            
            # 위젯 초기화
            if hasattr(self.tm.main_window, 'betting_widget'):
                self.tm.main_window.betting_widget.room_position_counter = 0
                self.tm.main_window.betting_widget.reset_step_markers()
            
            # 마틴 서비스 초기화
            if hasattr(self.tm, 'martin_service'):
                self.tm.martin_service.reset()
            
            # 현재 방 정보 초기화
            self.tm.current_target_room = None
            self.tm.target_streak_rooms = []
            
            # 새로운 연패 방 검색 모드로 전환
            self.tm.streak_handler.return_to_streak_monitoring()
            
        except Exception as e:
            self.logger.error(f"승리 처리 오류: {e}")

    def _handle_lose_result(self):
        """패배 결과 처리"""
        try:
            self.logger.info("❌ 패배 처리")
            
            # 위젯 카운터 증가
            if hasattr(self.tm.main_window, 'betting_widget'):
                current_pos = getattr(self.tm.main_window.betting_widget, 'room_position_counter', 0)
                self.tm.main_window.betting_widget.room_position_counter = current_pos + 1
                self.tm.main_window.betting_widget.set_step_marker(current_pos, "X")
            
            # 연패 확인
            if self._check_consecutive_losses():
                self.logger.info("연패 조건 달성 - 새로운 방 검색")
                self.tm.streak_handler.return_to_streak_monitoring()
                
        except Exception as e:
            self.logger.error(f"패배 처리 오류: {e}")

    def _handle_tie_result(self):
        """무승부 결과 처리"""
        try:
            self.logger.info("🤝 무승부 처리")
            
            # 베팅 상태 초기화
            self.tm.betting_service.has_bet_current_round = False
            self.tm.had_tie_last_round = True
            
        except Exception as e:
            self.logger.error(f"무승부 처리 오류: {e}")

    def _check_consecutive_losses(self) -> bool:
        """연패 확인"""
        try:
            if hasattr(self.tm, 'excel_trading_service'):
                return self.tm.excel_trading_service.should_change_room()
            return False
        except Exception as e:
            self.logger.error(f"연패 확인 오류: {e}")
            return False