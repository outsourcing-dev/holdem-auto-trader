# utils/betting_manager.py
"""
배팅 관리 모듈
- 배팅 결정 및 처리
- 결과 분석
"""
from utils.excel_manager import ExcelManager
from typing import Dict, Any, Optional

class BettingManager:
    def __init__(self, excel_path="AUTO.xlsx"):
        self.excel_path = excel_path
        
        # 엑셀 관리자 초기화
        try:
            self.excel_manager = ExcelManager(excel_path)
            print(f"[INFO] 엑셀 파일 '{excel_path}' 로드 완료")
        except FileNotFoundError:
            print(f"[WARNING] 엑셀 파일 '{excel_path}'을 찾을 수 없습니다.")
            self.excel_manager = None
        
        # 배팅 상태 초기화
        self.current_room = ""
        self.current_column = None
        self.current_pick = ""
        self.win_count = 0
        self.lose_count = 0
        self.betting_history = []
    
    def set_current_room(self, room_name):
        """현재 방 이름 설정"""
        self.current_room = room_name
    
    def get_current_betting_info(self) -> Dict[str, Any]:
        """
        현재 배팅 정보 가져오기
        
        Returns:
            Dict[str, Any]: 현재 배팅 정보
        """
        if not self.excel_manager:
            return {
                "can_bet": False,
                "message": "엑셀 관리자가 초기화되지 않았습니다."
            }
        
        # 현재 라운드 정보 가져오기
        round_info = self.excel_manager.get_current_round_info()
        
        # 열이 비어 있는 경우
        if round_info["round_column"] is None:
            return {
                "can_bet": False,
                "message": "모든 열이 채워져 있습니다."
            }
        
        # 현재 열 설정
        self.current_column = round_info["round_column"]
        
        # 배팅 필요 여부 확인
        need_betting = round_info["need_betting"]
        pick_value = round_info["pick_value"]
        self.current_pick = pick_value
        
        # 배팅이 필요하지 않은 경우
        if not need_betting:
            return {
                "can_bet": False,
                "column": self.current_column,
                "pick": pick_value,
                "message": f"배팅이 필요하지 않습니다. PICK 값: {pick_value}"
            }
        
        # 배팅 대상 결정
        if pick_value == 'B':
            target = "뱅커(Banker)"
        elif pick_value == 'P':
            target = "플레이어(Player)"
        else:
            # 오류 상황 - 배팅이 필요하지만 PICK 값이 'B'나 'P'가 아닌 경우
            return {
                "can_bet": False,
                "column": self.current_column,
                "pick": pick_value,
                "message": f"잘못된 PICK 값: {pick_value}"
            }
        
        return {
            "can_bet": True,
            "column": self.current_column,
            "pick": pick_value,
            "target": target,
            "room": self.current_room,
            "message": f"{self.current_column} 열, {target}에 배팅 필요"
        }
    
    def record_game_result(self, result: str) -> Dict[str, Any]:
        """
        게임 결과 기록 및 분석
        
        Args:
            result (str): 게임 결과 ('P', 'B', 'T' 중 하나)
        
        Returns:
            Dict[str, Any]: 결과 정보
        """
        if not self.excel_manager or not self.current_column:
            return {
                "success": False,
                "message": "엑셀 관리자가 초기화되지 않았거나 현재 열 정보가 없습니다."
            }
        
        # 결과 기록
        success = self.excel_manager.write_game_result(self.current_column, result)
        if not success:
            return {
                "success": False,
                "message": f"{self.current_column}3 열에 결과 '{result}' 쓰기 실패"
            }
        
        # 결과 분석을 위해 현재 정보 저장
        current_column = self.current_column
        current_pick = self.current_pick
        
        # 다음 라운드 정보 업데이트 (현재 열 초기화)
        self.current_column = None
        self.current_pick = ""
        
        return {
            "success": True,
            "column": current_column,
            "pick": current_pick,
            "result": result,
            "message": f"{current_column}3 열에 결과 '{result}' 쓰기 성공"
        }
    
    def check_betting_result(self, column: str) -> Dict[str, Any]:
        """
        배팅 결과 확인 (16행 값 확인)
        
        Args:
            column (str): 열 문자
        
        Returns:
            Dict[str, Any]: 결과 정보
        """
        if not self.excel_manager:
            return {
                "success": False,
                "message": "엑셀 관리자가 초기화되지 않았습니다."
            }
        
        # 결과 확인
        is_success, result_value = self.excel_manager.check_result(column)
        
        # 승/패 카운트 업데이트
        if result_value == 'W':
            self.win_count += 1
        elif result_value == 'L':
            self.lose_count += 1
        
        # 히스토리에 기록
        self.betting_history.append({
            "column": column,
            "result": result_value,
            "is_success": is_success,
            "room": self.current_room
        })
        
        return {
            "column": column,
            "result_value": result_value,
            "is_success": is_success,
            "win_count": self.win_count,
            "lose_count": self.lose_count,
            "message": f"{column}16 결과: {result_value} ({'성공' if is_success else '실패'})"
        }