# services/excel_trading_service.py 리팩토링
import logging
# import openpyxl
from typing import Dict, Any, Tuple, List, Optional, Union
import time
from utils.prediction_engine import PredictionEngine

class ExcelTradingService:
    def __init__(self, main_window, logger=None):
        """Excel 트레이딩 서비스 초기화"""
        self.main_window = main_window
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        from utils.excel_manager import ExcelManager # type: ignore
        # self.excel_manager = ExcelManager()
        self.prediction_engine = PredictionEngine(logger=self.logger)

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
        if self._is_duplicate_result(latest_result, new_game_count):
            # 중복 결과인 경우에도 예측은 시도한다
            next_pick = self.prediction_engine.predict_next_pick()
            return "DUPLICATE", new_game_count, recent_results, next_pick
        
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

    def _handle_first_run(self, filtered_results, recent_results, actual_game_count):
        """첫 실행 시 처리 - 예측 엔진 사용"""
        self.logger.info(f"첫 실행 감지: 예측 엔진에 최근 결과 {len(filtered_results)}개 추가 (TIE 제외)")

        # 예측 엔진 초기화 및 결과 추가
        self.prediction_engine.clear()
        self.prediction_engine.add_multiple_results(filtered_results)

        # 다음 PICK 예측
        next_pick = self.prediction_engine.predict_next_pick()

        # processed_rounds 업데이트
        self._update_processed_rounds(filtered_results, start_count=actual_game_count - len(filtered_results))

        # 열 정보는 더 이상 의미 없으므로 None 반환
        return "PREDICTED", actual_game_count, recent_results, next_pick

    def _record_new_result(self, result, column, new_game_count, recent_results):
        """새 결과 기록 - 엑셀 대신 예측 엔진 사용"""
        self.logger.info(f"새 결과 '{result}' 예측 엔진에 추가")
        
        # 예측 엔진에 새 결과 추가
        self.prediction_engine.add_result(result)
        
        # 처리된 결과 추적 - ID 추가
        if hasattr(self.main_window, 'trading_manager'):
            result_id = f"{new_game_count}_{result}"
            self.main_window.trading_manager.processed_rounds.add(result_id)

        # 다음 PICK 값 예측
        next_pick = self.prediction_engine.predict_next_pick()
        
        # 이전 버전과의 호환성을 위해 열 정보 유지
        return column, new_game_count, recent_results, next_pick
  
    def _is_duplicate_result(self, latest_result, new_game_count):
        """중복 결과인지 확인"""
        result_id = f"{new_game_count}_{latest_result}"
        if hasattr(self.main_window, 'trading_manager') and result_id in self.main_window.trading_manager.processed_rounds:
            # self.logger.info(f"이미 처리된 결과 감지 (ID: {result_id}) - 중복 처리 방지")
            return True
        return False
        
    def _update_processed_rounds(self, results, start_count=None):
        """처리된 라운드 업데이트"""
        if hasattr(self.main_window, 'trading_manager'):
            base_count = start_count or self.main_window.trading_manager.game_count
            for i, res in enumerate(results):
                result_id = f"{base_count-len(results)+i+1}_{res}"
                self.main_window.trading_manager.processed_rounds.add(result_id)
    
    def _process_new_result(self, latest_result, new_game_count, recent_results):
        """새 게임 결과 처리 - 엑셀 제거 이후 리팩토링 버전"""

        # TIE 결과는 기록하지 않음
        if latest_result == 'T':
            return self._handle_tie_result("AUTO", new_game_count, recent_results)

        # 새 결과 기록 (TIE가 아닌 경우에만)
        if latest_result in ['P', 'B']:
            return self._record_new_result(latest_result, "AUTO", new_game_count, recent_results)

        # 기타 예외적 결과 처리
        return None, new_game_count, recent_results, None


    def _handle_tie_result(self, current_column, new_game_count, recent_results):
        """TIE 결과 처리 - 예측 엔진 사용"""
        self.logger.info(f"TIE 결과 감지 - 예측 엔진 기반 PICK 값 사용")

        next_pick = self.prediction_engine.predict_next_pick()
        if next_pick == 'N':
            self.logger.warning("예측 엔진에서 PICK 값을 계산할 수 없음 (데이터 부족)")

        return "AUTO", new_game_count, recent_results, next_pick