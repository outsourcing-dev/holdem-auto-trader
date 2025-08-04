# services/excel_trading_service.py (단순화)
import logging
from typing import Tuple, List
from utils.choice_pick import ChoicePickSystem

class ExcelTradingService:
    """
    Excel 기반 트레이딩 서비스 - 서버 기반으로 단순화
    복잡한 분석 로직은 서버에서 처리하고, 기본적인 픽 생성만 담당
    """
    
    def __init__(self, main_window, logger=None):
        """서비스 초기화"""
        self.main_window = main_window
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # 단순화된 ChoicePickSystem 사용
        self.choice_pick_system = ChoicePickSystem(logger=self.logger)
        
        self.logger.info("단순화된 ExcelTradingService 초기화 완료")

    def process_game_results(self, game_state, game_count, current_room_name, log_on_change=False):
        """게임 결과 처리 - 단순화"""
        try:
            if not game_state:
                return None, game_count, [], None

            new_game_count = game_state['round']
            latest_result = game_state.get('latest_result')
            filtered_results = game_state.get('filtered_results', [])

            # 중복 결과 확인
            if self._is_duplicate_result(latest_result, new_game_count):
                return "DUPLICATE", new_game_count, [], self.choice_pick_system.generate_choice_pick()

            # 첫 실행인지 확인
            is_first_run = game_count == 0 or game_count < new_game_count - 3

            if is_first_run and filtered_results:
                return self._handle_first_run(filtered_results, new_game_count)

            # 새로운 결과가 있는지 확인
            has_new_result = new_game_count > game_count and latest_result is not None
            if not has_new_result:
                if not log_on_change:
                    self.logger.debug("새로운 게임 결과 없음")
                return None, new_game_count, [], None

            self.logger.info(f"새로운 게임 결과 감지: {latest_result}")
            return self._process_new_result(latest_result, new_game_count)

        except Exception as e:
            self.logger.error(f"게임 결과 처리 중 오류: {e}")
            return None, game_count, [], None

    def _handle_first_run(self, filtered_results, actual_game_count):
        """첫 실행 처리 - 단순화"""
        try:
            self.logger.info(f"첫 실행: 최근 결과 {len(filtered_results)}개 추가")
            
            # ChoicePickSystem 초기화 및 데이터 추가
            self.choice_pick_system.clear()
            self.choice_pick_system.add_multiple_results(filtered_results)

            # 방 입장 직후라면 픽 생성 하지 않음
            if self.choice_pick_system.wait_first_result:
                self.logger.info("방 입장 직후 - 픽 생성 생략")
                next_pick = "N"
                self.choice_pick_system.current_pick = "N"
            else:
                next_pick = self.choice_pick_system.generate_choice_pick()

            return "PREDICTED", actual_game_count, [], next_pick

        except Exception as e:
            self.logger.error(f"첫 실행 처리 중 오류: {e}")
            return None, actual_game_count, [], None

    def _process_new_result(self, latest_result, new_game_count):
        """새로운 결과 처리 - 단순화"""
        try:
            if latest_result == 'T':
                return self._handle_tie_result(new_game_count)

            if latest_result in ['P', 'B']:
                return self._record_new_result(latest_result, new_game_count)

            return None, new_game_count, [], None

        except Exception as e:
            self.logger.error(f"새로운 결과 처리 중 오류: {e}")
            return None, new_game_count, [], None

    def _record_new_result(self, result, new_game_count):
        """새로운 결과 기록 - 단순화"""
        try:
            # ChoicePickSystem에 결과 추가
            self.choice_pick_system.add_result(result)
            
            # 다음 픽 생성
            next_pick = self.choice_pick_system.generate_choice_pick()
            
            self.logger.info(f"결과 기록: {result}, 다음 픽: {next_pick}")
            
            return "AUTO", new_game_count, [], next_pick

        except Exception as e:
            self.logger.error(f"결과 기록 중 오류: {e}")
            return None, new_game_count, [], None

    def _handle_tie_result(self, new_game_count):
        """타이 결과 처리 - 단순화"""
        try:
            self.logger.info("타이 결과 감지 - 이전 픽 유지")
            
            # 이전 픽 유지
            current_pick = self.choice_pick_system.current_pick
            if current_pick is None:
                current_pick = self.choice_pick_system.generate_choice_pick()
                self.logger.info(f"이전 픽이 없어 새로 생성: {current_pick}")
            else:
                self.logger.info(f"타이 후 이전 픽 유지: {current_pick}")

            return "AUTO", new_game_count, [], current_pick

        except Exception as e:
            self.logger.error(f"타이 결과 처리 중 오류: {e}")
            return None, new_game_count, [], None

    def _is_duplicate_result(self, latest_result, new_game_count):
        """중복 결과 확인"""
        try:
            if not hasattr(self.main_window, 'trading_manager'):
                return False
                
            result_id = f"{new_game_count}_{latest_result}"
            processed_rounds = getattr(self.main_window.trading_manager, 'processed_rounds', set())
            
            return result_id in processed_rounds

        except Exception as e:
            self.logger.error(f"중복 결과 확인 중 오류: {e}")
            return False

    def get_current_bet_amount(self, widget_position=0):
        """현재 베팅 금액 반환"""
        try:
            return self.choice_pick_system.get_current_bet_amount(widget_position=widget_position)
        except Exception as e:
            self.logger.error(f"베팅 금액 확인 중 오류: {e}")
            return 1000  # 기본값

    def set_martin_amounts(self, amounts):
        """마틴 금액 설정"""
        try:
            self.choice_pick_system.set_martin_amounts(amounts)
            self.logger.info(f"마틴 금액 설정 완료: {amounts}")
        except Exception as e:
            self.logger.error(f"마틴 금액 설정 중 오류: {e}")

    def record_betting_result(self, is_win):
        """베팅 결과 기록"""
        try:
            self.choice_pick_system.record_betting_result(is_win)
            if self.logger:
                result_text = "승리" if is_win else "패배"
                self.logger.info(f"베팅 결과 기록: {result_text}")
        except Exception as e:
            self.logger.error(f"베팅 결과 기록 중 오류: {e}")

    def should_change_room(self) -> bool:
        """방 이동 필요 여부 확인"""
        try:
            return self.choice_pick_system.should_change_room()
        except Exception as e:
            self.logger.error(f"방 이동 확인 중 오류: {e}")
            return False
    
    def record_room_final_stats(self, room_name: str, stats: dict):
        """방 퇴장 시 최종 통계 기록"""
        try:
            self.logger.info(f"📊 방 '{room_name}' 최종 통계 기록:")
            self.logger.info(f"  - 총 베팅: {stats.get('total_bets', 0)}회")
            self.logger.info(f"  - 승률: {stats.get('win_rate', 0):.1f}%")
            self.logger.info(f"  - 최대 연승: {stats.get('max_win_streak', 0)}회")
            self.logger.info(f"  - 최대 연패: {stats.get('max_lose_streak', 0)}회")
            
            # 향후 파일 저장 기능 확장 가능
            # CSV나 Excel 파일로 저장하는 로직을 여기에 추가할 수 있음
            
        except Exception as e:
            self.logger.error(f"방 최종 통계 기록 오류: {e}")
    
    def reset_after_room_change(self, preserve_martin=False):
        """방 이동 후 초기화"""
        try:
            self.choice_pick_system.reset_after_room_change(preserve_martin)
            self.logger.info(f"방 이동 후 초기화 완료 (마틴 유지: {preserve_martin})")
        except Exception as e:
            self.logger.error(f"방 이동 후 초기화 중 오류: {e}")

    def clear(self):
        """전체 초기화"""
        try:
            self.choice_pick_system.clear()
            self.logger.info("ExcelTradingService 전체 초기화 완료")
        except Exception as e:
            self.logger.error(f"전체 초기화 중 오류: {e}")