# utils/game_controller.py
"""
게임 컨트롤러 - 게임 상태 감지 및 액션 결정 모듈
"""
from modules.game_detector import GameDetector
# from utils.excel_manager import ExcelManager  # 제거됨: ExcelManager는 더 이상 사용되지 않음

class GameController:
    def __init__(self, driver, excel_path="AUTO.xlsx"):
        self.driver = driver
        self.game_detector = GameDetector()
        # self.excel_manager = ExcelManager(excel_path)  # 제거됨: ExcelManager는 호출되지 않음
        self.current_state = None
        self.current_pick = None
        self.current_betting_step = 0  # 현재 마틴 배팅 단계
        self.consecutive_losses = 0    # 연속 패배 수

    def analyze_game_state(self):
        """
        현재 게임 상태를 분석하고 필요한 액션을 결정합니다.

        Returns:
            dict: 게임 상태 및 액션 정보
        """
        # 페이지 소스 가져오기
        html_content = self.driver.page_source

        # 게임 상태 감지
        self.current_state = self.game_detector.detect_game_state(html_content)

        # 현재 라운드 정보 조회 (삭제됨)
        # round_info = self.excel_manager.get_current_round_info()
        # need_betting = round_info["need_betting"]
        # self.current_pick = round_info["pick_value"]

        # 예시용 기본값 설정
        need_betting = False
        self.current_pick = None

        result = {
            'game_count': self.current_state['round'],
            'betting_available': self.current_state['betting_available'],
            'need_betting': need_betting,
            'pick': self.current_pick,
            'betting_step': self.current_betting_step,
            'consecutive_losses': self.consecutive_losses
        }

        if need_betting and self.current_state['betting_available']:
            result['action'] = 'bet'
            result['target'] = 'player' if self.current_pick == 'P' else 'banker'
        else:
            result['action'] = 'wait'

        return result

    def reset_state(self):
        """
        상태를 초기화합니다.
        """
        self.current_state = None
        self.consecutive_losses = 0
        self.current_betting_step = 0
        self.current_pick = None
