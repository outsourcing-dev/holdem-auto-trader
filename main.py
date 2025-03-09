import sys
from PyQt6.QtWidgets import QApplication, QStackedWidget
from ui.login_window import LoginWindow
from ui.main_window import MainWindow
import urllib3
import logging

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