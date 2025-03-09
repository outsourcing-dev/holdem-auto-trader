# utils/excel_manager.py
"""
엑셀 파일 관리 모듈 (최적화 버전)
- 게임 결과 저장 (3행)
- PICK 데이터 읽기 (12행)
- 결과 데이터 읽기 (16행)
- Excel COM 인스턴스 재사용으로 성능 최적화
"""
import openpyxl
import os
from typing import Dict, Any, Optional, Tuple
import time
import atexit
import logging

# 로거 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Windows에서만 사용 가능한 COM 인터페이스
try:
    import win32com.client
    import pythoncom
    HAS_WIN32COM = True
    logger.info("Excel COM 인터페이스 사용 가능")
except ImportError:
    HAS_WIN32COM = False
    logger.info("Excel COM 인터페이스 사용 불가 - win32com 라이브러리 없음")

class ExcelManager:
    def __init__(self, excel_path: str = "AUTO.xlsx"):
        """
        엑셀 파일 관리자 초기화
        
        Args:
            excel_path (str): 엑셀 파일 경로 (기본값: "AUTO.xlsx")
        """
        self.excel_path = excel_path
        self.excel_app = None
        self.workbook = None
        self.is_excel_open = False
        
        # 프로그램 종료 시 Excel 종료 보장
        atexit.register(self.close_excel)
        
        # 엑셀 파일이 존재하는지 확인
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"엑셀 파일을 찾을 수 없습니다: {excel_path}")
        
        # 프로그램 시작 시 Excel 열기 시도
        if HAS_WIN32COM:
            self.open_excel_once()
            
    def __del__(self):
        """객체 소멸 시 Excel 종료 보장"""
        self.close_excel()
    
    def open_excel_once(self):
        """Excel 애플리케이션을 한 번 열고 계속 사용"""
        if not HAS_WIN32COM:
            return False
            
        # 기존에 열려있으면 먼저 닫기
        if self.is_excel_open:
            self.close_excel()
            time.sleep(0.5)  # 잠시 대기
        
        try:
            # COM 스레드 초기화
            pythoncom.CoInitialize()
            
            # Excel 애플리케이션 실행
            self.excel_app = win32com.client.Dispatch("Excel.Application")
            self.excel_app.Visible = False
            self.excel_app.DisplayAlerts = False
            
            # 절대 경로로 변환
            abs_path = os.path.abspath(self.excel_path)
            
            # 워크북 열기
            self.workbook = self.excel_app.Workbooks.Open(abs_path)
            
            self.is_excel_open = True
            logger.info("Excel 애플리케이션 시작 및 파일 로드 완료")
            return True
        except Exception as e:
            logger.error(f"Excel 애플리케이션 시작 실패: {e}")
            self.close_excel()
            return False
        
    def close_excel(self):
        """Excel 애플리케이션 종료"""
        try:
            if self.workbook:
                try:
                    self.workbook.Save()
                    logger.info("Excel 파일 저장 완료")
                except Exception as e:
                    logger.warning(f"Excel 저장 중 오류: {e}")
                
                try:
                    self.workbook.Close(True)  # True: 변경 사항 저장
                    logger.info("Excel 워크북 닫기 완료")
                except Exception as e:
                    logger.warning(f"Excel 닫기 중 오류: {e}")
                
                self.workbook = None
            
            if self.excel_app:
                try:
                    self.excel_app.Quit()
                    logger.info("Excel 애플리케이션 종료 완료")
                except Exception as e:
                    logger.warning(f"Excel 종료 중 오류: {e}")
                
                self.excel_app = None
            
            # COM 스레드 해제
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            
            self.is_excel_open = False
        except Exception as e:
            logger.warning(f"Excel 종료 중 오류: {e}")
    
    def reopen_excel_if_needed(self):
        """필요한 경우 Excel을 다시 엽니다"""
        if not self.is_excel_open or not self.excel_app or not self.workbook:
            logger.info("Excel 재연결이 필요하여 다시 여는 중...")
            return self.open_excel_once()
        return True
        
    def update_formulas(self):
        """수식 업데이트만 수행 (저장 없이)"""
        if not self.reopen_excel_if_needed():
            return False
            
        try:
            self.workbook.Application.Calculate()
            return True
        except Exception as e:
            logger.error(f"수식 업데이트 실패: {e}")
            self.reopen_excel_if_needed()
            return False
        
    def save_without_close(self):
        """파일 저장 (닫지 않고)"""
        if not self.reopen_excel_if_needed():
            return False
            
        try:
            start_time = time.time()
            self.workbook.Save()
            elapsed = time.time() - start_time
            logger.info(f"Excel 파일 저장 완료 (소요시간: {elapsed:.2f}초)")
            return True
        except Exception as e:
            logger.error(f"파일 저장 실패: {e}")
            self.reopen_excel_if_needed()
            return False
    
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
        # COM 인스턴스를 사용하여 읽기 시도
        if not self.reopen_excel_if_needed():
            return {}
            
        try:
            # 수식 업데이트
            self.update_formulas()
            
            # 결과를 저장할 딕셔너리 초기화
            result = {}
            
            # 열 문자를 열 인덱스로 변환
            start_col_idx = openpyxl.utils.column_index_from_string(start_col)
            end_col_idx = openpyxl.utils.column_index_from_string(end_col)
            
            sheet = self.workbook.ActiveSheet
            
            # 지정된 행의 열별로 값 읽기
            for col_idx in range(start_col_idx, end_col_idx + 1):
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                cell_value = sheet.Cells(row_number, col_idx).Value
                result[col_letter] = cell_value
            
            return result
        except Exception as e:
            logger.error(f"COM 인터페이스로 행 읽기 실패: {e}")
            self.reopen_excel_if_needed()
            return {}
    
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
    
    def read_cell_value(self, column, row):
        """특정 셀 값 읽기 (COM 인터페이스 사용)"""
        if not self.reopen_excel_if_needed():
            return None
            
        try:
            sheet = self.workbook.ActiveSheet
            col_idx = openpyxl.utils.column_index_from_string(column)
            return sheet.Cells(row, col_idx).Value
        except Exception as e:
            logger.error(f"셀 값 읽기 실패: {e}")
            self.reopen_excel_if_needed()
            return None
    
    def write_game_result(self, column: str, result: str) -> bool:
        """
        게임 결과를 3행에 씁니다.
        COM 인스턴스 재사용 방식을 사용합니다.
        
        Args:
            column (str): 열 문자 (예: 'B', 'C', 'D')
            result (str): 결과 값 ('P', 'B', 'T' 중 하나)
        
        Returns:
            bool: 성공 여부
        """
        if not self.reopen_excel_if_needed():
            return False
            
        try:
            start_time = time.time()
            sheet = self.workbook.ActiveSheet
            
            # 3행에 결과 쓰기
            col_idx = openpyxl.utils.column_index_from_string(column)
            sheet.Cells(3, col_idx).Value = result
            
            # 저장 (닫지 않고)
            self.save_without_close()
            
            # 수식 업데이트
            self.update_formulas()
            
            elapsed = time.time() - start_time
            logger.info(f"{column}3에 '{result}' 기록 완료 (소요시간: {elapsed:.2f}초)")
            return True
        except Exception as e:
            logger.error(f"엑셀 파일에 게임 결과 쓰기 실패: {e}")
            self.reopen_excel_if_needed()
            return False
    
    def get_next_empty_column(self, row: int = 3, start_col: str = 'B', end_col: str = 'BW') -> Optional[str]:
        """
        지정된 행에서 값이 비어 있는 첫 번째 열을 찾습니다.
        
        Args:
            row (int): 확인할 행 번호 (기본값: 3)
            start_col (str): 시작 열 문자 (기본값: 'B')
            end_col (str): 끝 열 문자 (기본값: 'BW')
        
        Returns:
            Optional[str]: 값이 비어 있는 첫 번째 열 문자 또는 None (모든 열이 채워진 경우)
        """
        # COM 인스턴스 사용 시도
        if not self.reopen_excel_if_needed():
            return None
            
        try:
            sheet = self.workbook.ActiveSheet
            
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
            logger.error(f"COM으로 빈 열 찾기 실패: {e}")
            self.reopen_excel_if_needed()
            return None
    
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
        if not self.reopen_excel_if_needed():
            return (False, 'N')
            
        try:
            # 수식 업데이트
            self.update_formulas()
            
            # 셀 값 읽기
            pick_value = self.read_cell_value(column, 12)
            
            # 값이 None이면 'N'으로 처리
            if pick_value is None:
                pick_value = 'N'
            # 문자열이 아니면 문자열로 변환
            elif not isinstance(pick_value, str):
                pick_value = str(pick_value)
            
            # 배팅 필요 여부 결정
            need_betting = pick_value in ['B', 'P']
            return (need_betting, pick_value)
        except Exception as e:
            logger.error(f"PICK 값 확인 실패: {e}")
            self.reopen_excel_if_needed()
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
        if not self.reopen_excel_if_needed():
            return (False, 'N')
            
        try:
            # 수식 업데이트
            self.update_formulas()
            
            # 셀 값 읽기
            result_value = self.read_cell_value(column, 16)
            
            # 값이 None이면 'N'으로 처리
            if result_value is None:
                result_value = 'N'
            # 문자열이 아니면 문자열로 변환
            elif not isinstance(result_value, str):
                result_value = str(result_value)
            
            # 성공 여부 결정
            is_success = result_value == 'W'
            return (is_success, result_value)
        except Exception as e:
            logger.error(f"결과 값 확인 실패: {e}")
            self.reopen_excel_if_needed()
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
        if not self.reopen_excel_if_needed():
            return False
            
        try:
            sheet = self.workbook.ActiveSheet
            
            # 열 인덱스 변환
            start_col_idx = openpyxl.utils.column_index_from_string(start_col)
            end_col_idx = openpyxl.utils.column_index_from_string(end_col)
            
            # 범위 지정 초기화
            clear_range = sheet.Range(
                sheet.Cells(row_number, start_col_idx), 
                sheet.Cells(row_number, end_col_idx)
            )
            clear_range.ClearContents()
            
            # 저장
            self.save_without_close()
            
            logger.info(f"{row_number}행 {start_col}~{end_col} 열 초기화 완료 (COM)")
            return True
        except Exception as e:
            logger.error(f"{row_number}행 초기화 실패: {e}")
            self.reopen_excel_if_needed()
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
        
        Args:
            results (list): 게임 결과 리스트 (예: ['P', 'B', 'T', 'B', ...])
            
        Returns:
            bool: 성공 여부
        """
        if not self.reopen_excel_if_needed():
            logger.error("Excel에 연결할 수 없어 게임 결과를 기록할 수 없습니다.")
            return False
            
        try:
            # COM 인스턴스를 사용하여 기록
            sheet = self.workbook.ActiveSheet
            
            # 3행 전체를 초기화
            start_col = 2  # B열(인덱스 2)
            end_col = 75   # BW열(인덱스 75)
            
            logger.info("3행 초기화 중...")
            clear_range = sheet.Range(
                sheet.Cells(3, start_col), 
                sheet.Cells(3, end_col)
            )
            clear_range.ClearContents()
            logger.info("3행 초기화 완료")
            
            # 결과 시퀀스 기록
            for idx, result in enumerate(results):
                col_idx = 2 + idx  # B(2)부터 시작
                sheet.Cells(3, col_idx).Value = result
            
            # 저장 및 수식 업데이트
            self.workbook.Save()
            self.update_formulas()
            
            logger.info(f"총 {len(results)}개의 결과를 Excel COM으로 기록 완료")
            return True
        except Exception as e:
            logger.error(f"게임 결과 시퀀스 기록 중 오류 발생: {e}")
            # 에러 발생 시 재연결 시도
            self.reopen_excel_if_needed()
            return False
        
    def get_next_column_letter(self, column):
        """
        지정된 열의 다음 열 문자를 반환합니다.
        
        Args:
            column (str): 열 문자 (예: 'B')
            
        Returns:
            str: 다음 열 문자 (예: 'C')
        """
        try:
            col_idx = openpyxl.utils.column_index_from_string(column)
            return openpyxl.utils.get_column_letter(col_idx + 1)
        except Exception as e:
            logger.error(f"다음 열 문자 가져오기 실패: {e}")
            return None
    
    def get_prev_column_letter(self, column):
        """
        지정된 열의 이전 열 문자를 반환합니다.
        
        Args:
            column (str): 열 문자 (예: 'C')
            
        Returns:
            str: 이전 열 문자 (예: 'B') 또는 열이 'A'인 경우 None
        """
        try:
            col_idx = openpyxl.utils.column_index_from_string(column)
            if col_idx <= 1:  # 'A' 이하면 이전 열이 없음
                return None
            return openpyxl.utils.get_column_letter(col_idx - 1)
        except Exception as e:
            logger.error(f"이전 열 문자 가져오기 실패: {e}")
            return None
    
    def check_next_column_pick(self, last_result_column):
        """
        마지막으로 결과가 입력된 열의 다음 열에서 12행(PICK) 값을 확인합니다.
        
        Args:
            last_result_column (str): 마지막 결과가 입력된 열 문자 (예: 'J')
            
        Returns:
            str: 다음 열의 PICK 값 ('P', 'B', 'N' 중 하나)
        """
        if not self.reopen_excel_if_needed():
            return 'N'
            
        try:
            # 열 인덱스 계산
            col_idx = openpyxl.utils.column_index_from_string(last_result_column)
            next_col_idx = col_idx + 1
            next_col_letter = openpyxl.utils.get_column_letter(next_col_idx)
            
            # 수식 업데이트
            self.update_formulas()
            
            # 12행 값 읽기
            pick_value = self.read_cell_value(next_col_letter, 12)
            
            # 값이 None이면 'N'으로 처리
            if pick_value is None:
                pick_value = 'N'
            # 문자열이 아니면 문자열로 변환
            elif not isinstance(pick_value, str):
                pick_value = str(pick_value)
            
            start_time = time.time()
            elapsed = time.time() - start_time
            logger.info(f"다음 열 {next_col_letter}12의 PICK 값: {pick_value} (소요시간: {elapsed:.2f}초)")
            return pick_value
        except Exception as e:
            logger.error(f"다음 열 PICK 값 확인 중 오류 발생: {e}")
            self.reopen_excel_if_needed()
            return 'N'  # 오류 발생 시 기본값 'N' 반환
    
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