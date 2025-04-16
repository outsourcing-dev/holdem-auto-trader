# services/excel_trading_service.py
import logging
from typing import Dict, Any, Tuple, List, Optional, Union
from utils.choice_pick import ChoicePickSystem

class ExcelTradingService:
    def __init__(self, main_window, logger=None):
        """Excel 트레이딩 서비스 초기화"""
        self.main_window = main_window
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.choice_pick_system = ChoicePickSystem(logger=self.logger)

        # 내부 예측 엔진 사용 (Excel 없이 동작)
        from utils.prediction_engine import PredictionEngine
        self.prediction_engine = PredictionEngine(logger=self.logger)

    def process_game_results(self, game_state, game_count, current_room_name, log_on_change=False):
        """
        게임 결과를 처리하고 필요한 정보를 반환합니다.
        
        Args:
            game_state (dict): 게임 상태 정보
            game_count (int): 현재 게임 카운트
            current_room_name (str): 현재 방 이름
            log_on_change (bool): 변화가 있을 때만 로그 출력 여부
            
        Returns:
            tuple: (처리 상태, 새 게임 카운트, 최근 결과 목록, 다음 픽 값)
        """
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

    # utils/excel_trading_service.py의 _handle_first_run 메서드에서 수정할 부분
    def _handle_first_run(self, filtered_results, recent_results, actual_game_count):
        """
        첫 실행 시 처리 - 예측 엔진 사용
        """
        self.logger.info(f"첫 실행 감지: 예측 엔진에 최근 결과 {len(filtered_results)}개 추가 (TIE 제외)")

        # 예측 엔진 초기화 및 결과 추가
        self.prediction_engine.clear()
        self.prediction_engine.add_multiple_results(filtered_results)

        # 결과 로깅 강화
        self.logger.info(f"첫 실행 결과: {filtered_results}")

        # 다음 PICK 예측
        next_pick = self.prediction_engine.predict_next_pick()

        # processed_rounds 업데이트 (좀 더 명확한 게임 카운트 계산)
        start_count = max(1, actual_game_count - len(filtered_results))
        self._update_processed_rounds(filtered_results, start_count=start_count)

        return "PREDICTED", actual_game_count, recent_results, next_pick

    def _record_new_result(self, result, column, new_game_count, recent_results):
        """
        새 결과 기록 - 엑셀 대신 예측 엔진 사용
        
        Args:
            result (str): 게임 결과 ('P', 'B', 'T' 중 하나)
            column (str): 열 정보 (호환성 유지용)
            new_game_count (int): 새 게임 카운트
            recent_results (list): 최근 결과 목록
            
        Returns:
            tuple: (열 정보, 게임 카운트, 최근 결과 목록, 다음 픽 값)
        """
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
        """
        중복 결과인지 확인
        
        Args:
            latest_result (str): 최근 게임 결과
            new_game_count (int): 새 게임 카운트
            
        Returns:
            bool: 중복 여부
        """
        result_id = f"{new_game_count}_{latest_result}"
        if hasattr(self.main_window, 'trading_manager') and result_id in self.main_window.trading_manager.processed_rounds:
            # self.logger.info(f"이미 처리된 결과 감지 (ID: {result_id}) - 중복 처리 방지")
            return True
        return False
        
    def _update_processed_rounds(self, results, start_count=None):
        """
        처리된 라운드 업데이트 - 더 정확한 게임 ID 생성
        """
        if hasattr(self.main_window, 'trading_manager'):
            base_count = start_count or 1  # 항상 최소 1부터 시작
            for i, res in enumerate(results):
                result_id = f"{base_count+i}_{res}"
                self.main_window.trading_manager.processed_rounds.add(result_id)
                self.logger.debug(f"라운드 처리 기록: {result_id}")
    
    def _process_new_result(self, latest_result, new_game_count, recent_results):
        """
        새 게임 결과 처리 - 예측 엔진 사용
        
        Args:
            latest_result (str): 최근 게임 결과
            new_game_count (int): 새 게임 카운트
            recent_results (list): 최근 결과 목록
            
        Returns:
            tuple: (열 정보, 게임 카운트, 최근 결과 목록, 다음 픽 값)
        """
        # TIE 결과 처리
        if latest_result == 'T':
            return self._handle_tie_result("AUTO", new_game_count, recent_results)

        # 새 결과 기록 (P 또는 B인 경우)
        if latest_result in ['P', 'B']:
            return self._record_new_result(latest_result, "AUTO", new_game_count, recent_results)

        # 기타 예외적 결과 처리
        return None, new_game_count, recent_results, None

    def _handle_tie_result(self, current_column, new_game_count, recent_results):
        """
        TIE 결과 처리 - 예측 엔진 사용
        
        Args:
            current_column (str): 현재 열 정보 (호환성 유지용)
            new_game_count (int): 새 게임 카운트
            recent_results (list): 최근 결과 목록
            
        Returns:
            tuple: (열 정보, 게임 카운트, 최근 결과 목록, 다음 픽 값)
        """
        self.logger.info(f"TIE 결과 감지 - 예측 엔진 기반 PICK 값 사용")

        next_pick = self.prediction_engine.predict_next_pick()
        if next_pick == 'N':
            self.logger.warning("예측 엔진에서 PICK 값을 계산할 수 없음 (데이터 부족)")

        return "AUTO", new_game_count, recent_results, next_pick
        
    def record_betting_result(self, is_win: bool) -> None:
        """
        베팅 결과 기록
        
        Args:
            is_win (bool): 베팅 성공 여부
        """
        self.prediction_engine.record_betting_result(is_win)
        
    def should_change_room(self) -> bool:
        """
        방 이동 필요 여부 확인
        
        Returns:
            bool: 방 이동 필요 여부
        """
        return self.prediction_engine.should_change_room()
        
    def get_current_bet_amount(self, widget_position=None) -> int:
        """현재 마틴 단계에 따른 베팅 금액 반환"""
        # widget_position = 0
        # 위젯 위치 가져오기
        if hasattr(self.main_window, 'betting_widget') and hasattr(self.main_window.betting_widget, 'room_position_counter'):
            widget_position = self.main_window.betting_widget.room_position_counter
        
        # 위젯 위치를 전달하여 금액 계산
        return self.choice_pick_system.get_current_bet_amount(widget_position)
        
    def set_martin_amounts(self, amounts: List[int]) -> None:
        """
        마틴 금액 설정
        
        Args:
            amounts (List[int]): 마틴 단계별 금액 목록
        """
        self.prediction_engine.set_martin_amounts(amounts)
        
    def reset_after_room_change(self, preserve_martin: bool = False) -> None:
        """방 이동 후 초기화"""
        self.prediction_engine.reset_after_room_change(preserve_martin=preserve_martin)

        
    def get_reverse_bet_pick(self, original_pick):
        """
        원본 픽에 베팅 방향을 적용하여 실제 베팅할 픽 반환
        
        Args:
            original_pick (str): 원본 픽 값
            
        Returns:
            str: 베팅 방향이 적용된 실제 베팅할 픽
        """
        return self.prediction_engine.choice_pick_system.get_reverse_bet_pick(original_pick)