# game_detector.py (게임 상태 감지)
class GameDetector:
    def __init__(self):
        self.current_round = 0  # 현재 게임 판수
        self.pb_history = []  # P/B 기록 (T 제외)

    def detect_game_state(self, screen_data):
        """
        - screen_data에서 현재 게임 판수를 감지하는 로직
        - 배팅 가능 여부 확인 (True / False 반환)
        """
        # TODO: 화면에서 정보 추출하는 로직 구현 필요
        return {'round': self.current_round, 'betting_available': True}

    def record_pb(self, result):
        """
        - P(플레이어) 또는 B(뱅커)만 기록 (T 제외)
        """
        if result in ['P', 'B']:
            self.pb_history.append(result)