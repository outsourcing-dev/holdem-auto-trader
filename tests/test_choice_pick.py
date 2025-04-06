# tests/test_choice_pick.py
"""
초이스 픽 시스템 테스트
- 15판 기준 픽 생성 테스트
- 5단계 로직 검증
- 정배팅/역배팅 조건 검증
"""
import unittest
import logging
import sys
import os

# 상위 디렉토리 경로 추가 (프로젝트 루트)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.choice_pick import ChoicePickSystem

class TestChoicePickSystem(unittest.TestCase):
    """초이스 픽 시스템 테스트 케이스"""
    
    def setUp(self):
        """테스트 설정"""
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        self.logger = logging.getLogger("test_choice_pick")
        
        # 초이스 픽 시스템 생성
        self.choice_system = ChoicePickSystem(self.logger)
    
    def test_initial_state(self):
        """초기 상태 테스트"""
        self.assertEqual(len(self.choice_system.results), 0)
        self.assertIsNone(self.choice_system.current_pick)
        self.assertEqual(self.choice_system.betting_direction, "normal")
        self.assertEqual(self.choice_system.consecutive_failures, 0)
    
    def test_add_result(self):
        """결과 추가 테스트"""
        # 결과 추가
        self.choice_system.add_result('P')
        self.choice_system.add_result('B')
        self.choice_system.add_result('T')  # 무시되어야 함
        
        # 검증
        self.assertEqual(len(self.choice_system.results), 2)
        self.assertEqual(self.choice_system.results, ['P', 'B'])
    
    def test_add_multiple_results(self):
        """다중 결과 추가 테스트"""
        # 결과 추가
        results = ['P', 'B', 'T', 'P', 'B', 'P']
        self.choice_system.add_multiple_results(results)
        
        # 검증
        self.assertEqual(len(self.choice_system.results), 5)  # T 제외
        self.assertEqual(self.choice_system.results, ['P', 'B', 'P', 'B', 'P'])
    
    def test_stage1_pick(self):
        """1단계 픽 계산 테스트"""
        # 테스트 케이스 1: 1,2번이 같고 4번이 P
        test_results = ['P', 'P', 'B', 'P', 'B']
        self.choice_system.add_multiple_results(test_results)
        stage1_pick = self.choice_system._calculate_stage1_pick()
        self.assertEqual(stage1_pick, 'P')  # 1,2번이 같으면 4번과 동일
        
        # 테스트 케이스 2: 1,2번이 다르고 4번이 P
        self.choice_system.clear()
        test_results = ['P', 'B', 'B', 'P', 'B']
        self.choice_system.add_multiple_results(test_results)
        stage1_pick = self.choice_system._calculate_stage1_pick()
        self.assertEqual(stage1_pick, 'B')  # 1,2번이 다르면 4번의 반대
    
    def test_stage2_pick(self):
        """2단계 픽 계산 테스트"""
        # 테스트 케이스: 1단계 픽이 'P', 4개 중 2승 이상
        stage1_pick = 'P'
        test_results = ['P', 'B', 'P', 'P', 'B']  # 1단계 픽 기준 3승 1패
        self.choice_system.add_multiple_results(test_results)
        stage2_pick = self.choice_system._calculate_stage2_pick(stage1_pick)
        self.assertEqual(stage2_pick, 'P')  # 1단계 픽과 동일
        
        # 테스트 케이스: 1단계 픽이 'P', 4개 중 1승 이하
        self.choice_system.clear()
        stage1_pick = 'P'
        test_results = ['B', 'B', 'B', 'P', 'B']  # 1단계 픽 기준 1승 3패
        self.choice_system.add_multiple_results(test_results)
        stage2_pick = self.choice_system._calculate_stage2_pick(stage1_pick)
        self.assertEqual(stage2_pick, 'B')  # 1단계 픽의 반대
    
    def test_stage3_pick(self):
        """3단계 픽 계산 테스트"""
        # 테스트 케이스: 8,9번에서 전환 조건 충족
        stage2_pick = 'P'
        test_results = ['P', 'B', 'P', 'P', 'B', 'P', 'P', 'B', 'B', 'P']
        # 인덱스:        0   1   2   3   4   5   6   7   8   9
        # 8번째(인덱스 7)가 2단계 픽(P)과 다르고, 9번째(인덱스 8)가 반대 픽(B)인 경우
        self.choice_system.add_multiple_results(test_results)
        stage3_pick = self.choice_system._calculate_stage3_pick(stage2_pick)
        self.assertEqual(stage3_pick, 'B')  # 전환됨
        
        # 테스트 케이스: 전환 조건 미충족
        self.choice_system.clear()
        stage2_pick = 'P'
        test_results = ['P', 'B', 'P', 'P', 'B', 'P', 'P', 'P', 'B', 'P']
        # 인덱스:        0   1   2   3   4   5   6   7   8   9
        # 8번째(인덱스 7)가 2단계 픽(P)과 같아서 전환 조건 미충족
        self.choice_system.add_multiple_results(test_results)
        stage3_pick = self.choice_system._calculate_stage3_pick(stage2_pick)
        self.assertEqual(stage3_pick, 'P')  # 유지됨
    
    def test_choice_pick_generation(self):
        """초이스 픽 생성 종합 테스트"""
        # 15판의 테스트 데이터
        test_results = ['P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P']
        self.choice_system.add_multiple_results(test_results)
        
        # 초이스 픽 생성
        pick = self.choice_system.generate_choice_pick()
        
        # 기본 확인
        self.assertIsNotNone(pick)
        self.assertIn(pick, ['P', 'B'])
        
        # 방향 확인
