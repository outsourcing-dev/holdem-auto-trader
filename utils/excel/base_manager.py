# utils/excel/base_manager.py
"""
Excel 파일 기본 관리 클래스
- 파일 경로 관리
- Excel 애플리케이션 연결
- 암호화/복호화 처리
"""
import os
import sys
import logging
import time
import atexit
from utils.encrypt_excel import EncryptExcel, decrypt_auto_excel

# Windows에서만 사용 가능한 COM 인터페이스
try:
    import win32com.client
    import pythoncom
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False

# 암호화된 Excel 사용 여부
USE_ENCRYPTED_EXCEL = True
EXCEL_PASSWORD = "holdem2025"  # 기본 암호

class ExcelBaseManager:
    """Excel 파일의 기본적인 관리 기능을 제공하는 클래스"""
    
    def __init__(self, excel_path=None):
        """
        Excel 기본 관리자 초기화
        
        Args:
            excel_path (str): Excel 파일 경로 (None이면 자동 탐지)
        """
        # 로거 설정
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Excel 관련 속성 초기화
        self.excel_app = None
        self.workbook = None
        self.is_excel_open = False
        
        # 명시적으로 경로 지정된 경우
        if excel_path is not None:
            self.excel_path = excel_path
        else:
            # 환경 변수에서 경로 가져오기 시도
            env_path = os.environ.get("AUTO_EXCEL_PATH")
            if env_path and os.path.exists(env_path):
                self.excel_path = env_path
            else:
                # 마지막으로 AUTO.xlsx 확인
                self.excel_path = self.get_excel_path("AUTO.xlsx")
        
        # Excel 암호화 관리자
        self.encryptor = EncryptExcel()
        
        # 프로그램 종료 시 Excel 종료 보장
        atexit.register(self.close_excel)
        
        # 암호화된 Excel 파일 확인 및 복호화
        self._check_and_decrypt_excel()
        
        # 엑셀 파일이 존재하는지 확인
        if not os.path.exists(self.excel_path):
            self.logger.error(f"엑셀 파일을 찾을 수 없습니다: {self.excel_path}")
            raise FileNotFoundError(f"엑셀 파일을 찾을 수 없습니다: {self.excel_path}")
        
        # 프로그램 시작 시 Excel 열기 시도
        if HAS_WIN32COM:
            self.open_excel_once()
    
    def __del__(self):
        """애플리케이션 종료 시 자원 정리"""
        # Excel 프로세스 정리
        try:
            from utils.excel_cleanup import terminate_excel_processes
            terminate_excel_processes(save_first=True)
        except:
            pass
        
        # 임시 파일 정리
        cleanup_temp_excel()
    
    def get_excel_path(self, filename="AUTO.xlsx"):
        """
        실행 환경에 따라 Excel 파일의 적절한 경로를 반환합니다.
        
        Args:
            filename (str): 엑셀 파일명
            
        Returns:
            str: 전체 경로
        """
        # 암호화된 파일을 찾는 경우 파일명 수정
        if filename == "AUTO.xlsx.enc":
            filename = "AUTO.encrypted"  # 이름 통일
            
        if getattr(sys, 'frozen', False):
            # PyInstaller로 빌드된 실행 파일인 경우
            base_dir = os.path.dirname(sys.executable)
            excel_path = os.path.join(base_dir, filename)
        else:
            # 일반 Python 스크립트로 실행되는 경우
            excel_path = filename
        
        return excel_path
    
    def _check_and_decrypt_excel(self):
        """암호화된 Excel 파일이 있는지 확인하고 필요시 복호화"""
        if not USE_ENCRYPTED_EXCEL:
            return
            
        # 암호화된 파일 경로
        encrypted_excel_path = self.get_excel_path("AUTO.xlsx.enc")
        
        # 암호화된 파일이 있고 일반 파일이 없으면 복호화
        if os.path.exists(encrypted_excel_path) and not os.path.exists(self.excel_path):
            # 복호화 시도
            if decrypt_auto_excel(EXCEL_PASSWORD):
                pass
            else:
                self.logger.error("Excel 파일 복호화 실패")
                raise FileNotFoundError("Excel 파일을 복호화할 수 없습니다")
    
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
            return True
        except Exception as e:
            self.logger.error(f"Excel 애플리케이션 시작 실패: {e}")
            self.close_excel()
            return False
    
    def close_excel(self):
        """Excel 애플리케이션 종료"""
        try:
            if self.workbook:
                try:
                    self.workbook.Save()
                except Exception as e:
                    self.logger.warning(f"Excel 저장 중 오류: {e}")
                
                try:
                    self.workbook.Close(True)  # True: 변경 사항 저장
                except Exception as e:
                    self.logger.warning(f"Excel 닫기 중 오류: {e}")
                
                self.workbook = None
            
            if self.excel_app:
                try:
                    self.excel_app.Quit()
                except Exception as e:
                    self.logger.warning(f"Excel 종료 중 오류: {e}")
                
                self.excel_app = None
            
            # COM 스레드 해제
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            
            self.is_excel_open = False
            
            # 종료 시 자동 암호화 
            if USE_ENCRYPTED_EXCEL:
                # 종료 후 원본 파일 암호화 (기존 암호화 파일 덮어쓰기)
                encrypted_path = self.get_excel_path("AUTO.xlsx.enc")
                self.encryptor.encrypt_file(self.excel_path, encrypted_path, EXCEL_PASSWORD)
        except Exception as e:
            self.logger.warning(f"Excel 종료 중 오류: {e}")
    
    def reopen_excel_if_needed(self):
        """필요한 경우 Excel을 다시 엽니다"""
        if not self.is_excel_open or not self.excel_app or not self.workbook:
            return self.open_excel_once()
        return True