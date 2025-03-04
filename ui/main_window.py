from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from ui.header_widget import HeaderWidget
from utils.devtools import DevToolsController
from utils.settings_manager import SettingsManager
from utils.parser import HTMLParser

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("홀덤 자동 매매")
        self.setGeometry(100, 100, 800, 600)
        self.setObjectName("MainWindow")  # QSS 스타일 적용을 위한 ID 지정

        # ✅ DevToolsController 객체 생성 (자동 실행 X)
        self.devtools = DevToolsController()

        # ✅ 스타일 적용
        with open("ui/style.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        # 상단 정보바
        self.header = HeaderWidget()
        layout.addWidget(self.header)

        # 사이트 이동 버튼 (한 줄 정렬)
        self.settings_manager = SettingsManager()
        site1, site2, site3 = self.settings_manager.get_sites()

        site_button_layout = QHBoxLayout()
        self.site1_button = QPushButton("사이트 1 이동")
        self.site2_button = QPushButton("사이트 2 이동")
        self.site3_button = QPushButton("사이트 3 이동")

        self.site1_button.clicked.connect(lambda: self.devtools.open_site(site1))  # ✅ devtools.py에서 실행
        self.site2_button.clicked.connect(lambda: self.devtools.open_site(site2))
        self.site3_button.clicked.connect(lambda: self.devtools.open_site(site3))

        site_button_layout.addWidget(self.site1_button)
        site_button_layout.addWidget(self.site2_button)
        site_button_layout.addWidget(self.site3_button)

        layout.addLayout(site_button_layout)

        # 시작 / 종료 버튼 (한 줄 정렬)
        start_stop_layout = QHBoxLayout()
        self.start_button = QPushButton("🔵 자동 매매 시작")
        self.stop_button = QPushButton("🔴 자동 매매 종료")

        self.start_button.clicked.connect(self.start_trading)
        self.stop_button.clicked.connect(self.stop_trading)

        start_stop_layout.addWidget(self.start_button)
        start_stop_layout.addWidget(self.stop_button)

        layout.addLayout(start_stop_layout)

        central_widget.setLayout(layout)  # 중앙 위젯에 레이아웃 설정

    def start_trading(self):
        """자동 매매 시작"""
        print("[INFO] 자동 매매 시작!")

        # 현재 페이지 HTML 가져오기
        html = self.devtools.get_page_source()
        parser = HTMLParser(html)

        # 잔액 가져오기
        balance = parser.get_balance()
        if balance is not None:
            print(f"[INFO] 현재 잔액: {balance}원")
            self.run_auto_trading(balance)
        else:
            print("[ERROR] 잔액 정보를 찾을 수 없습니다.")

    def run_auto_trading(self, balance):
        """자동 매매 로직"""
        print(f"[INFO] 자동 매매 진행 중... 잔액: {balance}원")
        # TODO: 자동 매매 알고리즘 구현

    def stop_trading(self):
        """자동 매매 종료"""
        print("[INFO] 자동 매매 종료!")
