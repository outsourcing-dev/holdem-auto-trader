from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QMessageBox, QTableWidget, 
                             QSizePolicy,QHeaderView)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication

from ui.header_widget import HeaderWidget
from ui.betting_widget import BettingWidget
from utils.devtools import DevToolsController
from utils.settings_manager import SettingsManager
from utils.room_manager import RoomManager
from utils.trading_manager import TradingManager
from utils.ui_updater import UIUpdater
from ui.room_log_widget import RoomLogWidget

import time


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 화면 해상도 가져오기
        screen = QGuiApplication.primaryScreen()
        screen_size = screen.availableGeometry()
        
        # 가로는 고정 크기(1200), 높이는 화면에서 사용 가능한 최대 높이의 90%로 설정
        window_width = min(1200, screen_size.width() - 40)
        window_height = int(screen_size.height() * 0.9)
        
        # 창 위치 설정
        x_position = (screen_size.width() - window_width) // 2
        y_position = int(screen_size.height() * 0.05)
        
        # 창 설정
        self.setWindowTitle("홀덤 자동 배팅")
        self.move(x_position, y_position)  # 위치 설정
        
        # 최대/최소 크기를 모두 원하는 크기로 설정하여 크기 고정
        self.setMinimumSize(window_width, window_height)
        self.setMaximumSize(window_width, window_height)
        
        # 사이즈 정책 설정
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
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

    # ui/main_window.py의 setup_ui 메서드에서 수정할 부분
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
        self.layout.addLayout(self.left_panel, 2)  # 비율 2:1

        # 상단 정보바
        self.header = HeaderWidget()
        self.left_panel.addWidget(self.header)
        
        # 배팅 위젯 (현재 진행 상황 표시)
        self.betting_widget = BettingWidget()
        self.left_panel.addWidget(self.betting_widget)

        # 방 로그 위젯 (새로 추가)
        self.room_log_widget = RoomLogWidget()
        self.left_panel.addWidget(self.room_log_widget)

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

        # 자동 배팅 시작 / 종료 버튼
        start_stop_layout = QHBoxLayout()
        self.start_button = QPushButton("🔵 자동 배팅 시작")
        self.stop_button = QPushButton("🔴 자동 배팅 종료")

        # 초기에 버튼 비활성화
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)

        self.start_button.clicked.connect(self.start_trading)
        self.stop_button.clicked.connect(self.stop_trading)

        start_stop_layout.addWidget(self.start_button)
        start_stop_layout.addWidget(self.stop_button)
        self.left_panel.addLayout(start_stop_layout)

        # 오른쪽 UI (방 목록 패널) - 변경된 부분
        self.room_panel = QVBoxLayout()
        self.layout.addLayout(self.room_panel, 1)  # 비율 2:1

        # "방 목록" 제목 추가
        self.room_label = QLabel("📋 방 목록")
        self.room_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.room_panel.addWidget(self.room_label)

        # 방 목록 테이블 추가
        self.room_table = QTableWidget()
        
        # 테이블 스타일 설정
        self.room_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #DDDDDD;
                border: 1px solid #CCCCCC;
            }
            QTableWidget::item {
                background-color: white;
                padding: 4px;
                text-align: center;
            }
            QTableWidget QHeaderView::section {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #2E7D32;
                text-align: center;
            }
            QCheckBox {
                background-color: white;
            }
        """)
        
        # 테이블 헤더 설정
        self.room_table.setColumnCount(2)  # 체크박스, 방 이름
        self.room_table.setHorizontalHeaderLabels(["선택", "방 이름"])
        
        # 테이블 열 사이즈 설정
        self.room_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.room_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.room_table.setColumnWidth(0, 50)  # 체크박스 열 너비
        
        self.room_panel.addWidget(self.room_table)

        # 방 목록 관리 버튼들 (가로 배치)
        room_buttons_layout = QHBoxLayout()
        
        # 방 목록 불러오기 버튼
        self.update_room_button = QPushButton("방 목록 불러오기")
        self.update_room_button.clicked.connect(lambda: self.show_room_list(None))
        room_buttons_layout.addWidget(self.update_room_button)
        
        # 방 목록 저장하기 버튼
        self.save_room_button = QPushButton("방 목록 저장하기")
        self.save_room_button.clicked.connect(self.save_room_settings)
        room_buttons_layout.addWidget(self.save_room_button)
        
        self.room_panel.addLayout(room_buttons_layout)
        
    def reset_ui(self):
        """UI의 모든 값을 초기화 (사용자 이름 유지)"""
        # 금액 관련 값들만 초기화
        self.start_amount = 0
        self.current_amount = 0
        self.total_bet_amount = 0
        self.profit_amount = 0
        
        # HeaderWidget 초기화 - 사용자 이름은 유지
        current_username = self.header.user_value.text()  # 현재 표시된 사용자 이름 저장
        self.header.reset_values()
        if current_username != "로그인 필요":  # 의미 있는 사용자 이름이 있을 때만 복원
            self.header.user_value.setText(current_username)
        
        # BettingWidget 초기화
        self.betting_widget.clear_results()
        self.betting_widget.reset_step_markers()
        self.betting_widget.update_current_room("")
        self.betting_widget.set_pick("")
        
        # RoomLogWidget 초기화
        if hasattr(self, 'room_log_widget'):
            self.room_log_widget.clear_logs()
            
    def open_site(self, url):
        """사이트 열기"""
        # 브라우저가 실행 중인지 확인
        if not self.devtools.driver:
            self.devtools.start_browser()
            
        self.devtools.open_site(url)
        print(f"[INFO] 사이트 열기: {url}")
    
    def switch_to_casino_window(self):
        """카지노 창(2번 창)으로 전환 - 로직 강화"""
        if not self.devtools.driver:
            QMessageBox.warning(self, "알림", "브라우저가 실행되지 않았습니다. 먼저 브라우저를 실행해주세요.")
            return False
            
        window_handles = self.devtools.driver.window_handles
        
        # 창이 2개 이상인지 확인
        if len(window_handles) < 2:
            QMessageBox.warning(self, "알림", "창이 2개 이상 필요합니다. 사이트 버튼으로 카지노 페이지를 열어주세요.")
            return False
        
        # 로그에 모든 창 정보 출력 (디버깅 용도)
        print(f"[INFO] 현재 열려있는 창 개수: {len(window_handles)}")
        for i, handle in enumerate(window_handles):
            # 현재 창 핸들로 전환하여 URL 확인
            self.devtools.driver.switch_to.window(handle)
            current_url = self.devtools.driver.current_url
            print(f"[INFO] 창 #{i+1} (핸들: {handle[:8]}...) URL: {current_url}")
        
        # 카지노/에볼루션 관련 창 찾기 (URL 확인)
        casino_handle = None
        for handle in window_handles:
            try:
                self.devtools.driver.switch_to.window(handle)
                current_url = self.devtools.driver.current_url
                
                # 카지노 관련 URL인지 확인 (각 사이트마다 다를 수 있음)
                casino_related = any(keyword in current_url.lower() for keyword in 
                                    ["evo-games", "evolution", "casino", "live", "game"])
                
                if casino_related:
                    casino_handle = handle
                    print(f"[INFO] 카지노 관련 창 발견! URL: {current_url}")
                    break
            except Exception as e:
                print(f"[WARNING] 창 URL 확인 중 오류: {e}")
        
        # 카지노 창을 찾았으면 해당 창으로 전환
        if casino_handle:
            self.devtools.driver.switch_to.window(casino_handle)
            print(f"[INFO] 카지노 창으로 성공적으로 전환했습니다.")
            time.sleep(1)  # 창 전환 안정화 대기
            return True
        
        # 카지노 창을 못 찾았다면 기본적으로 두 번째 창으로 시도
        if len(window_handles) >= 2:
            print("[INFO] 카지노 창을 식별할 수 없어 기본값(두 번째 창)으로 전환합니다.")
            self.devtools.driver.switch_to.window(window_handles[1])
            time.sleep(1)  # 창 전환 안정화 대기
            current_url = self.devtools.driver.current_url
            print(f"[INFO] 전환된 창 URL: {current_url}")
            return True
        
        return False

    def switch_to_main_window(self):
        """메인 창(1번 창)으로 전환"""
        if not self.devtools.driver:
            return False
            
        window_handles = self.devtools.driver.window_handles
        if len(window_handles) < 1:
            return False
            
        print("[INFO] 메인 창으로 전환 시도...")
        self.devtools.driver.switch_to.window(window_handles[0])
        time.sleep(1)
        return True
    
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
    
    # 방 목록 불러오기 메서드 개선
    def show_room_list(self, rooms=None):
        """방 목록을 테이블에 업데이트"""
        print(f"[DEBUG-MAIN] show_room_list 호출")
        
        # 브라우저 실행 확인
        if not self.devtools.driver:
            QMessageBox.warning(self, "알림", "브라우저가 실행되지 않았습니다. 먼저 브라우저를 실행해주세요.")
            return
        
        # 카지노 창으로 전환
        if not self.switch_to_casino_window():
            QMessageBox.warning(self, "알림", "카지노 창을 찾을 수 없습니다. 먼저 카지노 페이지를 열어주세요.")
            return
        
        # 새로운 다이얼로그 기반 방식 사용
        self.room_manager.show_room_list_dialog()
        
        # 방 목록 불러오기 완료 후 카지노 창에 포커스 유지 보장
        self.switch_to_casino_window()

        
    def save_room_settings(self):
        """방 목록 설정 저장"""
        if self.room_manager.save_room_settings():
            QMessageBox.information(self, "알림", "방 목록 설정이 저장되었습니다.")
        else:
            QMessageBox.warning(self, "오류", "방 목록 설정 저장 중 오류가 발생했습니다.")