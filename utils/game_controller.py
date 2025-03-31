# utils/game_controller.py
"""
게임 컨트롤러 - 게임 상태 감지 및 액션 결정 모듈
"""
from modules.game_detector import GameDetector
from utils.excel_manager import ExcelManager # type: ignore

class GameController:
    def __init__(self, driver, excel_path="AUTO.xlsx"):
        self.driver = driver
        self.game_detector = GameDetector()
        self.excel_manager = ExcelManager(excel_path)
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
        
        # 현재 라운드 정보 조회
        round_info = self.excel_manager.get_current_round_info()
        
        # 배팅 필요 여부와 PICK 값 저장
        need_betting = round_info["need_betting"]
        self.current_pick = round_info["pick_value"]
        
        # 결과 생성
        result = {
            'game_count': self.current_state['round'],
            'betting_available': self.current_state['betting_available'],
            'need_betting': need_betting,
            'pick': self.current_pick,
            'betting_step': self.current_betting_step,
            'consecutive_losses': self.consecutive_losses
        }
        
        # 액션 결정 (배팅 또는 대기)
        if need_betting and self.current_state['betting_available']:
            result['action'] = 'bet'
            result['target'] = 'player' if self.current_pick == 'P' else 'banker'
        else:
            result['action'] = 'wait'
            
        return result
        
    def record_game_result(self, result):
        """
        게임 결과를 기록하고 필요한 처리를 수행합니다.
        
        Args:
            result (str): 게임 결과 ('P', 'B', 'T' 중 하나)
            
        Returns:
            dict: 처리 결과 정보
        """
        if not self.current_state:
            return {'success': False, 'message': '게임 상태가 초기화되지 않았습니다.'}
            
        # 게임 결과 기록
        self.game_detector.record_pb(result)
        
        # 현재 열에 결과 기록
        current_column = self.excel_manager.get_current_column()
        if not current_column:
            return {'success': False, 'message': '기록할 엑셀 열을 찾을 수 없습니다.'}
            
        write_success = self.excel_manager.write_game_result(current_column, result)
        if not write_success:
            return {'success': False, 'message': f'{current_column}3 열에 결과 기록 실패'}
            
        # 배팅 결과 확인 (승/패)
        is_win, result_value = self.excel_manager.check_result(current_column)
        
        # 승패 후속 처리
        if is_win:
            self.consecutive_losses = 0
            self.current_betting_step = 0
        else:
            self.consecutive_losses += 1
            self.current_betting_step += 1
            
        return {
            'success': True,
            'column': current_column,
            'game_result': result,
            'betting_result': result_value,
            'is_win': is_win,
            'consecutive_losses': self.consecutive_losses,
            'betting_step': self.current_betting_step,
            'message': f'게임 결과 {result} 기록 완료, 배팅 결과: {result_value}'
        }
        
    # def should_change_room(self):
    #     """
    #     방 이동이 필요한지 확인합니다.
        
    #     Returns:
    #         bool: 방 이동 필요 여부
    #     """
    #     # 배팅에 1번 성공하면 방 이동
    #     if self.consecutive_losses == 0 and self.current_betting_step == 0:
    #         # 방금 배팅에 성공한 경우
    #         last_result = self.excel_manager.check_result(self.excel_manager.get_current_column())
    #         if last_result and last_result[0]:  # 가장 최근 결과가 승리인 경우
    #             return True
                
    #     return False

    def should_change_room(self):
        """
        방 이동이 필요한지 확인합니다.
        단순 1승으로는 이동하지 않으며, 라운드 수로만 판단하도록 변경 가능
        """
        if self.current_state and self.current_state.get('round', 0) >= 60:
            return True  # 60게임 도달 시 이동
        return False

    def reset_state(self):
        """
        상태를 초기화합니다.
        """
        self.current_state = None
        self.consecutive_losses = 0
        self.current_betting_step = 0
        self.current_pick = None