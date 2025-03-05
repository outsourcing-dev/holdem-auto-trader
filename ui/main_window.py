# 5. 수정된 main_window.py
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QMessageBox, QTableWidget, 
                             QTableWidgetItem)
from PyQt6.QtCore import Qt, QTimer
from ui.header_widget import HeaderWidget
from ui.betting_widget import BettingWidget
from utils.devtools import DevToolsController
from utils.settings_manager import SettingsManager
from utils.room_manager import RoomManager
from utils.trading_manager import TradingManager
from utils.ui_updater import UIUpdater

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("홀덤 자동 매매")
        self.setGeometry(100, 100, 1000, 600)
        self.setObjectName("MainWindow")

        # 유틸리티 클래스 초기화
        self.devtools = DevToolsController()
        self.settings_manager = SettingsManager()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_remaining_time)
        self.remaining_seconds = 0
        
        # 상태 변수 초기화
        self.start_amount = 0
        self.current_amount = 0
        self.total_bet_amount = 0
        self.profit_amount = 0
        self.username = ""

        # 스타일 적용
        with open("ui/style.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        # UI 구성
        self.setup_ui()
        
        # 매니저 클래스 초기화 (UI 구성 후에 초기화)
        self.room_manager = RoomManager(self)
        self.trading_manager = TradingManager(self)
        self.ui_updater = UIUpdater(self)

    def setup_ui(self):
        """UI 구성"""
        # 메인 위젯 및 레이아웃 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 전체 레이아웃 (왼쪽 기존 UI + 오른쪽 방 목록 패널)
        self.layout = QHBoxLayout()
        central_widget.setLayout(self.layout)

        # 왼쪽 UI (기존 UI 유지)
        self.left_panel = QVBoxLayout()
        self.layout.addLayout(self.left_panel, 3)  # 비율 3:1

        # 상단 정보바
        self.header = HeaderWidget()
        self.left_panel.addWidget(self.header)
        
        # 배팅 위젯 (현재 진행 상황 표시)
        self.betting_widget = BettingWidget()
        self.left_panel.addWidget(self.betting_widget)

        # 남은 시간 표시
        remaining_time_layout = QHBoxLayout()
        self.remaining_time_label = QLabel("남은시간")
        self.remaining_time_value = QLabel("00 : 00 : 00")
        remaining_time_layout.addWidget(self.remaining_time_label)
        remaining_time_layout.addWidget(self.remaining_time_value)
        self.left_panel.addLayout(remaining_time_layout)

        # 사이트 이동 버튼
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
        self.left_panel.addLayout(site_button_layout)

        # 자동 매매 시작 / 종료 버튼
        start_stop_layout = QHBoxLayout()
        self.start_button = QPushButton("🔵 자동 매매 시작")
        self.stop_button = QPushButton("🔴 자동 매매 종료")

        self.start_button.clicked.connect(self.start_trading)
        self.stop_button.clicked.connect(self.stop_trading)

        start_stop_layout.addWidget(self.start_button)
        start_stop_layout.addWidget(self.stop_button)
        self.left_panel.addLayout(start_stop_layout)

        # 오른쪽 UI (방 목록 패널)
        self.room_panel = QVBoxLayout()
        self.layout.addLayout(self.room_panel, 1)  # 비율 3:1

        # "방 목록" 제목 추가
        self.room_label = QLabel("📋 방 목록")
        self.room_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.room_panel.addWidget(self.room_label)

        # 방 목록 테이블 추가
        self.room_table = QTableWidget()
        self.room_table.setColumnCount(1)
        self.room_table.setHorizontalHeaderLabels(["방 이름"])
        self.room_table.setColumnWidth(0, 200)  # 컬럼 크기 조정
        self.room_panel.addWidget(self.room_table)

        # 방 목록 업데이트 버튼
        self.update_room_button = QPushButton("방 목록 불러오기")
        self.update_room_button.clicked.connect(self.load_rooms_into_table)
        self.room_panel.addWidget(self.update_room_button)

    def reset_ui(self):
        """UI의 모든 값을 초기화 (0원)"""
        self.start_amount = 0
        self.current_amount = 0
        self.total_bet_amount = 0
        self.profit_amount = 0
        self.username = ""
        
        # HeaderWidget 초기화
        self.header.reset_values()
        
        # BettingWidget 초기화
        self.betting_widget.clear_results()
        self.betting_widget.reset_step_markers()
        self.betting_widget.update_current_room("")
        self.betting_widget.set_pick("")

    def open_site(self, url):
        """사이트 열기"""
        # 브라우저가 실행 중인지 확인
        if not self.devtools.driver:
            self.devtools.start_browser()
            
        self.devtools.open_site(url)
        print(f"[INFO] 사이트 열기: {url}")
    
    # 델리게이트 함수들: 각 매니저 클래스의 메서드를 호출
    def set_remaining_time(self, hours, minutes, seconds):
        self.ui_updater.set_remaining_time(hours, minutes, seconds)
    
    def update_remaining_time(self):
        self.ui_updater.update_remaining_time()
    
    def update_user_data(self, **kwargs):
        self.ui_updater.update_user_data(**kwargs)
    
    def update_betting_status(self, **kwargs):
        self.ui_updater.update_betting_status(**kwargs)
    
    def add_betting_result(self, no, room_name, step, result):
        self.ui_updater.add_betting_result(no, room_name, step, result)
    
    def start_trading(self):
        self.trading_manager.start_trading()
    
    def stop_trading(self):
        self.trading_manager.stop_trading()
    
    def load_rooms_into_table(self, rooms=None):
        self.room_manager.load_rooms_into_table(rooms)