import sys
import os
import tempfile
import atexit
import shutil
from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.login_window import LoginWindow
from ui.main_window import MainWindow
import urllib3
import logging
from utils.encrypt_excel import EncryptExcel

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 전역 변수
temp_excel_path = None
backup_path = None

def get_default_style():
    """기본 스타일시트 반환"""
    return """
    QWidget, QMainWindow, QDialog {
        background-color: #F5F5F5;
    }
    QPushButton {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
        padding: 5px;
    }
    """

def get_style_path():
    """스타일시트 파일 경로 결정"""
    # PyInstaller로 패키징된 경우
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        # 여러 경로 후보를 확인
        paths = [
            os.path.join(base_dir, "ui", "style.qss"),
            os.path.join(base_dir, "style.qss"),
            os.path.join(base_dir, "_internal", "ui", "style.qss")
        ]
    else:
        # 개발 환경인 경우
        base_dir = os.path.dirname(os.path.abspath(__file__))
        paths = [
            os.path.join(base_dir, "ui", "style.qss"),
            os.path.join(base_dir, "style.qss"),
        ]
    
    # 존재하는 첫 번째 경로 반환
    for path in paths:
        if os.path.exists(path):
            logging.info(f"스타일시트 파일 발견: {path}")
            return path
    
    logging.warning("스타일시트 파일을 찾을 수 없습니다.")
    return None

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

def ensure_backup_exists():
    """암호화 파일의 백업이 존재하는지 확인하고 필요시 생성"""
    global backup_path
    
    # 실행 경로
    base_path = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    
    # 암호화된 파일 경로와 백업 경로
    encrypted_path = os.path.join(base_path, "AUTO.encrypted")
    backup_path = os.path.join(base_path, "AUTO.encrypted.bak")
    
    # 원본 파일이 있고 백업 파일이 없는 경우에만 백업 생성
    if os.path.exists(encrypted_path) and not os.path.exists(backup_path):
        try:
            shutil.copy2(encrypted_path, backup_path)
            logging.info(f"암호화 파일 백업 생성: {backup_path}")
        except Exception as e:
            logging.error(f"백업 생성 오류: {e}")
    
    return os.path.exists(backup_path)

def prepare_excel_file():
    """암호화된 Excel 파일을 복호화하여 임시 파일로 준비"""
    global temp_excel_path, backup_path
    
    # 백업 확인
    backup_exists = ensure_backup_exists()
    logging.info(f"백업 파일 존재 여부: {backup_exists}")
    
    # 실행 경로 및 파일 경로 설정
    base_path = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
    original_excel_path = os.path.join(base_path, "AUTO.xlsx")
    encrypted_path = os.path.join(base_path, "AUTO.encrypted")
    
    # 1. 개발 환경에서 원본 Excel 파일 사용 (존재할 경우)
    if os.path.exists(original_excel_path):
        logging.info(f"원본 Excel 파일 사용: {original_excel_path}")
        return original_excel_path
    
    # 2. 암호화된 파일 체크
    if not os.path.exists(encrypted_path):
        # 백업에서 복원 시도
        if backup_exists:
            try:
                shutil.copy2(backup_path, encrypted_path)
                logging.info(f"백업에서 암호화 파일 복원: {backup_path} -> {encrypted_path}")
            except Exception as e:
                logging.error(f"백업 복원 오류: {e}")
        else:
            logging.error(f"암호화된 Excel 파일을 찾을 수 없음: {encrypted_path}")
            return None
    
    # 3. 임시 파일 경로 설정
    temp_dir = tempfile.gettempdir()
    temp_excel_path = os.path.join(temp_dir, f"AUTO_temp_{os.getpid()}.xlsx")
    
    # 4. 복호화 시도
    SECRET_KEY = "holdem2025_secret_key"
    encryptor = EncryptExcel()
    
    # 첫 번째 복호화 시도
    try:
        decrypt_result = encryptor.decrypt_file(encrypted_path, temp_excel_path, SECRET_KEY)
        logging.info(f"복호화 결과: {decrypt_result}")
        
        if decrypt_result and os.path.exists(temp_excel_path) and os.path.getsize(temp_excel_path) > 0:
            logging.info(f"Excel 파일 복호화 성공: {temp_excel_path}")
            return temp_excel_path
        
        # 복호화 실패 시 백업에서 복원 후 재시도
        if backup_exists:
            logging.info("복호화 실패, 백업에서 복원 후 재시도")
            
            # 손상된 파일 삭제
            if os.path.exists(encrypted_path):
                os.remove(encrypted_path)
            
            # 백업에서 복원
            shutil.copy2(backup_path, encrypted_path)
            
            # 두 번째 복호화 시도
            decrypt_result = encryptor.decrypt_file(encrypted_path, temp_excel_path, SECRET_KEY)
            logging.info(f"두 번째 복호화 결과: {decrypt_result}")
            
            if decrypt_result and os.path.exists(temp_excel_path) and os.path.getsize(temp_excel_path) > 0:
                logging.info(f"백업 복원 후 복호화 성공: {temp_excel_path}")
                return temp_excel_path
        
        logging.error("모든 복호화 시도 실패")
        return None
        
    except Exception as e:
        logging.error(f"복호화 중 오류: {str(e)}", exc_info=True)
        return None

class MainApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        
        # 기본 스타일 적용
        self.setStyleSheet(get_default_style())
        
        # 스타일시트 로드
        style_path = get_style_path()
        if style_path and os.path.exists(style_path):
            try:
                with open(style_path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
            except Exception as e:
                logging.error(f"스타일시트 로딩 오류: {e}")
        
        # Excel 파일 준비 (최대 2번 시도)
        for attempt in range(1, 3):
            self.excel_path = prepare_excel_file()
            if self.excel_path:
                break
            logging.warning(f"Excel 파일 준비 {attempt}번째 시도 실패")
        
        # 실패 시 종료
        if not self.excel_path:
            QMessageBox.critical(None, "오류", "필요한 Excel 파일을 준비할 수 없어 프로그램을 종료합니다.")
            sys.exit(1)
        
        # 환경 변수에 경로 저장
        os.environ["AUTO_EXCEL_PATH"] = self.excel_path
        logging.info(f"Excel 파일 경로 설정: {self.excel_path}")
        
        # 로그인 창 표시
        self.username = ""
        self.login_window = LoginWindow(self)
        self.login_window.show()
        self.main_window = None  # 필요할 때 생성
    
    def show_main_window(self, username=None, days_left=None):
        """로그인 성공 시 메인 화면으로 이동하고 사용자명 설정"""
        try:
            # 로그인 창 닫기
            self.login_window.close()
            
            # 메인 창 생성
            if self.main_window is None:
                self.main_window = MainWindow()
            
            # 사용자명과 남은 일수 설정
            if username:
                self.username = username
                self.main_window.set_user_info(username, days_left)
            
            # 메인 창 표시
            self.main_window.show()
            
        except Exception as e:
            logging.error(f"메인 창 표시 오류: {e}", exc_info=True)
            QMessageBox.critical(None, "오류", f"메인 창을 표시할 수 없습니다: {str(e)}")

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):  # PyInstaller에서 실행될 때
        sys.stdout = None  # ✅ 콘솔 창 출력 방지
        sys.stderr = None  # ✅ 에러 메시지도 숨김

    try:
        # Excel 정리 유틸리티 로드 시도
        try:
            from utils.excel_cleanup import cleanup_excel_on_startup
            cleanup_excel_on_startup()
        except ImportError:
            logging.warning("Excel 정리 유틸리티를 가져올 수 없습니다.")
        
        # 네트워크 풀 설정
        urllib3.PoolManager(maxsize=10)
        
        # 애플리케이션 시작
        logging.info("애플리케이션 시작")
        app = MainApp(sys.argv)
        sys.exit(app.exec())
        
    except Exception as e:
        logging.critical(f"애플리케이션 실행 중 치명적 오류: {e}", exc_info=True)

        QMessageBox.critical(None, "치명적 오류", f"프로그램 실행 중 오류가 발생했습니다: {str(e)}")
