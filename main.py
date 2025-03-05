import sys
from PyQt6.QtWidgets import QApplication, QStackedWidget
from ui.login_window import LoginWindow  # 로그인 창 추가
from ui.main_window import MainWindow  # 메인 윈도우

class MainApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)

        self.stack = QStackedWidget()  # 화면 전환을 위한 QStackedWidget 사용
        self.username = ""  # 사용자 아이디 저장 변수

        # 로그인 창 추가
        self.login_window = LoginWindow(self)
        self.stack.addWidget(self.login_window)

        # 메인 창 추가
        self.main_window = MainWindow()
        self.stack.addWidget(self.main_window)

        self.stack.setCurrentWidget(self.login_window)  # 로그인 화면 먼저 실행
        self.stack.show()

    def show_main_window(self, username=None):
        """로그인 성공 시 메인 화면으로 이동하고 사용자명 설정"""
        # 사용자명 저장
        if username:
            self.username = username
            # 메인 윈도우에 사용자명 전달
            self.main_window.update_user_data(username=username)
        
        # 메인 화면으로 전환
        self.stack.setCurrentWidget(self.main_window)

if __name__ == "__main__":
    app = MainApp(sys.argv)
    sys.exit(app.exec())