# betting_strategy.py (배팅 로직)
class BettingStrategy:
    def __init__(self, base_bet=10, excel_path="auto.xlsx"):
        self.base_bet = base_bet  # 기본 베팅 금액
        self.current_bet = base_bet
        self.loss_streak = 0  # 연패 횟수
        self.round_count = 0  # 6판 카운팅
        self.tingkim_bet = 1000  # 팅김방지 배팅 금액
        self.excel_path = excel_path  # 기존 auto.xlsx 사용

    def update_excel(self, round_number, result):
        """
        - 웹에서 가져온 승패 데이터를 3행 & 7행에 입력
        """
        if not self.excel_path:
            return
        
        df = pd.read_excel(self.excel_path, sheet_name='DATA')
        
        # 3행과 7행의 해당 라운드 칸에 결과 입력
        df.iloc[2, round_number] = result  # 3행 (엑셀 기준)
        df.iloc[6, round_number] = result  # 7행 (엑셀 기준)
        
        df.to_excel(self.excel_path, sheet_name='DATA', index=False)

    def get_excel_pick(self, round_number):
        """
        - 12행의 최종 예상 PICK 값을 가져옴
        """
        if not self.excel_path:
            return 'N'  # 기본값 (배팅 안 함)

        df = pd.read_excel(self.excel_path, sheet_name='DATA')
        pick_value = df.iloc[11, round_number]  # 12행 (엑셀 기준)
        
        return pick_value if isinstance(pick_value, str) else 'N'

    def decide_bet(self, round_number):
        """
        - 엑셀의 PICK 값을 기반으로 배팅 결정
        """
        pick = self.get_excel_pick(round_number)
        if pick == 'N':
            return "No Bet"
        elif pick == 'B':
            return f"Bet {self.current_bet} on Banker"
        elif pick == 'P':
            return f"Bet {self.current_bet} on Player"
        return "Invalid Pick Value"
