import os
import sys
import logging
import win32com.client
import pythoncom
import openpyxl
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64
import hashlib

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EncryptExcel")

class EncryptExcel:
    """Excel 파일 암호화 및 복호화 클래스"""
    
    def __init__(self):
        """초기화"""
        self.excel_app = None
    
    def get_file_path(self, filename):
        """실행 환경에 따라 파일의 적절한 경로를 반환"""
        if getattr(sys, 'frozen', False):
            # PyInstaller로 빌드된 실행 파일인 경우
            base_dir = os.path.dirname(sys.executable)
            file_path = os.path.join(base_dir, filename)
        else:
            # 일반 Python 스크립트로 실행되는 경우
            file_path = filename
        
        return file_path
    
    def set_excel_password(self, file_path, password, save_as=None):
        """
        엑셀 파일에 암호 설정 (COM 인터페이스 사용)
        
        Args:
            file_path (str): 엑셀 파일 경로
            password (str): 설정할 암호
            save_as (str, optional): 다른 이름으로 저장할 경로 (없으면 원본 덮어쓰기)
        
        Returns:
            bool: 성공 여부
        """
        try:
            # COM 스레드 초기화
            pythoncom.CoInitialize()
            
            # Excel 애플리케이션 실행
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            
            # 절대 경로로 변환
            abs_path = os.path.abspath(file_path)
            
            # 워크북 열기
            workbook = excel.Workbooks.Open(abs_path)
            
            # 저장 경로 설정
            output_path = save_as if save_as else abs_path
            
            # 암호 설정하여 저장
            workbook.SaveAs(
                output_path,
                Password=password,
                WriteResPassword=password  # 수정 암호
            )
            
            # 워크북 닫기
            workbook.Close()
            
            # Excel 종료
            excel.Quit()
            
            # 정리
            del workbook, excel
            pythoncom.CoUninitialize()
            
            logger.info(f"Excel 파일에 암호 설정 완료: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Excel 파일 암호 설정 중 오류: {e}")
            
            # 정리 시도
            try:
                if 'workbook' in locals():
                    workbook.Close(SaveChanges=False)
                if 'excel' in locals():
                    excel.Quit()
                pythoncom.CoUninitialize()
            except:
                pass
                
            return False
    
    def open_password_protected_excel(self, file_path, password):
        """
        암호로 보호된 엑셀 파일 열기 (COM 인터페이스 사용)
        
        Args:
            file_path (str): 암호화된 엑셀 파일 경로
            password (str): 암호
        
        Returns:
            tuple: (성공 여부, 워크북 객체 또는 None)
        """
        try:
            # COM 스레드 초기화
            pythoncom.CoInitialize()
            
            # Excel 애플리케이션 실행
            self.excel_app = win32com.client.Dispatch("Excel.Application")
            self.excel_app.Visible = False
            self.excel_app.DisplayAlerts = False
            
            # 절대 경로로 변환
            abs_path = os.path.abspath(file_path)
            
            # 암호와 함께 워크북 열기
            workbook = self.excel_app.Workbooks.Open(abs_path, Password=password)
            
            logger.info(f"암호화된 Excel 파일 열기 성공: {file_path}")
            return True, workbook
            
        except Exception as e:
            logger.error(f"암호화된 Excel 파일 열기 실패: {e}")
            
            # 정리 시도
            try:
                if self.excel_app:
                    self.excel_app.Quit()
                    self.excel_app = None
                pythoncom.CoUninitialize()
            except:
                pass
                
            return False, None
    
    def close_workbook(self, workbook, save_changes=True):
        """
        워크북 닫기
        
        Args:
            workbook: 워크북 객체
            save_changes (bool): 변경 사항 저장 여부
        """
        try:
            if workbook:
                workbook.Close(SaveChanges=save_changes)
            
            if self.excel_app:
                self.excel_app.Quit()
                self.excel_app = None
                
            pythoncom.CoUninitialize()
            
            logger.info("Excel 워크북 닫기 완료")
            return True
        except Exception as e:
            logger.error(f"Excel 워크북 닫기 중 오류: {e}")
            return False
    
    # 파일 내용 암호화/복호화 메서드들 (AES 사용)
    
    def _get_encryption_key(self, password, salt=None):
        """
        비밀번호에서 암호화 키 생성
        
        Args:
            password (str): 비밀번호
            salt (bytes, optional): 솔트 값
            
        Returns:
            tuple: (key, salt)
        """
        if salt is None:
            salt = get_random_bytes(16)
        
        # PBKDF2를 사용하여 키 생성 (256비트)
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, 32)
        
        return key, salt
    
    def encrypt_file(self, input_path, output_path, password):
        """
        파일을 AES로 암호화하여 저장
        
        Args:
            input_path (str): 원본 파일 경로
            output_path (str): 암호화된 파일 저장 경로
            password (str): 암호화에 사용할 비밀번호
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 파일 읽기
            with open(input_path, 'rb') as f:
                plain_data = f.read()
            
            # 비밀번호로부터 암호화 키 생성
            salt = get_random_bytes(16)
            key, _ = self._get_encryption_key(password, salt)
            
            # 랜덤 IV 생성 (초기화 벡터)
            iv = get_random_bytes(16)
            
            # AES 암호화 (CBC 모드)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            padded_data = pad(plain_data, AES.block_size)
            encrypted_data = cipher.encrypt(padded_data)
            
            # 암호화된 데이터에 솔트와 IV 추가
            data_to_save = salt + iv + encrypted_data
            
            # 암호화된 데이터 저장
            with open(output_path, 'wb') as f:
                f.write(data_to_save)
            
            logger.info(f"파일 암호화 완료: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"파일 암호화 중 오류: {e}")
            return False
    
    def decrypt_file(self, input_path, output_path, password):
        """
        암호화된 파일을 복호화하여 저장
        
        Args:
            input_path (str): 암호화된 파일 경로
            output_path (str): 복호화된 파일 저장 경로
            password (str): 복호화에 사용할 비밀번호
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 암호화된 파일 읽기
            with open(input_path, 'rb') as f:
                encrypted_data = f.read()
            
            # 솔트, IV 추출
            salt = encrypted_data[:16]
            iv = encrypted_data[16:32]
            actual_encrypted_data = encrypted_data[32:]
            
            # 비밀번호로부터 복호화 키 생성
            key, _ = self._get_encryption_key(password, salt)
            
            # AES 복호화
            cipher = AES.new(key, AES.MODE_CBC, iv)
            padded_plain_data = cipher.decrypt(actual_encrypted_data)
            
            try:
                plain_data = unpad(padded_plain_data, AES.block_size)
            except ValueError as e:
                logger.error(f"복호화 패딩 오류. 비밀번호가 올바르지 않을 수 있습니다: {e}")
                return False
            
            # 복호화된 데이터 저장
            with open(output_path, 'wb') as f:
                f.write(plain_data)
            
            logger.info(f"파일 복호화 완료: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"파일 복호화 중 오류: {e}")
            return False

def encrypt_auto_excel(password="default_password"):
    """
    AUTO.xlsx 파일 암호화 유틸리티 함수
    
    Args:
        password (str): 암호화에 사용할 비밀번호
    
    Returns:
        bool: 성공 여부
    """
    encryptor = EncryptExcel()
    
    # 파일 경로
    auto_xlsx = encryptor.get_file_path("AUTO.xlsx")
    auto_xlsx_encrypted = encryptor.get_file_path("AUTO.xlsx.enc")
    
    # 파일 존재 확인
    if not os.path.exists(auto_xlsx):
        logger.error(f"AUTO.xlsx 파일을 찾을 수 없습니다: {auto_xlsx}")
        return False
    
    # 파일 암호화
    return encryptor.encrypt_file(auto_xlsx, auto_xlsx_encrypted, password)

def decrypt_auto_excel(password="default_password"):
    """
    암호화된 AUTO.xlsx.enc 파일을 복호화하여 AUTO.xlsx로 저장
    
    Args:
        password (str): 복호화에 사용할 비밀번호
    
    Returns:
        bool: 성공 여부
    """
    encryptor = EncryptExcel()
    
    # 파일 경로
    auto_xlsx = encryptor.get_file_path("AUTO.xlsx")
    auto_xlsx_encrypted = encryptor.get_file_path("AUTO.xlsx.enc")
    
    # 암호화된 파일 존재 확인
    if not os.path.exists(auto_xlsx_encrypted):
        logger.error(f"암호화된 AUTO.xlsx.enc 파일을 찾을 수 없습니다: {auto_xlsx_encrypted}")
        return False
    
    # 파일 복호화
    return encryptor.decrypt_file(auto_xlsx_encrypted, auto_xlsx, password)

# # 명령행에서 실행 시 테스트
# if __name__ == "__main__":
#     import argparse
    
#     parser = argparse.ArgumentParser(description='Excel 파일 암호화/복호화 도구')
#     parser.add_argument('action', choices=['encrypt', 'decrypt'], help='수행할 작업')
#     parser.add_argument('--password', default="holdem2025", help='암호화/복호화에 사용할 비밀번호')
    
#     args = parser.parse_args()
    
#     if args.action == 'encrypt':
#         if encrypt_auto_excel(args.password):
#             print("AUTO.xlsx 파일이 성공적으로 암호화되었습니다.")
#         else:
#             print("AUTO.xlsx 파일 암호화 실패.")
#     else:
#         if decrypt_auto_excel(args.password):
#             print("AUTO.xlsx.enc 파일이 성공적으로 복호화되었습니다.")
#         else:
#             print("AUTO.xlsx.enc 파일 복호화 실패.")