# utils/trading_manager_modules/betting_executor.py
import logging
from utils.trading_manager_helpers import get_widget_position


class BettingExecutor:
    """베팅 실행 전담 클래스"""
    
    def __init__(self, trading_manager):
        self.tm = trading_manager
        self.logger = trading_manager.logger

    def execute_betting(self, pick: str, round_number: int, current_game: int = None):
        """베팅 실행 - 최신 상태 재확인 및 추적 통합"""
        try:
            # 🔥 현재 타겟 방이 있는지 먼저 확인
            if not self.tm.current_target_room:
                self.logger.debug("현재 타겟 방이 없음 - 베팅 취소")
                return
                
            streak_info = ""
            if self.tm.current_target_room:
                streak_count = self.tm.current_target_room.get('streak_count', 0)
                streak_info = f" (연패: {streak_count})"
            
            self.logger.info(f"⚡ 베팅 실행 전 빠른 상태 확인...")
            
            # 🔥 베팅 직전 최신 게임 상태 재확인
            latest_state = self._get_latest_game_state()
            if latest_state:
                latest_round = latest_state.get('round', 0)
                latest_current_game = latest_state.get('current_game', 0)
                
                # 라운드가 변경되었는지 확인
                if latest_round != round_number:
                    self.logger.warning(f"⚠️ 라운드 변경 감지: {round_number} → {latest_round}")
                    self.logger.warning(f"⚠️ 베팅 취소 - 라운드 동기화 필요")
                    return
                
                # current_game 업데이트
                if latest_current_game > 0:
                    current_game = latest_current_game
            
            # 🔥 실제 계산은 BettingResultTracker가 중앙 관리 - 표시용 정보만 로깅
            display_round = round_number  # 표시용 (마지막 완료된 라운드)
            display_current_game = current_game if current_game else "N/A"
            
            self.logger.info(f"🎯 베팅 실행 준비: {pick}{streak_info}")
            self.logger.info(f"  - 완료된 라운드: {display_round}")
            self.logger.info(f"  - 진행 중인 게임: {display_current_game}")
            self.logger.info(f"  - 베팅 라운드 계산: BettingResultTracker 담당")
            
            # 베팅 금액 계산 - 마틴 서비스 사용 (위젯 동기화 보장)
            widget_pos = get_widget_position(self.tm.main_window)
            
            # 🔥 중요: martin_service 사용으로 변경 (위젯과 완벽 동기화)
            if hasattr(self.tm, 'martin_service'):
                # 현재 위젯 상태 디버깅
                self.logger.info(f"🔍 베팅 전 위젯 상태 확인:")
                self.logger.info(f"   - get_widget_position: {widget_pos}")
                if hasattr(self.tm.main_window, 'betting_widget'):
                    actual_pos = self.tm.main_window.betting_widget.room_position_counter
                    self.logger.info(f"   - 실제 위젯 카운터: {actual_pos}")
                    if actual_pos != widget_pos:
                        self.logger.warning(f"   ⚠️ 포지션 불일치 감지!")
                
                bet_amount = self.tm.martin_service.get_current_bet_amount()
                self.logger.info(f"💰 마틴 서비스에서 베팅 금액 가져옴: {bet_amount:,}원 (위젯 포지션: {widget_pos+1})")
            else:
                # Fallback: 기존 방식 사용
                bet_amount = self.tm.excel_trading_service.get_current_bet_amount(widget_position=widget_pos)
                self.logger.warning(f"⚠️ 마틴 서비스 없음 - Excel 서비스 사용: {bet_amount:,}원")
            
            # 🔥 먼저 베팅 실행 - 성공 후에만 추적 시작
            bet_success = self.tm.betting_service.place_bet(
                pick,
                self.tm.current_room_name,
                display_round,  # 표시된 라운드 (베팅 서비스에서 재확인됨)
                self.tm.is_trading_active,
                bet_amount
            )
            
            # 🔥 베팅 처리는 BettingService에서 중앙 관리 (중복 제거)
            # BettingService.place_bet()이 모든 베팅 추적을 담당하므로 여기서는 제거됨
            
            if bet_success:
                # BettingResultTracker에서 베팅 정보 가져오기 (로깅용)
                actual_betting_round = None
                if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                    actual_betting_round = self.tm.game_processor.betting_tracker.get_bet_round()
                
                self.logger.info(f"✅ 베팅 성공: {pick}, 금액: {bet_amount:,}원")
                if actual_betting_round:
                    self.logger.info(f"  - ⭐ 베팅 대상 라운드: {actual_betting_round}{streak_info}")
                
                # iframe 로거에 베팅 액션 기록 (선택적)
                if hasattr(self.tm, 'iframe_logger') and self.tm.iframe_logger and self.tm.iframe_logger.is_logging:
                    try:
                        betting_details = {
                            'action': 'PLACE_BET',
                            'pick': pick,
                            'amount': bet_amount,
                            'round': actual_betting_round,
                            'room': self.tm.current_room_name,
                            'martin_step': widget_pos + 1,
                            'streak_count': self.tm.current_target_room.get('streak_count', 0) if self.tm.current_target_room else 0
                        }
                        self.tm.iframe_logger.log_betting_action('베팅 실행', betting_details)
                        self.tm.iframe_logger.capture_iframe_snapshot()
                    except Exception as e:
                        self.logger.debug(f"iframe 베팅 로깅 실패: {e}")
                
                self.tm.main_window.update_betting_status(
                    pick=pick, 
                    bet_amount=bet_amount,
                    streak_info=streak_info
                )
            else:
                self.logger.warning(f"❌ 베팅 실패: {pick}")
                # 베팅 실패 시 상태 복구
                self._recover_betting_state()
                    
        except Exception as e:
            self.logger.error(f"베팅 실행 오류: {e}")
            # 오류 시 상태 복구
            self._recover_betting_state()
    
    def _recover_betting_state(self):
        """베팅 실패 또는 오류 시 상태 복구"""
        try:
            # 베팅 추적기 초기화
            if hasattr(self.tm, 'game_processor') and hasattr(self.tm.game_processor, 'betting_tracker'):
                self.tm.game_processor.betting_tracker.reset_tracking()
            
            # 베팅 서비스 상태 초기화
            if hasattr(self.tm, 'betting_service'):
                self.tm.betting_service.has_bet_current_round = False
            
            # 게임 모니터링 워커 베팅 플래그 리셋
            if (hasattr(self.tm, 'room_manager_handler') and 
                hasattr(self.tm.room_manager_handler, 'game_monitoring_worker')):
                self.tm.room_manager_handler.game_monitoring_worker.reset_betting_flag()
            
            # 게임 프로세서 쿨다운 리셋
            if hasattr(self.tm, 'game_processor'):
                self.tm.game_processor.betting_cooldown = False
                self.tm.game_processor.consecutive_requests = 0
            
            self.logger.info("✅ 베팅 상태 복구 완료 - 다음 베팅 가능")
            
        except Exception as e:
            self.logger.error(f"베팅 상태 복구 오류: {e}")
                
    def generate_pick_for_streak_room(self) -> str:
        """연패 방을 위한 픽 생성"""
        try:
            if not self.tm.current_target_room:
                return 'P'
            
            # ExcelTradingService의 ChoicePickSystem 사용
            if hasattr(self.tm.excel_trading_service, 'choice_pick_system'):
                pick = self.tm.excel_trading_service.choice_pick_system.generate_choice_pick()
                if pick in ['P', 'B']:
                    return pick
            
            return 'P'  # 기본값
            
        except Exception as e:
            self.logger.error(f"픽 생성 오류: {e}")
            return 'P'

    def _get_latest_game_state(self):
        """베팅 직전 최신 게임 상태 확인"""
        try:
            if not hasattr(self.tm, 'game_monitoring_service') or not self.tm.game_monitoring_service:
                self.logger.warning("게임 모니터링 서비스가 없음")
                return None
            
            # 현재 방 이름에서 room_id 추출 (필요시)
            current_room_name = self.tm.current_room_name
            room_id = None
            if hasattr(self.tm, 'current_target_room') and self.tm.current_target_room:
                room_id = self.tm.current_target_room.get('room_id')
            
            # 최신 게임 상태 파싱 (원하는 결과 개수 15개)
            latest_game_state = self.tm.game_monitoring_service.get_current_game_state_with_server_format(
                room_id=room_id,
                room_name=current_room_name,
                log_always=True,
                desired_pb_count=15
            )
            
            if latest_game_state:
                self.logger.info(f"✅ 최신 게임 상태 확인 완료: 라운드 {latest_game_state.get('round', 0)}")
                return latest_game_state
            else:
                self.logger.warning("최신 게임 상태 파싱 실패")
                return None
                
        except Exception as e:
            self.logger.error(f"최신 게임 상태 확인 오류: {e}")
            return None

    def _get_updated_prediction(self, latest_results, current_pick):
        """서버에 최신 결과로 새로운 예측값 요청"""
        try:
            if not hasattr(self.tm, 'server_client') or not self.tm.server_client:
                self.logger.warning("서버 클라이언트가 없음 - 기존 예측값 유지")
                return current_pick
            
            if not latest_results or len(latest_results) < 5:
                self.logger.warning(f"결과 데이터 부족 ({len(latest_results) if latest_results else 0}개) - 기존 예측값 유지")
                return current_pick
            
            # 현재 타겟 방의 room_id 가져오기
            room_id = None
            if hasattr(self.tm, 'current_target_room') and self.tm.current_target_room:
                room_id = self.tm.current_target_room.get('room_id')
            
            if not room_id:
                self.logger.warning("room_id가 없음 - 기존 예측값 유지")
                return current_pick
            
            self.logger.info(f"🔄 서버에 최신 예측값 요청: {len(latest_results)}개 결과로 업데이트")
            
            # 서버에 최신 데이터로 예측값 요청
            new_prediction = self.tm.server_client.get_next_prediction(room_id, latest_results)
            
            if new_prediction and new_prediction in ['P', 'B']:
                if new_prediction != current_pick:
                    self.logger.info(f"🔄 서버 예측값 업데이트: {current_pick} → {new_prediction}")
                else:
                    self.logger.info(f"✅ 서버 예측값 동일: {new_prediction}")
                return new_prediction
            else:
                self.logger.warning(f"서버 예측값 유효하지 않음: {new_prediction} - 기존값 유지")
                return current_pick
                
        except Exception as e:
            self.logger.error(f"서버 예측값 업데이트 오류: {e} - 기존값 유지")
            return current_pick