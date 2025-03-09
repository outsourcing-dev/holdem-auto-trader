import sys
import os
import tempfile
import atexit
from PyQt6.QtWidgets import QApplication, QStackedWidget, QMessageBox
from ui.login_window import LoginWindow
from ui.main_window import MainWindow
import urllib3
import logging
from utils.encrypt_excel import EncryptExcel  # simple_decrypt_file 대신 EncryptExcel 클래스 임포트

# 전역 변수 - 임시 파일 경로
temp_excel_path = None

def cleanup_temp_excel():
    """프로그램 종료 시 임시 파일 삭제"""
    global temp_excel_path
    if temp_excel_path and os.path.exists(temp_excel_path):
        try:
            os.remove(temp_excel_path)
            logging.info(f"임시 Excel 파일 삭제 완료: {temp_excel_path}")
        except Exception as e:
            logging.error(f"임시 파일 삭제 실패: {e}")

# 프로그램 종료 시 임시 파일 정리
atexit.register(cleanup_temp_excel)

def prepare_excel_file():
    """암호화된 Excel 파일을 복호화하여 임시 파일로 준비"""
    global temp_excel_path
    
    # 현재 실행 경로
    base_path = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    
    # 기본 Excel 파일 경로 (암호화되지 않은 원본)
    original_excel_path = os.path.join(base_path, "AUTO.xlsx")
    
    # 암호화된 파일 경로
    encrypted_path = os.path.join(base_path, "AUTO.encrypted")
    
    # 1. 원본 Excel 파일이 있는지 확인 (개발 환경용)
    if os.path.exists(original_excel_path):
        logging.info(f"원본 Excel 파일 사용: {original_excel_path}")
        return original_excel_path
    
    # 2. 암호화된 파일이 있는지 확인
    if not os.path.exists(encrypted_path):
        logging.error(f"오류: 암호화된 Excel 파일을 찾을 수 없습니다: {encrypted_path}")
        return None
    
    # 3. 임시 디렉토리에 임시 파일 생성
    temp_dir = tempfile.gettempdir()
    temp_excel_path = os.path.join(temp_dir, f"AUTO_temp_{os.getpid()}.xlsx")
    
    # 4. 암호화 키
    SECRET_KEY = "holdem2025_secret_key"
    
    # 5. 복호화 - EncryptExcel 클래스 사용
    try:
        encryptor = EncryptExcel()
        if encryptor.decrypt_file(encrypted_path, temp_excel_path, SECRET_KEY):
            logging.info(f"Excel 파일 복호화 완료: {temp_excel_path}")
            return temp_excel_path
        else:
            logging.error("Excel 파일 복호화 실패")
            return None
    except Exception as e:
        logging.error(f"Excel 파일 복호화 중 오류: {e}")
        return None

# Excel 프로세스 정리 유틸리티 가져오기 (시작 전 정리용)
try:
    from utils.excel_cleanup import cleanup_excel_on_startup
    # 프로그램 시작 시 실행 중인 Excel 프로세스 정리
    cleanup_excel_on_startup()
except ImportError:
    logging.warning("Excel 정리 유틸리티를 가져올 수 없습니다.")

urllib3.PoolManager(maxsize=10)  # 기본값 1에서 10으로 증가

# 전역 변수로 메인 윈도우 인스턴스 저장
global_main_window = None

class MainApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)

        # Excel 파일 준비
        self.excel_path = prepare_excel_file()
        if not self.excel_path:
            QMessageBox.critical(None, "오류", "필요한 Excel 파일을 준비할 수 없어 프로그램을 종료합니다.")
            sys.exit(1)
        
        # 환경 변수에 Excel 파일 경로 저장 (다른 모듈에서 사용하기 위함)
        os.environ["AUTO_EXCEL_PATH"] = self.excel_path
        logging.info(f"Excel 파일 경로 설정: {self.excel_path}")

        # 로그인 창은 직접 표시하고, 메인 창은 별도로 관리
        self.username = ""  # 사용자 아이디 저장 변수
        
        # 로그인 창 생성 및 표시
        self.login_window = LoginWindow(self)
        self.login_window.show()
        
        # 메인 창은 미리 생성하지만 표시하지 않음
        self.main_window = None  # 필요할 때 생성

    def show_main_window(self, username=None):
        """로그인 성공 시 메인 화면으로 이동하고 사용자명 설정"""
        global global_main_window
        
        # 로그인 창 닫기
        self.login_window.close()
        
        # 메인 창이 아직 생성되지 않았으면 생성
        if self.main_window is None:
            self.main_window = MainWindow()
            # 전역 변수에 저장
            global_main_window = self.main_window
        
        # 사용자명 저장
        if username:
            self.username = username
            # 메인 윈도우에 사용자명 전달
            self.main_window.update_user_data(username=username)
        
        # 메인 창 표시
        self.main_window.show()

if __name__ == "__main__":
    # 기본 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    app = MainApp(sys.argv)
    sys.exit(app.exec())