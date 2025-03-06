# utils/excel_manager.py
"""
엑셀 파일 관리 모듈
- 게임 결과 저장 (3행)
- PICK 데이터 읽기 (12행)
- 결과 데이터 읽기 (16행)
"""
import openpyxl
import os
from typing import Dict, Any, Optional, Tuple

class ExcelManager:
    def __init__(self, excel_path: str = "AUTO.xlsx"):
        """
        엑셀 파일 관리자 초기화
        
        Args:
            excel_path (str): 엑셀 파일 경로 (기본값: "AUTO.xlsx")
        """
        self.excel_path = excel_path
        
        # 엑셀 파일이 존재하는지 확인
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"엑셀 파일을 찾을 수 없습니다: {excel_path}")
    
    def read_row(self, row_number: int, start_col: str = 'B', end_col: str = 'R') -> Dict[str, Any]:
        """
        특정 행의 값을 읽어옵니다.
        
        Args:
            row_number (int): 읽어올 행 번호
            start_col (str): 시작 열 문자 (기본값: 'B')
            end_col (str): 끝 열 문자 (기본값: 'R')
        
        Returns:
            Dict[str, Any]: 열 이름을 키로 하고 셀 값을 값으로 하는 딕셔너리
        """
        # 엑셀 워크북 로드 (data_only=True로 설정하여 수식 대신 값을 읽어옴)
        workbook = openpyxl.load_workbook(self.excel_path, data_only=True)
        
        # 활성화된 시트 (또는 첫 번째 시트) 선택
        sheet = workbook.active
        
        # 열 문자를 열 인덱스로 변환 (A=1, B=2, ...)
        start_col_idx = openpyxl.utils.column_index_from_string(start_col)
        end_col_idx = openpyxl.utils.column_index_from_string(end_col)
        
        # 결과를 저장할 딕셔너리 초기화
        result = {}
        
        # 지정된 행의 시작 열부터 끝 열까지 값을 읽어옴
        for col_idx in range(start_col_idx, end_col_idx + 1):
            col_letter = openpyxl.utils.get_column_letter(col_idx)
            cell_value = sheet[f"{col_letter}{row_number}"].value
            result[col_letter] = cell_value
        
        # 워크북 닫기
        workbook.close()
        
        return result
    
    def read_pick_row(self) -> Dict[str, str]:
        """
        12행(PICK 행)의 값을 읽어옵니다.
        
        Returns:
            Dict[str, str]: 열 이름을 키로 하고 셀 값을 값으로 하는 딕셔너리
        """
        row_data = self.read_row(12)
        
        # 문자열로 변환
        for col, value in row_data.items():
            if value is None:
                row_data[col] = "N"  # None은 'N'으로 처리
            elif not isinstance(value, str):
                row_data[col] = str(value)
        
        return row_data
    
    def read_result_row(self) -> Dict[str, str]:
        """
        16행(결과 행)의 값을 읽어옵니다.
        
        Returns:
            Dict[str, str]: 열 이름을 키로 하고 셀 값(W/L/N)을 값으로 하는 딕셔너리
        """
        row_data = self.read_row(16)
        
        # 문자열로 변환
        for col, value in row_data.items():
            if value is None:
                row_data[col] = "N"  # None은 'N'으로 처리
            elif not isinstance(value, str):
                row_data[col] = str(value)
        
        return row_data
    
    def write_game_result(self, column: str, result: str) -> bool:
        """
        게임 결과를 3행에 씁니다.
        
        Args:
            column (str): 열 문자 (예: 'B', 'C', 'D')
            result (str): 결과 값 ('P', 'B', 'T' 중 하나)
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 엑셀 워크북 로드
            workbook = openpyxl.load_workbook(self.excel_path)
            
            # 활성화된 시트 (또는 첫 번째 시트) 선택
            sheet = workbook.active
            
            # 3행에 결과 쓰기
            sheet[f"{column}3"] = result
            
            # 변경 사항 저장
            workbook.save(self.excel_path)
            workbook.close()
            
            return True
        
        except Exception as e:
            print(f"엑셀 파일에 게임 결과 쓰기 실패: {str(e)}")
            return False
    
    def get_next_empty_column(self, row: int = 3, start_col: str = 'B', end_col: str = 'R') -> Optional[str]:
        """
        지정된 행에서 값이 비어 있는 첫 번째 열을 찾습니다.
        
        Args:
            row (int): 확인할 행 번호 (기본값: 3)
            start_col (str): 시작 열 문자 (기본값: 'B')
            end_col (str): 끝 열 문자 (기본값: 'R')
        
        Returns:
            Optional[str]: 값이 비어 있는 첫 번째 열 문자 또는 None (모든 열이 채워진 경우)
        """
        # 엑셀 워크북 로드
        workbook = openpyxl.load_workbook(self.excel_path, data_only=True)
        
        # 활성화된 시트 (또는 첫 번째 시트) 선택
        sheet = workbook.active
        
        # 열 문자를 열 인덱스로 변환
        start_col_idx = openpyxl.utils.column_index_from_string(start_col)
        end_col_idx = openpyxl.utils.column_index_from_string(end_col)
        
        # 비어 있는 열 찾기
        for col_idx in range(start_col_idx, end_col_idx + 1):
            col_letter = openpyxl.utils.get_column_letter(col_idx)
            cell_value = sheet[f"{col_letter}{row}"].value
            
            if cell_value is None or cell_value == "":
                workbook.close()
                return col_letter
        
        workbook.close()
        return None  # 모든 열이 채워진 경우
    
    def get_current_column(self) -> Optional[str]:
        """
        현재 작업 중인 열을 찾습니다. (3행 기준으로 비어 있는 첫 번째 열)
        
        Returns:
            Optional[str]: 현재 작업 중인 열 문자 또는 None
        """
        return self.get_next_empty_column(row=3)
    
    def check_betting_needed(self, column: str) -> Tuple[bool, str]:
        """
        지정된 열의 12행 값을 확인하여 배팅이 필요한지 결정합니다.
        
        Args:
            column (str): 열 문자 (예: 'B', 'C', 'D')
        
        Returns:
            Tuple[bool, str]: (배팅 필요 여부, PICK 값)
            - 배팅 필요 여부: PICK 값이 'B' 또는 'P'일 때 True, 그 외에는 False
            - PICK 값: 'B'(뱅커), 'P'(플레이어), 'N'(배팅 안 함) 또는 다른 값
        """
        try:
            # 엑셀 워크북 로드
            workbook = openpyxl.load_workbook(self.excel_path, data_only=True)
            
            # 활성화된 시트 (또는 첫 번째 시트) 선택
            sheet = workbook.active
            
            # 12행의 PICK 값 읽기
            pick_value = sheet[f"{column}12"].value
            
            # 값이 None이면 'N'(배팅 안 함)으로 처리
            if pick_value is None:
                pick_value = 'N'
            # 값이 문자열이 아니면 문자열로 변환
            elif not isinstance(pick_value, str):
                pick_value = str(pick_value)
            
            workbook.close()
            
            # 배팅 필요 여부 결정 ('B' 또는 'P'일 때만 배팅)
            need_betting = pick_value in ['B', 'P']
            
            return (need_betting, pick_value)
        
        except Exception as e:
            print(f"PICK 값 확인 실패: {str(e)}")
            return (False, 'N')  # 오류 발생 시 배팅 안 함
    
    def check_result(self, column: str) -> Tuple[bool, str]:
        """
        지정된 열의 16행 값을 확인하여 승패 결과를 확인합니다.
        
        Args:
            column (str): 열 문자 (예: 'B', 'C', 'D')
        
        Returns:
            Tuple[bool, str]: (성공 여부, 결과 값)
            - 성공 여부: 결과 값이 'W'일 때 True, 그 외에는 False
            - 결과 값: 'W'(승리), 'L'(패배), 'N'(미배팅) 또는 다른 값
        """
        try:
            # 엑셀 워크북 로드
            workbook = openpyxl.load_workbook(self.excel_path, data_only=True)
            
            # 활성화된 시트 (또는 첫 번째 시트) 선택
            sheet = workbook.active
            
            # 16행의 결과 값 읽기
            result_value = sheet[f"{column}16"].value
            
            # 값이 None이면 'N'(미배팅)으로 처리
            if result_value is None:
                result_value = 'N'
            # 값이 문자열이 아니면 문자열로 변환
            elif not isinstance(result_value, str):
                result_value = str(result_value)
            
            workbook.close()
            
            # 성공 여부 결정 ('W'일 때만 성공)
            is_success = result_value == 'W'
            
            return (is_success, result_value)
        
        except Exception as e:
            print(f"결과 값 확인 실패: {str(e)}")
            return (False, 'N')  # 오류 발생 시 미배팅으로 처리
    
    def get_current_round_info(self) -> Dict[str, Any]:
        """
        현재 라운드 정보를 반환합니다.
        - 다음에 결과를 입력할 열
        - 다음 라운드에 배팅해야 하는지 여부
        - PICK 값
        
        Returns:
            Dict[str, Any]: 현재 라운드 정보
        """
        # 현재 열 찾기
        current_column = self.get_current_column()
        
        if current_column is None:
            return {
                "round_column": None,
                "need_betting": False,
                "pick_value": 'N',
                "message": "모든 열이 채워져 있습니다."
            }
        
        # 배팅 필요 여부 확인
        need_betting, pick_value = self.check_betting_needed(current_column)
        
        return {
            "round_column": current_column,
            "need_betting": need_betting,
            "pick_value": pick_value,
            "message": f"{current_column} 열, PICK 값: {pick_value}"
        }
    def clear_row(self, row_number: int, start_col: str = 'B', end_col: str = 'BW') -> bool:
        """
        지정된 행의 값을 모두 지웁니다.
        
        Args:
            row_number (int): 지울 행 번호
            start_col (str): 시작 열 문자 (기본값: 'B')
            end_col (str): 끝 열 문자 (기본값: 'BW')
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 엑셀 워크북 로드
            workbook = openpyxl.load_workbook(self.excel_path)
            
            # 활성화된 시트 (또는 첫 번째 시트) 선택
            sheet = workbook.active
            
            # 열 문자를 열 인덱스로 변환
            start_col_idx = openpyxl.utils.column_index_from_string(start_col)
            end_col_idx = openpyxl.utils.column_index_from_string(end_col)
            
            # 지정된 행의 셀 값 모두 지우기
            for col_idx in range(start_col_idx, end_col_idx + 1):
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                sheet[f"{col_letter}{row_number}"] = None
            
            # 변경 사항 저장
            workbook.save(self.excel_path)
            workbook.close()
            
            print(f"[INFO] {row_number}행 {start_col}~{end_col} 열 초기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] {row_number}행 초기화 실패: {str(e)}")
            return False

    def initialize_excel(self) -> bool:
        """
        엑셀 파일 초기화
        - 3행(결과 행) 초기화
        
        Returns:
            bool: 성공 여부
        """
        # 3행 초기화
        return self.clear_row(3, 'B', 'BW')
    
    def write_game_results_sequence(self, results):
        """
        게임 결과 시퀀스를 B3부터 순서대로 엑셀에 기록합니다.
        가장 오래된 결과부터 최신 결과 순으로 입력합니다.
        먼저 3행 전체를 초기화합니다.
        
        Args:
            results (list): 게임 결과 리스트 (예: ['P', 'B', 'T', 'B', ...])
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 먼저 3행 전체를 초기화 (B열부터 BW열까지)
            self.clear_row(3, 'B', 'BW')
            
            # 엑셀 워크북 로드
            workbook = openpyxl.load_workbook(self.excel_path)
            
            # 활성화된 시트 선택
            sheet = workbook.active
            
            # 결과 시퀀스 기록 (B3부터 시작)
            for idx, result in enumerate(results):
                col_letter = openpyxl.utils.get_column_letter(2 + idx)  # B(2)부터 시작
                sheet[f"{col_letter}3"] = result
                print(f"[INFO] {col_letter}3에 '{result}' 기록")
            
            # 변경 사항 저장
            workbook.save(self.excel_path)
            workbook.close()
            
            print(f"[INFO] 총 {len(results)}개의 결과를 엑셀에 기록했습니다.")
            return True
            
        except Exception as e:
            print(f"[ERROR] 게임 결과 시퀀스 기록 중 오류 발생: {str(e)}")
            return False

    def write_filtered_game_results(self, filtered_results, actual_results):
        """
        TIE를 포함한 실제 사용 결과를 엑셀에 기록합니다.
        
        Args:
            filtered_results (list): TIE를 제외한 결과 리스트 (P, B만 포함)
            actual_results (list): TIE를 포함한 실제 사용 결과 리스트
            
        Returns:
            bool: 성공 여부
        """
        # actual_results를 엑셀에 기록 (가장 오래된 순서대로)
        return self.write_game_results_sequence(actual_results)