# 방향 확인
        self.assertIn(self.choice_system.betting_direction, ["normal", "reverse"])
        
        # 스테이지별 픽 확인
        for stage in range(1, 6):
            self.assertIn(self.choice_system.stage_picks[stage], ['P', 'B'])
    
    def test_normal_betting_candidates(self):
        """정배팅 후보 검증 테스트"""
        # 정배팅 조건을 만족하는 데이터
        # 1. 3연패 이상 없음
        # 2. 마지막 결과가 패
        test_results = ['P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'B']
        # 위 데이터에서 'P' 픽 기준: 연패는 최대 1, 마지막은 패(B)
        self.choice_system.add_multiple_results(test_results)
        
        # 스테이지 픽 설정 (테스트용)
        self.choice_system.stage_picks = {
            1: 'P',
            2: 'B',
            3: 'P',
            4: 'B',
            5: 'P'
        }
        
        # 정배팅 후보 찾기
        candidates = self.choice_system._find_normal_betting_candidates()
        
        # P 픽이 후보에 포함되어 있어야 함 (마지막 결과가 B이므로)
        self.assertIn('P', candidates)
        
        # 점수 계산 확인
        # P 픽 기준: 7승 8패, 점수 = 7 - 8 = -1
        if 'P' in candidates:
            self.assertEqual(candidates['P'], -1)
    
    def test_reverse_betting_candidates(self):
        """역배팅 후보 검증 테스트"""
        # 역배팅 조건을 만족하는 데이터
        # 1. 3연승 이상 없음
        # 2. 마지막 결과가 승
        test_results = ['P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P', 'B', 'P']
        # 위 데이터에서 'B' 픽 기준: 연승은 최대 1, 마지막 결과가 승(P vs B의 반대)
        self.choice_system.add_multiple_results(test_results)
        
        # 스테이지 픽 설정 (테스트용)
        self.choice_system.stage_picks = {
            1: 'B',
            2: 'P',
            3: 'B',
            4: 'P',
            5: 'B'
        }
        
        # 역배팅 후보 찾기
        candidates = self.choice_system._find_reverse_betting_candidates()
        
        # 'P' 픽이 후보에 포함되어 있어야 함 ('B'의 반대)
        self.assertIn('P', candidates)
        
        # 점수 계산 확인
        # 'B' 기준으로 마지막 결과는 승리(P), 전체 7승 8패, 점수 = 8 - 7 = 1
        if 'P' in candidates:
            self.assertEqual(candidates['P'], 1)
    
    def test_final_pick_selection(self):
        """최종 초이스 픽 선택 테스트"""
        # 정배팅 후보
        normal_candidates = {
            'P': -1,
            'B': -3
        }
        
        # 역배팅 후보
        reverse_candidates = {
            'P': 1,
            'B': 2
        }
        
        # 최종 픽 선택
        pick, direction, score = self.choice_system._select_final_pick(normal_candidates, reverse_candidates)
        
        # 가장 높은 점수의 픽이 선택되어야 함 (B, reverse, 2)
        self.assertEqual(pick, 'B')
        self.assertEqual(direction, 'reverse')
        self.assertEqual(score, 2)
        
        # 동일 점수 테스트
        normal_candidates = {'P': 2}
        reverse_candidates = {'B': 2}
        
        # 동일 점수면 None 반환 (패스)
        pick, direction, score = self.choice_system._select_final_pick(normal_candidates, reverse_candidates)
        self.assertIsNone(pick)
        self.assertEqual(direction, "")
        self.assertEqual(score, 0)
    
    def test_betting_result_record(self):
        """베팅 결과 기록 테스트"""
        # 초기화
        self.choice_system.martin_step = 0
        self.choice_system.consecutive_failures = 0
        self.choice_system.last_win_count = 10
        
        # 성공 케이스
        self.choice_system.record_betting_result(True)
        self.assertEqual(self.choice_system.martin_step, 0)  # 초기화 유지
        self.assertEqual(self.choice_system.consecutive_failures, 0)  # 초기화 유지
        self.assertEqual(self.choice_system.last_win_count, 0)  # 승리 시 리셋
        
        # 실패 케이스 (마틴 1단계)
        self.choice_system.record_betting_result(False)
        self.assertEqual(self.choice_system.martin_step, 1)  # 증가
        self.assertEqual(self.choice_system.consecutive_failures, 0)  # 유지
        
        # 실패 케이스 (마틴 2단계)
        self.choice_system.record_betting_result(False)
        self.assertEqual(self.choice_system.martin_step, 2)  # 증가
        
        # 실패 케이스 (마틴 3단계 -> 초기화, 연속 실패 증가)
        self.choice_system.record_betting_result(False)
        self.assertEqual(self.choice_system.martin_step, 0)  # 초기화
        self.assertEqual(self.choice_system.consecutive_failures, 1)  # 증가
    
    def test_should_change_room(self):
        """방 이동 필요 여부 테스트"""
        # 초기 상태
        self.assertFalse(self.choice_system.should_change_room())
        
        # 3마틴 실패 케이스
        self.choice_system.consecutive_failures = 1
        self.choice_system.martin_step = 0
        self.assertTrue(self.choice_system.should_change_room())
        
        # 초이스 픽 2회 연속 실패 케이스
        self.choice_system.consecutive_failures = 0
        self.choice_system.pick_results = [False, False]
        self.assertTrue(self.choice_system.should_change_room())
        
        # 마지막 승리 이후 57판 이상 케이스
        self.choice_system.pick_results = [True]  # 초기화
        self.choice_system.last_win_count = 57
        self.assertTrue(self.choice_system.should_change_room())
        
    def test_martin_amounts(self):
        """마틴 금액 설정 테스트"""
        # 기본 마틴 금액
        default_amounts = self.choice_system.martin_amounts
        self.assertEqual(len(default_amounts), 3)  # 3단계
        
        # 마틴 금액 변경
        new_amounts = [2000, 4000, 8000]
        self.choice_system.set_martin_amounts(new_amounts)
        self.assertEqual(self.choice_system.martin_amounts, new_amounts)
        
        # 현재 베팅 금액 확인
        self.choice_system.martin_step = 0
        self.assertEqual(self.choice_system.get_current_bet_amount(), 2000)
        
        self.choice_system.martin_step = 1
        self.assertEqual(self.choice_system.get_current_bet_amount(), 4000)
        
        self.choice_system.martin_step = 2
        self.assertEqual(self.choice_system.get_current_bet_amount(), 8000)
        
        # 범위 초과 시 마지막 금액 반환
        self.choice_system.martin_step = 3
        self.assertEqual(self.choice_system.get_current_bet_amount(), 8000)

if __name__ == "__main__":
    unittest.main()