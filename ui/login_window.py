from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt6.QtGui import QFont

class LoginWindow(QDialog):  # ✅ QDialog를 상속하도록 변경
    def __init__(self, app):
        super().__init__()

        self.app = app  # MainApp 객체 가져오기

        self.setWindowTitle("로그인")
        self.setGeometry(100, 100, 320, 220)
        self.setObjectName("LoginWindow")  # ✅ 스타일 적용을 위한 ID 지정

        # ✅ 스타일 적용 (QSS 불러오기)
        with open("ui/style.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        layout = QVBoxLayout()

        # 글꼴 설정
        label_font = QFont("Arial", 12, QFont.Weight.Bold)
        input_font = QFont("Arial", 12)

        # 아이디 입력
        self.label = QLabel("아이디:")
        self.label.setFont(label_font)
        layout.addWidget(self.label)

        self.username_input = QLineEdit()
        self.username_input.setFont(input_font)
        layout.addWidget(self.username_input)

        # 비밀번호 입력
        self.label2 = QLabel("비밀번호:")
        self.label2.setFont(label_font)
        layout.addWidget(self.label2)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFont(input_font)
        layout.addWidget(self.password_input)

        # 로그인 버튼
        self.login_button = QPushButton("🔑 로그인")
        self.login_button.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.login_button.setFixedHeight(40)
        self.login_button.clicked.connect(self.authenticate)
        layout.addWidget(self.login_button)

        self.setLayout(layout)

    def authenticate(self):
        """로그인 검증"""
        username = self.username_input.text()
        password = self.password_input.text()

        # TODO: DB 연동하여 검증 (현재는 테스트용 코드)
        if username == "admin" and password == "1234":
            QMessageBox.information(self, "로그인 성공", "환영합니다! 😊")
            self.app.show_main_window()  # 메인 화면으로 이동
        else:
            QMessageBox.warning(self, "로그인 실패", "아이디 또는 비밀번호가 잘못되었습니다.")
