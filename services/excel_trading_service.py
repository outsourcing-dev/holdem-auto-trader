# services/excel_trading_service.py
import logging
import openpyxl
from typing import Dict, Any, Tuple
from utils.excel_manager import ExcelManager

class ExcelTradingService:
    def __init__(self, main_window, logger=None):
        """
        Excel 트레이딩 서비스 초기화
        
        Args:
            main_window (QMainWindow): 메인 윈도우 객체
            logger (logging.Logger, optional): 로깅을 위한 로거 객체
        """
        self.main_window = main_window
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.excel_manager = ExcelManager()

    # services/excel_trading_service.py
    def process_game_results(self, game_state: Dict[str, Any], game_count: int, current_room_name: str):
        """
        게임 결과를 처리하고 필요한 정보를 반환합니다.
        
        Args:
            game_state (dict): 게임 상태 정보
            game_count (int): 현재 게임 카운트
            current_room_name (str): 현재 방 이름
        
        Returns:
            Tuple[str, int, list, str]: (마지막 열, 새 게임 카운트, 최근 결과 리스트, PICK 값)
        """
        new_game_count = game_state['round']
        latest_result = game_state.get('latest_result')
        recent_results = game_state.get('recent_results', [])
        actual_results = game_state.get('actual_results', [])

        # 새로운 결과가 있는지 확인
        has_new_result = new_game_count > game_count and latest_result is not None

        # 새로운 결과가 없을 때
        if not has_new_result:
            self.logger.info("새로운 게임 결과 없음")
            return None, new_game_count, recent_results, None

        self.logger.info(f"새로운 게임 결과 감지: {latest_result}")

        # 첫 실행 여부 확인
        is_first_run = game_count == 0

        # 첫 실행 시 또는 첫 결과일 때 처리
        if is_first_run and actual_results:
            self.logger.info("첫 실행 감지: 엑셀에 최근 10개 결과 기록")
            self.excel_manager.write_filtered_game_results([], actual_results)
            
            last_column_idx = 1 + len(actual_results)
            last_column = openpyxl.utils.get_column_letter(last_column_idx)
        else:
            # 현재 열 찾기
            current_column = self.excel_manager.get_current_column()
            
            if not current_column:
                self.logger.warning("기록할 빈 열을 찾을 수 없음")
                return None, new_game_count, recent_results, None

            # 새 결과 기록
            self.logger.info(f"{current_column}3에 새 결과 '{latest_result}' 기록 중...")
            self.excel_manager.write_game_result(current_column, latest_result)
            last_column = current_column

        # 엑셀 저장
        save_success = self.excel_manager.save_with_app()

        if not save_success or not last_column:
            self.logger.warning("자동 Excel 저장에 실패했습니다.")
            return None, new_game_count, recent_results, None

        # 다음 열의 PICK 값 확인
        next_pick = self.excel_manager.check_next_column_pick(last_column)
        
        return last_column, new_game_count, recent_results, next_pick
        """
        게임 결과를 처리하고 필요한 정보를 반환합니다.
        
        Args:
            game_state (dict): 게임 상태 정보
            game_count (int): 현재 게임 카운트
            current_room_name (str): 현재 방 이름
        
        Returns:
            Tuple[str, int, list]: (마지막 열, 새 게임 카운트, 최근 결과 리스트)
        """
        new_game_count = game_state['round']
        latest_result = game_state.get('latest_result')
        recent_results = game_state.get('recent_results', [])
        actual_results = game_state.get('actual_results', [])

        # 새로운 결과가 있는지 확인
        has_new_result = new_game_count > game_count and latest_result is not None

        if not has_new_result:
            self.logger.info("새로운 게임 결과 없음")
            return None, new_game_count, recent_results

        self.logger.info(f"새로운 게임 결과 감지: {latest_result}")

        # 첫 실행 여부 확인
        is_first_run = game_count == 0

        # 첫 실행 시 또는 첫 결과일 때 처리
        if is_first_run and actual_results:
            self.logger.info("첫 실행 감지: 엑셀에 최근 10개 결과 기록")
            self.excel_manager.write_filtered_game_results([], actual_results)
            
            last_column_idx = 1 + len(actual_results)
            last_column = openpyxl.utils.get_column_letter(last_column_idx)
        else:
            # 현재 열 찾기
            current_column = self.excel_manager.get_current_column()
            
            if not current_column:
                self.logger.warning("기록할 빈 열을 찾을 수 없음")
                return None, new_game_count, recent_results

            # 새 결과 기록
            self.logger.info(f"{current_column}3에 새 결과 '{latest_result}' 기록 중...")
            self.excel_manager.write_game_result(current_column, latest_result)
            last_column = current_column

        # 엑셀 저장
        save_success = self.excel_manager.save_with_app()

        if not save_success or not last_column:
            self.logger.warning("자동 Excel 저장에 실패했습니다.")
            return None, new_game_count, recent_results

        # 다음 열의 PICK 값 확인
        next_pick = self.excel_manager.check_next_column_pick(last_column)
        
        return last_column, new_game_count, recent_results, next_pick