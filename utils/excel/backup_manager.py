# utils/excel/backup_manager.py
"""
Excel 파일 백업 및 대량 데이터 처리 클래스
- 데이터 초기화
- 게임 결과 시퀀스 기록
- 필터링된 게임 결과 처리
"""
import logging
import openpyxl
from typing import List, Optional

class ExcelBackupManager:
    """Excel 파일의 백업 및 초기화 관련 기능을 제공하는 클래스"""
    
    def __init__(self, base_manager):
        """
        Excel 백업 관리자 초기화
        
        Args:
            base_manager (ExcelBaseManager): 기본 Excel 관리자 객체
        """
        self.base_manager = base_manager
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
    
    def initialize_excel(self):
        """
        Excel 파일 초기화 - 3행(결과 행) 모두 비우기
        
        Returns:
            bool: 성공 여부
        """
        if not self.base_manager.reopen_excel_if_needed():
            return False
            
        try:
            sheet = self.base_manager.workbook.ActiveSheet
            
            # 3행 전체를 초기화
            start_col = 2  # B열(인덱스 2)
            end_col = 75   # BW열(인덱스 75)
            
            # 범위 지정 초기화
            clear_range = sheet.Range(
                sheet.Cells(3, start_col), 
                sheet.Cells(3, end_col)
            )
            clear_range.ClearContents()
            
            # 저장
            return self._save_without_close()
        except Exception as e:
            self.logger.error(f"3행 초기화 실패: {e}")
            self.base_manager.reopen_excel_if_needed()
            return False
    
    def write_game_results_sequence(self, results):
        """
        게임 결과 시퀀스를 B3부터 순서대로 엑셀에 기록합니다.
        
        Args:
            results (list): 게임 결과 리스트 (예: ['P', 'B', 'T', 'B', ...])
            
        Returns:
            bool: 성공 여부
        """
        if not self.base_manager.reopen_excel_if_needed():
            self.logger.error("Excel에 연결할 수 없어 게임 결과를 기록할 수 없습니다.")
            return False
            
        try:
            # COM 인스턴스를 사용하여 기록
            sheet = self.base_manager.workbook.ActiveSheet
            
            # 3행 전체를 초기화
            start_col = 2  # B열(인덱스 2)
            end_col = 75   # BW열(인덱스 75)
            
            # 초기화
            clear_range = sheet.Range(
                sheet.Cells(3, start_col), 
                sheet.Cells(3, end_col)
            )
            clear_range.ClearContents()
            
            # 결과 시퀀스 기록
            for idx, result in enumerate(results):
                col_idx = 2 + idx  # B(2)부터 시작
                sheet.Cells(3, col_idx).Value = result
            
            # 저장 및 수식 업데이트
            self.base_manager.workbook.Save()
            self._update_formulas()
            
            self.logger.info(f"총 {len(results)}개의 결과를 Excel COM으로 기록 완료")
            return True
        except Exception as e:
            self.logger.error(f"게임 결과 시퀀스 기록 중 오류 발생: {e}")
            # 에러 발생 시 재연결 시도
            self.base_manager.reopen_excel_if_needed()
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
        # 파라미터 유효성 검사
        if not isinstance(actual_results, list):
            self.logger.error(f"유효하지 않은 결과 리스트: {actual_results}")
            return False
            
        # actual_results를 엑셀에 기록 (가장 오래된 순서대로)
        return self.write_game_results_sequence(actual_results)
    
    # 내부 헬퍼 메서드
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
        """파일 저장 (내부 헬퍼 메서드)"""
        if not self.base_manager.workbook:
            return False
        try:
            self.base_manager.workbook.Save()
            return True
        except:
            return False