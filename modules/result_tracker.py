# result_tracker.py (게임 결과 기록)
class ResultTracker:
    def __init__(self):
        self.history = []  # 승패 기록

    def record_result(self, result):
        """
        - 결과 저장 ('win' 또는 'loss')
        """
        self.history.append(result)
        return self.history

    def check_room_change(self, room_data):
        """
        - 'M'이 찍힌 경우 방 이동
        """
        if 'M' in room_data:
            return True  # 방 이동 신호
        return False
