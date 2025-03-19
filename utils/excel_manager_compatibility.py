# utils/excel_manager_compatibility.py
"""
기존 utils/excel_manager.py의 호환성을 위한 어댑터 모듈
- 기존 코드 변경 없이 새 구조의 모듈을 사용할 수 있도록 함
- 기존 호출자는 이 모듈을 excel_manager.py 대신 import하면 됨
"""

from utils.excel import ExcelManager

# 필요한 경우 기존 상수 정의 추가
USE_ENCRYPTED_EXCEL = True
EXCEL_PASSWORD = "holdem2025"  # 기본 암호

# 기존 코드가 클래스를 그대로 import하는 형태로 사용한다면 이렇게 유지
# ExcelManager = ExcelManager  # 새 ExcelManager 클래스를 기존 이름으로 노출

# 기존 코드가 함수나 상수를 직접 import하는 형태로 사용한다면 필요한 것들을 여기서 정의
# example: from utils.excel_manager import get_encrypted_excel_path

def get_encrypted_excel_path():
    """기존 호환성 함수: 암호화된 엑셀 파일 경로 반환"""
    mgr = ExcelManager()
    return mgr.get_excel_path("AUTO.xlsx.enc")

def decrypt_auto_excel(password=EXCEL_PASSWORD):
    """기존 호환성 함수: AUTO.xlsx 파일 복호화"""
    from utils.encrypt_excel import decrypt_auto_excel
    return decrypt_auto_excel(password)