# services/excel_trading_service.py 리팩토링
import logging
import openpyxl
from typing import Dict, Any, Tuple, List, Optional, Union
import time

class ExcelTradingService:
    def __init__(self, main_window, logger=None):
        """Excel 트레이딩 서비스 초기화"""
        self.main_window = main_window
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        from utils.excel_manager import ExcelManager # type: ignore
        self.excel_manager = ExcelManager()

    # services/excel_trading_service.py의 process_game_results 함수 수정

    def process_game_results(self, game_state, game_count, current_room_name, log_on_change=False):
        """게임 결과를 처리하고 필요한 정보를 반환합니다."""
        if not game_state:
            return None, game_count, [], None
            
        new_game_count = game_state['round']
        latest_result = game_state.get('latest_result')
        recent_results = game_state.get('recent_results', [])
        filtered_results = game_state.get('filtered_results', [])  # TIE를 제외한 P/B 결과만
        
        # 중복 처리 방지 확인
        if latest_result:
            if self._is_duplicate_result(latest_result, new_game_count):
                return self._handle_duplicate_result(new_game_count, recent_results)
        
        # 첫 실행 여부 확인 - 수정: 첫 실행 판단 로직 개선
        is_first_run = game_count == 0 or game_count < new_game_count - 3
        
        # 첫 실행 시 처리 (방 입장 직후) - 수정: 입장 시 실제 게임 카운트 사용
        if is_first_run and filtered_results:
            # 중요 변경: 실제 게임 카운트 전달
            return self._handle_first_run(filtered_results, recent_results, new_game_count)
        
        # 새로운 결과가 있는지 확인 - 수정: 게임 카운트 증가 값 확인 로직 개선
        has_new_result = new_game_count > game_count and latest_result is not None
        
        if not has_new_result:
            if not log_on_change:
                self.logger.info("새로운 게임 결과 없음")
            return None, new_game_count, recent_results, None

        # 새로운 결과가 있을 때는 항상 로깅
        self.logger.info(f"새로운 게임 결과 감지: {latest_result}")

        # 현재 열 찾기 및 결과 처리
        return self._process_new_result(latest_result, new_game_count, recent_results)

    # _handle_first_run 함수 수정
    def _handle_first_run(self, filtered_results, recent_results, actual_game_count):
        """첫 실행 시 처리 - 실제 게임 카운트 인자 추가"""
        self.logger.info(f"첫 실행 감지: 엑셀에 최근 결과 {len(filtered_results)}개 기록 (TIE 제외)")
        
        # 전체 결과 초기화 및 기록
        success = self.excel_manager.write_filtered_game_results([], filtered_results)
        if not success:
            return None, 0, recent_results, None
            
        # 마지막 열 계산
        last_column_idx = 1 + len(filtered_results)
        last_column = openpyxl.utils.get_column_letter(last_column_idx)
        
        # 다음 열의 PICK 값 확인
        next_pick = self._get_pick_value(last_column)
        
        # 결과 처리 성공 시 processed_rounds에 추가 - 중요 변경: 실제 게임 카운트 사용
        self._update_processed_rounds(filtered_results, start_count=actual_game_count-len(filtered_results))
        
        # 중요 변경: 실제 게임 카운트 반환
        return last_column, actual_game_count, recent_results, next_pick
  
    def _is_duplicate_result(self, latest_result, new_game_count):
        """중복 결과인지 확인"""
        result_id = f"{new_game_count}_{latest_result}"
        if hasattr(self.main_window, 'trading_manager') and result_id in self.main_window.trading_manager.processed_rounds:
            self.logger.info(f"이미 처리된 결과 감지 (ID: {result_id}) - 중복 처리 방지")
            return True
        return False
        
    def _handle_duplicate_result(self, new_game_count, recent_results):
        """중복 결과 처리"""
        # 현재 열 찾기 - 이미 기록되어 있으므로 다음 열의 PICK 값만 확인
        current_column = self.excel_manager.get_current_column()
        if not current_column:
            return None, new_game_count, recent_results, None
            
        prev_column = self.excel_manager.get_prev_column_letter(current_column)
        if not prev_column:
            return None, new_game_count, recent_results, None
            
        next_pick = self._get_pick_value(prev_column)
        return prev_column, new_game_count, recent_results, next_pick
        
    def _update_processed_rounds(self, results, start_count=None):
        """처리된 라운드 업데이트"""
        if hasattr(self.main_window, 'trading_manager'):
            base_count = start_count or self.main_window.trading_manager.game_count
            for i, res in enumerate(results):
                result_id = f"{base_count-len(results)+i+1}_{res}"
                self.main_window.trading_manager.processed_rounds.add(result_id)
    
    def _process_new_result(self, latest_result, new_game_count, recent_results):
        """새 게임 결과 처리"""
        # 현재 열 찾기
        current_column = self.excel_manager.get_current_column()
        if not current_column:
            self.logger.warning("기록할 빈 열을 찾을 수 없음")
            return None, new_game_count, recent_results, None
        
        # TIE 결과는 기록하지 않음
        if latest_result == 'T':
            return self._handle_tie_result(current_column, new_game_count, recent_results)
        
        # 이미 결과가 기록되어 있는지 확인
        if self._is_column_already_filled(current_column):
            return self._handle_filled_column(current_column, new_game_count, recent_results)
        
        # 새 결과 기록 (TIE가 아닌 경우에만)
        if latest_result in ['P', 'B']:
            return self._record_new_result(latest_result, current_column, new_game_count, recent_results)
        
        return None, new_game_count, recent_results, None
    
    def _handle_tie_result(self, current_column, new_game_count, recent_results):
        """TIE 결과 처리"""
        self.logger.info(f"TIE 결과는 엑셀에 기록하지 않습니다.")
        
        # 현재 열의 이전 열(이미 데이터가 있는 열)에서 PICK 값 확인
        prev_column = self.excel_manager.get_prev_column_letter(current_column)
        if not prev_column:
            return None, new_game_count, recent_results, None
            
        next_pick = self._get_pick_value(prev_column)
        self.logger.info(f"TIE 결과 감지 후 이전 PICK 값 확인: {next_pick}")
        
        return prev_column, new_game_count, recent_results, next_pick
    
    def _is_column_already_filled(self, column):
        """해당 열에 이미 값이 있는지 확인"""
        existing_value = self.excel_manager.read_cell_value(column, 3)
        return existing_value is not None and existing_value != ""
    
    def _handle_filled_column(self, current_column, new_game_count, recent_results):
        """이미 값이 채워진 열 처리"""
        self.logger.warning(f"{current_column}3 셀에 이미 값이 존재함 - 중복 기록 방지")
        
        # 다음 열의 PICK 값만 확인
        next_pick = self._get_pick_value(current_column)
        
        return current_column, new_game_count, recent_results, next_pick
    
    def _record_new_result(self, result, column, new_game_count, recent_results):
        """새 결과 기록"""
        self.logger.info(f"{column}3에 새 결과 '{result}' 기록 중...")
        self.excel_manager.write_game_result(column, result)
        
        # 처리된 결과 추적 - ID 추가
        if hasattr(self.main_window, 'trading_manager'):
            result_id = f"{new_game_count}_{result}"
            self.main_window.trading_manager.processed_rounds.add(result_id)

        # 다음 열의 PICK 값 확인
        next_pick = self._get_pick_value(column)
        
        return column, new_game_count, recent_results, next_pick
    
    def _get_pick_value(self, column):
        """PICK 값 확인 (더 안정적으로)"""
        # Excel을 사용해 값 확인
        try:
            pick_value = self.excel_manager.check_next_column_pick(column)
            
            if pick_value in ['P', 'B']:
                self.logger.info(f"다음 열 PICK 값: {pick_value}")
                return pick_value
            
            # 직접 읽기 시도
            next_column = self.excel_manager.get_next_column_letter(column)
            if next_column:
                direct_value = self.excel_manager.read_cell_value(next_column, 12)
                if direct_value in ['P', 'B']:
                    self.logger.info(f"직접 읽은 PICK 값: {direct_value}")
                    return direct_value
        except Exception as e:
            self.logger.warning(f"PICK 값 확인 중 오류: {e}")
        
        return None