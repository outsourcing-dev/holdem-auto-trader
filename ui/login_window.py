from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QSizePolicy
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QSize

class LoginWindow(QDialog):
    def __init__(self, app):
        super().__init__()

        self.app = app  # MainApp 객체 가져오기

        # 창 설정
        self.setWindowTitle("로그인")
        self.setFixedSize(250, 180)  # 고정 크기 설정 (setGeometry 대신)
        self.setObjectName("LoginWindow")
        
        # 레이아웃 설정
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 글꼴 설정
        label_font = QFont("Arial", 10, QFont.Weight.Bold)
        input_font = QFont("Arial", 10)

        # 아이디 입력
        self.label = QLabel("아이디:")
        self.label.setFont(label_font)
        layout.addWidget(self.label)

        self.username_input = QLineEdit()
        self.username_input.setFont(input_font)
        self.username_input.setFixedHeight(25)
        layout.addWidget(self.username_input)

        # 비밀번호 입력
        self.label2 = QLabel("비밀번호:")
        self.label2.setFont(label_font)
        layout.addWidget(self.label2)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFont(input_font)
        self.password_input.setFixedHeight(25)
        layout.addWidget(self.password_input)

        # 로그인 버튼
        self.login_button = QPushButton("🔑 로그인")
        self.login_button.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.login_button.setFixedHeight(30)
        self.login_button.clicked.connect(self.authenticate)
        layout.addWidget(self.login_button)

        # 스타일시트 적용 (스타일에서 padding 값 조정)
        with open("ui/style.qss", "r", encoding="utf-8") as f:
            custom_style = f.read()
            # 로그인 창에만 적용될 특별 스타일 추가
            custom_style += """
            #LoginWindow QPushButton {
                padding: 3px;
            }
            #LoginWindow QLineEdit {
                padding: 3px;
            }
            """
            self.setStyleSheet(custom_style)

        # 사이즈 정책 설정
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # 레이아웃 설정
        self.setLayout(layout)
        
    def sizeHint(self):
        # 기본 크기 힌트 재정의
        return QSize(250, 180)
        
    def minimumSizeHint(self):
        # 최소 크기 힌트 재정의
        return QSize(250, 180)

    def authenticate(self):
        """로그인 검증"""
        username = self.username_input.text()
        password = self.password_input.text()

        # 입력값 검증
        if not username:
            QMessageBox.warning(self, "로그인 실패", "아이디를 입력해주세요.")
            return
            
        if not password:
            QMessageBox.warning(self, "로그인 실패", "비밀번호를 입력해주세요.")
            return

        # 테스트용 인증
        if username == "admin" and password == "1234":
            QMessageBox.information(self, "로그인 성공", "환영합니다! 😊")
            self.app.show_main_window(username=username)
        else:
            # 실제 DB 검증 대신 일단 바로 로그인 허용
            QMessageBox.information(self, "로그인 성공", f"{username}님 환영합니다! 😊")
            self.app.show_main_window(username=username)