# utils/excel/__init__.py
"""
Excel 파일 관리 모듈 패키지
기존 Excel 관리 기능을 더 작고 관리하기 쉬운 모듈로 분리
"""

from .base_manager import ExcelBaseManager
from .data_manager import ExcelDataManager
from .formula_manager import ExcelFormulaManager
from .backup_manager import ExcelBackupManager

class ExcelManager:
    """
    Excel 파일 관리 통합 클래스
    각 서브 모듈의 기능을 통합해서 제공합니다.
    """
    def __init__(self, excel_path=None):
        # 기본 관리자 초기화 - 다른 관리자들이 의존
        self.base_manager = ExcelBaseManager(excel_path)
        
        # 각 기능별 관리자 초기화 (기본 관리자 참조 전달)
        self.data_manager = ExcelDataManager(self.base_manager)
        self.formula_manager = ExcelFormulaManager(self.base_manager)
        self.backup_manager = ExcelBackupManager(self.base_manager)
        
        # 중요 속성들 직접 참조 가능하도록 연결
        self.excel_path = self.base_manager.excel_path
        
    # 기본 관리자 메서드 위임
    def get_excel_path(self, filename="AUTO.xlsx"):
        return self.base_manager.get_excel_path(filename)
        
    def open_excel_once(self):
        return self.base_manager.open_excel_once()
        
    def close_excel(self):
        return self.base_manager.close_excel()
        
    def reopen_excel_if_needed(self):
        return self.base_manager.reopen_excel_if_needed()
    
    # 데이터 관리자 메서드 위임
    def read_row(self, row_number, start_col='B', end_col='R'):
        return self.data_manager.read_row(row_number, start_col, end_col)
    
    def read_pick_row(self):
        return self.data_manager.read_pick_row()
    
    def read_result_row(self):
        return self.data_manager.read_result_row()
    
    def read_cell_value(self, column, row):
        return self.data_manager.read_cell_value(column, row)
    
    def write_game_result(self, column, result):
        return self.data_manager.write_game_result(column, result)
    
    def get_next_empty_column(self, row=3, start_col='B', end_col='BW'):
        return self.data_manager.get_next_empty_column(row, start_col, end_col)
    
    def get_current_column(self):
        return self.data_manager.get_current_column()
    
    # 수식 관리자 메서드 위임
    def update_formulas(self):
        return self.formula_manager.update_formulas()
    
    def save_without_close(self):
        return self.formula_manager.save_without_close()
    
    def check_betting_needed(self, column):
        return self.formula_manager.check_betting_needed(column)
    
    def check_result(self, column):
        return self.formula_manager.check_result(column)
    
    def check_next_column_pick(self, column):
        return self.formula_manager.check_next_column_pick(column)
    
    def get_next_column_letter(self, column):
        return self.formula_manager.get_next_column_letter(column)
    
    def get_prev_column_letter(self, column):
        return self.formula_manager.get_prev_column_letter(column)
    
    # 백업 관리자 메서드 위임
    def initialize_excel(self):
        return self.backup_manager.initialize_excel()
    
    def write_game_results_sequence(self, results):
        return self.backup_manager.write_game_results_sequence(results)
    
    def write_filtered_game_results(self, filtered_results, actual_results):
        return self.backup_manager.write_filtered_game_results(filtered_results, actual_results)