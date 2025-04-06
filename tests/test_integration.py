# tests/test_integration.py
"""
초이스 픽 시스템 통합 테스트
- 예측 엔진과 초이스 픽 시스템 연동 테스트
- 게임 결과 처리 및 베팅 결정 시뮬레이션
"""
import unittest
import logging
import sys
import os

# 상위 디렉토리 경로 추가 (프로젝트 루트)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.prediction_engine import PredictionEngine
from utils.choice_pick import ChoicePickSystem

class MockMainWindow:
    """테스트용 메인 윈도우 모의 객체"""
    def __init__(self):
        self.trading_manager = None

class TestIntegrationChoicePick(unittest.TestCase):
    """초이스 픽 시스템 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        self.logger = logging.getLogger("test_integration")
        
        # 메인 윈도우 모의 객체
        self.main_window = MockMainWindow()
        
        # 예측 엔진 생성
        self.prediction_engine = PredictionEngine(self.logger)
        
        # 모드 설정
        self.prediction_engine.set_mode("choice")
    
    def test_end_to_end_workflow(self):
        """엔드 투 엔드 워크플로우 테스트"""
        # 1. 초기 상태 15판 결과 입력
        results = ['P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P']
        self.prediction_engine.add_multiple_results(results)
        
        # 2. 첫 번째 픽 생성
        pick1 = self.prediction_engine.predict_next_pick()
        self.assertIn(pick1, ['P', 'B', 'N'])
        
        if pick1 != 'N':  # 유효한 픽인 경우만 테스트
            # 3. 첫 번째 베팅 결과 처리 (실패)
            opposite_result = 'B' if pick1 == 'P' else 'P'
            self.prediction_engine.add_result(opposite_result)
            self.prediction_engine.record_betting_result(False)
            
            # 4. 마틴 단계 확인
            martin_step = self.prediction_engine.choice_pick_system.martin_step
            self.assertEqual(martin_step, 1)  # 1단계로 증가
            
            # 5. 두 번째 베팅 금액 확인
            bet_amount = self.prediction_engine.get_current_bet_amount()
            self.assertEqual(bet_amount, self.prediction_engine.choice_pick_system.martin_amounts[1])
            
            # 6. 두 번째 베팅 결과 처리 (실패)
            self.prediction_engine.add_result(opposite_result)
            self.prediction_engine.record_betting_result(False)
            
            # 7. 마틴 단계 확인
            martin_step = self.prediction_engine.choice_pick_system.martin_step
            self.assertEqual(martin_step, 2)  # 2단계로 증가
            
            # 8. 세 번째 베팅 금액 확인
            bet_amount = self.prediction_engine.get_current_bet_amount()
            self.assertEqual(bet_amount, self.prediction_engine.choice_pick_system.martin_amounts[2])
            
            # 9. 세 번째 베팅 결과 처리 (실패)
            self.prediction_engine.add_result(opposite_result)
            self.prediction_engine.record_betting_result(False)
            
            # 10. 방 이동 필요 여부 확인
            should_change = self.prediction_engine.should_change_room()
            self.assertTrue(should_change)  # 3마틴 실패로 방 이동 필요
            
            # 11. 방 이동 후 상태 초기화
            self.prediction_engine.reset_after_room_change()
            martin_step = self.prediction_engine.choice_pick_system.martin_step
            self.assertEqual(martin_step, 0)  # 마틴 단계 초기화
    
    def test_success_workflow(self):
        """성공 워크플로우 테스트"""
        # 1. 초기 상태 15판 결과 입력
        results = ['P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P']
        self.prediction_engine.add_multiple_results(results)
        
        # 2. 첫 번째 픽 생성
        pick1 = self.prediction_engine.predict_next_pick()
        
        if pick1 != 'N':  # 유효한 픽인 경우만 테스트
            # 3. 첫 번째 베팅 결과 처리 (성공)
            self.prediction_engine.add_result(pick1)  # 같은 결과 = 성공
            self.prediction_engine.record_betting_result(True)
            
            # 4. 마틴 단계 확인
            martin_step = self.prediction_engine.choice_pick_system.martin_step
            self.assertEqual(martin_step, 0)  # 성공 시 초기화 유지
            
            # 5. 마지막 승리 이후 판 수 확인
            last_win_count = self.prediction_engine.choice_pick_system.last_win_count
            self.assertEqual(last_win_count, 0)  # 승리 시 초기화
            
            # 6. 두 번째 베팅을 위한 새 픽 생성 (이미 16판)
            pick2 = self.prediction_engine.predict_next_pick()
            
            # 7. 베팅 실패 후 연속 실패 처리
            if pick2 != 'N':
                opposite_result = 'B' if pick2 == 'P' else 'P'
                self.prediction_engine.add_result(opposite_result)
                self.prediction_engine.record_betting_result(False)
                
                # 8. 마틴 단계 확인
                martin_step = self.prediction_engine.choice_pick_system.martin_step
                self.assertEqual(martin_step, 1)  # 1단계로 증가
    
    def test_game_count_increase(self):
        """게임 판 수 증가에 따른 방 이동 테스트"""
        # 1. 초기 상태 15판 결과 입력
        results = ['P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P']
        self.prediction_engine.add_multiple_results(results)
        
        # 2. 첫 번째 베팅 성공
        pick1 = self.prediction_engine.predict_next_pick()
        if pick1 != 'N':
            self.prediction_engine.add_result(pick1)
            self.prediction_engine.record_betting_result(True)
            
            # 3. 57판 추가 (마지막 승리 이후 57판)
            for i in range(57):
                result = 'P' if i % 2 == 0 else 'B'
                self.prediction_engine.add_result(result)
            
            # 4. 방 이동 필요 여부 확인
            should_change = self.prediction_engine.should_change_room()
            self.assertTrue(should_change)  # 마지막 승리 이후 57판 경과로 방 이동 필요

if __name__ == "__main__":
    unittest.main()