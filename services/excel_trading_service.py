# services/excel_trading_service.py
import logging
import openpyxl
from typing import Dict, Any, Tuple
from utils.excel_manager import ExcelManager
import time
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
        
    def process_game_results(self, game_state, game_count, current_room_name, log_on_change=False):
        """
        게임 결과를 처리하고 필요한 정보를 반환합니다.
        """
        new_game_count = game_state['round']
        latest_result = game_state.get('latest_result')
        recent_results = game_state.get('recent_results', [])
        actual_results = game_state.get('actual_results', [])
        
        # 결과 중복 처리 방지 - 유니크 ID 생성 (라운드 번호 + 결과 값)
        if latest_result:
            result_id = f"{new_game_count}_{latest_result}"
            
            # 이미 처리한 결과인지 확인 (TradingManager의 processed_rounds 사용)
            if hasattr(self.main_window, 'trading_manager') and result_id in self.main_window.trading_manager.processed_rounds:
                self.logger.info(f"이미 처리된 결과 감지 (ID: {result_id}) - 중복 처리 방지")
                
                # 현재 열 찾기 - 이미 기록되어 있으므로 다음 열의 PICK 값만 확인
                current_column = self.excel_manager.get_current_column()
                if current_column:
                    prev_column = self.excel_manager.get_prev_column_letter(current_column)
                    next_pick = self.excel_manager.check_next_column_pick(prev_column)
                    return prev_column, new_game_count, recent_results, next_pick
                return None, new_game_count, recent_results, None

        # 첫 실행 여부 확인
        is_first_run = game_count == 0
        
        # 첫 실행 시 처리 (방 입장 직후)
        if is_first_run and actual_results:
            self.logger.info(f"첫 실행 감지: 엑셀에 최근 결과 {len(actual_results)}개 기록")
            # 전체 결과 초기화 및 기록
            success = self.excel_manager.write_filtered_game_results([], actual_results)
            if success:
                # 마지막 열 계산
                last_column_idx = 1 + len(actual_results)
                last_column = openpyxl.utils.get_column_letter(last_column_idx)
                # 다음 열의 PICK 값 확인
                next_pick = self.excel_manager.check_next_column_pick(last_column)
                
                # 결과 처리 성공 시 processed_rounds에 추가
                if hasattr(self.main_window, 'trading_manager'):
                    for i, res in enumerate(actual_results):
                        result_id = f"{new_game_count-len(actual_results)+i+1}_{res}"
                        self.main_window.trading_manager.processed_rounds.add(result_id)
                    
                return last_column, new_game_count, recent_results, next_pick
                
        # 새로운 결과가 있는지 확인 (첫 실행이 아닌 경우)
        has_new_result = new_game_count > game_count and latest_result is not None
        
        if not has_new_result:
            if not log_on_change:
                self.logger.info("새로운 게임 결과 없음")
            return None, new_game_count, recent_results, None

        # 새로운 결과가 있을 때는 항상 로깅
        self.logger.info(f"새로운 게임 결과 감지: {latest_result}")

        # 현재 열 찾기
        current_column = self.excel_manager.get_current_column()
        if not current_column:
            self.logger.warning("기록할 빈 열을 찾을 수 없음")
            return None, new_game_count, recent_results, None
        
        # 중요: 이미 결과가 기록되어 있는지 확인
        # current_column 열의 3행 값 확인
        existing_value = self.excel_manager.read_cell_value(current_column, 3)
        if existing_value is not None and existing_value != "":
            self.logger.warning(f"{current_column}3 셀에 이미 값이 존재함: {existing_value} - 중복 기록 방지")
            
            # 이미 기록된 경우 다음 열의 PICK 값만 확인
            next_column = self.excel_manager.get_next_column_letter(current_column)
            next_pick = self.excel_manager.check_next_column_pick(current_column)
            return current_column, new_game_count, recent_results, next_pick

        # 새 결과 기록
        self.logger.info(f"{current_column}3에 새 결과 '{latest_result}' 기록 중...")
        self.excel_manager.write_game_result(current_column, latest_result)
        last_column = current_column
        
        # 처리된 결과 추적 - ID 추가
        if hasattr(self.main_window, 'trading_manager') and latest_result:
            result_id = f"{new_game_count}_{latest_result}"
            self.main_window.trading_manager.processed_rounds.add(result_id)

        # 다음 열의 PICK 값 확인
        next_pick = self.excel_manager.check_next_column_pick(last_column)
        
        return last_column, new_game_count, recent_results, next_pick