from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt, QTimer
from ui.header_widget import HeaderWidget
from ui.betting_widget import BettingWidget
from utils.devtools import DevToolsController
from utils.settings_manager import SettingsManager
from utils.parser import HTMLParser

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("홀덤 자동 매매")
        self.setGeometry(100, 100, 800, 600)
        self.setObjectName("MainWindow")  # QSS 스타일 적용을 위한 ID 지정

        # DevToolsController 객체 생성
        self.devtools = DevToolsController()
        self.settings_manager = SettingsManager()
        self.is_trading_active = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_remaining_time)
        self.remaining_seconds = 0  # 초기 남은 시간 (초 단위)

        # 스타일 적용
        with open("ui/style.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        # 상단 정보바
        self.header = HeaderWidget()
        layout.addWidget(self.header)
        
        # 배팅 위젯 (현재 진행 상황 표시)
        self.betting_widget = BettingWidget()
        layout.addWidget(self.betting_widget)

        # 남은 시간 표시
        remaining_time_layout = QHBoxLayout()
        self.remaining_time_label = QLabel("남은시간")
        self.remaining_time_value = QLabel("00 : 00 : 00")
        remaining_time_layout.addWidget(self.remaining_time_label)
        remaining_time_layout.addWidget(self.remaining_time_value)
        layout.addLayout(remaining_time_layout)

        # 사이트 이동 버튼 (한 줄 정렬)
        site1, site2, site3 = self.settings_manager.get_sites()

        site_button_layout = QHBoxLayout()
        self.site1_button = QPushButton("사이트 1 이동")
        self.site2_button = QPushButton("사이트 2 이동")
        self.site3_button = QPushButton("사이트 3 이동")

        self.site1_button.clicked.connect(lambda: self.open_site(site1))
        self.site2_button.clicked.connect(lambda: self.open_site(site2))
        self.site3_button.clicked.connect(lambda: self.open_site(site3))

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

    def open_site(self, url):
        """사이트 열기"""
        # 브라우저가 실행 중인지 확인
        if not self.devtools.driver:
            self.devtools.start_browser()
            
        self.devtools.open_site(url)
        print(f"[INFO] 사이트 열기: {url}")
    
    def set_remaining_time(self, hours, minutes, seconds):
        """남은 시간 설정"""
        self.remaining_seconds = hours * 3600 + minutes * 60 + seconds
        self.update_remaining_time_display()
        
        # 타이머가 작동 중이 아니면 시작
        if not self.timer.isActive():
            self.timer.start(1000)  # 1초마다 업데이트
    
    def update_remaining_time(self):
        """타이머에 의해 호출되는 남은 시간 업데이트"""
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.update_remaining_time_display()
        else:
            self.timer.stop()
    
    def update_remaining_time_display(self):
        """남은 시간 표시 업데이트"""
        hours = self.remaining_seconds // 3600
        minutes = (self.remaining_seconds % 3600) // 60
        seconds = self.remaining_seconds % 60
        
        time_str = f"{hours:02} : {minutes:02} : {seconds:02}"
        self.remaining_time_value.setText(time_str)

    def update_user_data(self, username=None, start_amount=None, current_amount=None, profit_amount=None, total_bet=None):
        """사용자 데이터 업데이트"""
        if username is not None:
            self.header.update_user_info(username)
        if start_amount is not None:
            self.header.update_start_amount(start_amount)
        if current_amount is not None:
            self.header.update_current_amount(current_amount)
        if profit_amount is not None:
            self.header.update_profit(profit_amount)
        if total_bet is not None:
            self.header.update_total_bet(total_bet)
    
    def update_betting_status(self, room_name=None, pick=None, step_markers=None):
        """배팅 상태 업데이트"""
        if room_name is not None:
            self.betting_widget.update_current_room(room_name)
        if pick is not None:
            self.betting_widget.set_pick(pick)
        if step_markers is not None:
            for step, marker in step_markers.items():
                self.betting_widget.set_step_marker(step, marker)
    
    def add_betting_result(self, no, room_name, step, result):
        """배팅 결과 추가"""
        self.betting_widget.add_raw_result(no, room_name, step, result)

    def start_trading(self):
        """자동 매매 시작"""
        if self.is_trading_active:
            print("[INFO] 이미 자동 매매가 진행 중입니다.")
            return
            
        print("[INFO] 자동 매매 시작!")
        self.is_trading_active = True
        
        # 브라우저 실행 확인
        if not self.devtools.driver:
            self.devtools.start_browser()
            
        # 현재 페이지 HTML 가져오기
        html = self.devtools.get_page_source()
        if html:
            parser = HTMLParser(html)

            # 파싱 테스트: 잔액 가져오기
            balance = parser.get_balance()
            if balance is not None:
                print(f"[INFO] 현재 잔액: {balance}원")
                self.update_user_data(current_amount=balance)
            else:
                print("[WARNING] 잔액 정보를 찾을 수 없습니다.")
            
            # 남은 시간 파싱 및 설정 (임시: 1시간)
            self.set_remaining_time(1, 0, 0)
            
            # 자동 매매 루프 시작
            self.run_auto_trading()
        else:
            print("[ERROR] 페이지 소스를 가져올 수 없습니다. 사이트에 먼저 접속하세요.")
            self.is_trading_active = False

    def run_auto_trading(self):
        """자동 매매 로직"""
        if not self.is_trading_active:
            return
            
        # TODO: 파싱 및 자동 매매 로직 구현
        print("[INFO] 자동 매매 진행 중...")
        
        # 테스트: UI 업데이트 함수 호출
        self.update_betting_status(
            room_name="스피드바카라 A",
            pick="B",
            step_markers={1: "X", 2: "X", 3: "X", 4: "O"}
        )

    def stop_trading(self):
        """자동 매매 종료"""
        self.is_trading_active = False
        self.timer.stop()
        print("[INFO] 자동 매매 종료!")
        
        # TODO: 필요한 정리 작업 수행