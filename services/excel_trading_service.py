# services/excel_trading_service.py
import logging
from typing import Tuple, List
from utils.choice_pick import ChoicePickSystem

class ExcelTradingService:
    def __init__(self, main_window, logger=None):
        """ChoicePick 기반 베팅 서비스 초기화"""
        self.main_window = main_window
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.choice_pick_system = ChoicePickSystem(logger=self.logger)

    def process_game_results(self, game_state, game_count, current_room_name, log_on_change=False):
        if not game_state:
            return None, game_count, [], None

        new_game_count = game_state['round']
        latest_result = game_state.get('latest_result')
        recent_results = game_state.get('recent_results', [])
        filtered_results = game_state.get('filtered_results', [])

        if self._is_duplicate_result(latest_result, new_game_count):
            return "DUPLICATE", new_game_count, recent_results, self.choice_pick_system.generate_choice_pick()

        is_first_run = game_count == 0 or game_count < new_game_count - 3

        if is_first_run and filtered_results:
            self.choice_pick_system.should_refresh_data = True
            return self._handle_first_run(filtered_results, recent_results, new_game_count)

        has_new_result = new_game_count > game_count and latest_result is not None
        if not has_new_result:
            if not log_on_change:
                self.logger.info("새로운 게임 결과 없음")
            return None, new_game_count, recent_results, None

        self.logger.info(f"새로운 게임 결과 감지: {latest_result}")
        return self._process_new_result(latest_result, new_game_count, recent_results)

    def _process_new_result(self, latest_result, new_game_count, recent_results):
        if latest_result == 'T':
            return self._handle_tie_result("AUTO", new_game_count, recent_results)

        if latest_result in ['P', 'B']:
            return self._record_new_result(latest_result, "AUTO", new_game_count, recent_results)

        return None, new_game_count, recent_results, None

    def _handle_first_run(self, filtered_results, recent_results, actual_game_count):
        self.logger.info(f"첫 실행 감지: 최근 결과 {len(filtered_results)}개 추가")
        self.choice_pick_system.clear()
        self.choice_pick_system.add_multiple_results(filtered_results)
        next_pick = self.choice_pick_system.generate_choice_pick()
        start_count = max(1, actual_game_count - len(filtered_results))
        self._update_processed_rounds(filtered_results, start_count=start_count)
        return "PREDICTED", actual_game_count, recent_results, next_pick

    def _record_new_result(self, result, column, new_game_count, recent_results):
        if recent_results and recent_results[-1] == result:
            recent_results = recent_results[:-1]

        filtered_results = [r for r in recent_results if r in ['P', 'B']]
        filtered_results.append(result)

        self.choice_pick_system.clear()
        self.choice_pick_system.add_multiple_results(filtered_results)

        if hasattr(self.main_window, 'trading_manager'):
            start_count = new_game_count - len(filtered_results) + 1
            self._update_processed_rounds(filtered_results, start_count=start_count)

        next_pick = self.choice_pick_system.generate_choice_pick()
        return column, new_game_count, recent_results, next_pick

    def _is_duplicate_result(self, latest_result, new_game_count):
        result_id = f"{new_game_count}_{latest_result}"
        if hasattr(self.main_window, 'trading_manager') and result_id in self.main_window.trading_manager.processed_rounds:
            return True
        return False

    def _update_processed_rounds(self, results, start_count=None):
        if hasattr(self.main_window, 'trading_manager'):
            base_count = start_count or 1
            for i, res in enumerate(results):
                result_id = f"{base_count+i}_{res}"
                self.main_window.trading_manager.processed_rounds.add(result_id)

    def _handle_tie_result(self, current_column, new_game_count, recent_results):
        self.logger.info(f"TIE 결과 감지 - 이전 PICK 유지")
        current_pick = self.choice_pick_system.current_pick
        if current_pick is None:
            current_pick = self.choice_pick_system.generate_choice_pick()
            self.logger.info(f"이전 PICK 값이 없어 새로 예측: {current_pick}")
        else:
            self.logger.info(f"타이 후 이전 PICK 유지: {current_pick}")
        return current_column, new_game_count, recent_results, current_pick

    def get_current_bet_amount(self, widget_position=0):
        return self.choice_pick_system.get_current_bet_amount()

    def set_martin_amounts(self, amounts):
        self.choice_pick_system.set_martin_amounts(amounts)

    def record_betting_result(self, is_win):
        self.choice_pick_system.record_betting_result(is_win)

    def clear(self):
        self.choice_pick_system.clear()
