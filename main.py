import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from ui.login_window import LoginWindow
from ui.main_window import MainWindow
import urllib3
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 전역 변수
# temp_excel_path = None
# backup_path = None

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
        # 네트워크 풀 설정
        urllib3.PoolManager(maxsize=10)
        
        # 애플리케이션 시작
        logging.info("애플리케이션 시작")
        app = MainApp(sys.argv)
        sys.exit(app.exec())
        
    except Exception as e:
        logging.critical(f"애플리케이션 실행 중 치명적 오류: {e}", exc_info=True)

        QMessageBox.critical(None, "치명적 오류", f"프로그램 실행 중 오류가 발생했습니다: {str(e)}")
