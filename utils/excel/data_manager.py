# utils/excel/data_manager.py
"""
Excel 데이터 읽기/쓰기 전용 클래스
- 셀 및 행 데이터 읽기
- 게임 결과 쓰기
- 열 관리
"""
import logging
import openpyxl
from typing import Dict, Any, Optional

class ExcelDataManager:
    """Excel 파일 데이터 관리를 위한 클래스"""
    
    def __init__(self, base_manager):
        """
        Excel 데이터 관리자 초기화
        
        Args:
            base_manager (ExcelBaseManager): 기본 Excel 관리자 객체
        """
        self.base_manager = base_manager
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
    
    def read_row(self, row_number, start_col='B', end_col='R'):
        """
        특정 행의 값을 읽어옵니다.
        
        Args:
            row_number (int): 읽어올 행 번호
            start_col (str): 시작 열 문자 (기본값: 'B')
            end_col (str): 끝 열 문자 (기본값: 'R')
        
        Returns:
            Dict[str, Any]: 열 이름을 키로 하고 셀 값을 값으로 하는 딕셔너리
        """
        # COM 인스턴스를 사용하여 읽기 시도
        if not self.base_manager.reopen_excel_if_needed():
            return {}
            
        try:
            # 수식 업데이트 먼저 실행
            self._update_formulas()
            
            # 결과를 저장할 딕셔너리 초기화
            result = {}
            
            # 열 문자를 열 인덱스로 변환
            start_col_idx = openpyxl.utils.column_index_from_string(start_col)
            end_col_idx = openpyxl.utils.column_index_from_string(end_col)
            
            sheet = self.base_manager.workbook.ActiveSheet
            
            # 지정된 행의 열별로 값 읽기
            for col_idx in range(start_col_idx, end_col_idx + 1):
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                cell_value = sheet.Cells(row_number, col_idx).Value
                result[col_letter] = cell_value
            
            return result
        except Exception as e:
            self.logger.error(f"COM 인터페이스로 행 읽기 실패: {e}")
            self.base_manager.reopen_excel_if_needed()
            return {}
    
    def read_pick_row(self):
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
    
    def read_result_row(self):
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
    
    def read_cell_value(self, column, row):
        """
        특정 셀 값 읽기
        
        Args:
            column (str): 열 문자 (예: 'B', 'C')
            row (int): 행 번호
            
        Returns:
            Any: 셀 값 또는 None (읽기 실패시)
        """
        if not self.base_manager.reopen_excel_if_needed():
            return None
            
        try:
            sheet = self.base_manager.workbook.ActiveSheet
            col_idx = openpyxl.utils.column_index_from_string(column)
            return sheet.Cells(row, col_idx).Value
        except Exception as e:
            self.logger.error(f"셀 값 읽기 실패: {e}")
            self.base_manager.reopen_excel_if_needed()
            return None
    
    def write_game_result(self, column, result):
        """
        게임 결과를 3행에 씁니다.
        
        Args:
            column (str): 열 문자 (예: 'B', 'C', 'D')
            result (str): 결과 값 ('P', 'B', 'T' 중 하나)
            
        Returns:
            bool: 성공 여부
        """
        if not self.base_manager.reopen_excel_if_needed():
            return False
            
        try:
            sheet = self.base_manager.workbook.ActiveSheet
            
            # 3행에 결과 쓰기
            col_idx = openpyxl.utils.column_index_from_string(column)
            sheet.Cells(3, col_idx).Value = result
            
            # 저장 (닫지 않고)
            self._save_without_close()
            
            # 수식 업데이트
            self._update_formulas()
            
            return True
        except Exception as e:
            self.logger.error(f"엑셀 파일에 게임 결과 쓰기 실패: {e}")
            self.base_manager.reopen_excel_if_needed()
            return False
    
    def get_next_empty_column(self, row=3, start_col='B', end_col='BW'):
        """
        지정된 행에서 값이 비어 있는 첫 번째 열을 찾습니다.
        
        Args:
            row (int): 확인할 행 번호 (기본값: 3)
            start_col (str): 시작 열 문자 (기본값: 'B')
            end_col (str): 끝 열 문자 (기본값: 'BW')
            
        Returns:
            Optional[str]: 값이 비어 있는 첫 번째 열 문자 또는 None
        """
        if not self.base_manager.reopen_excel_if_needed():
            return None
            
        try:
            sheet = self.base_manager.workbook.ActiveSheet
            
            # 열 인덱스 변환
            start_col_idx = openpyxl.utils.column_index_from_string(start_col)
            end_col_idx = openpyxl.utils.column_index_from_string(end_col)
            
            # 비어 있는 열 찾기
            for col_idx in range(start_col_idx, end_col_idx + 1):
                cell_value = sheet.Cells(row, col_idx).Value
                if cell_value is None or cell_value == "":
                    col_letter = openpyxl.utils.get_column_letter(col_idx)
                    return col_letter
            
            return None
        except Exception as e:
            self.logger.error(f"COM으로 빈 열 찾기 실패: {e}")
            self.base_manager.reopen_excel_if_needed()
            return None
    
    def get_current_column(self):
        """
        현재 작업 중인 열을 찾습니다. (3행 기준으로 비어 있는 첫 번째 열)
        
        Returns:
            Optional[str]: 현재 작업 중인 열 문자 또는 None
        """
        return self.get_next_empty_column(row=3)
    
    # 내부 메서드 - 수식 업데이트와 저장 기능은 다른 관리자에서 상세 구현
    def _update_formulas(self):
        """수식 업데이트 (내부 헬퍼 메서드)"""
        if not self.base_manager.excel_app:
            return False
        try:
            self.base_manager.workbook.Application.Calculate()
            return True
        except:
            return False
            
    def _save_without_close(self):
        """Excel 파일 저장 (내부 헬퍼 메서드)"""
        if not self.base_manager.workbook:
            return False
        try:
            self.base_manager.workbook.Save()
            return True
        except:
            return False