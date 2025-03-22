from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QMessageBox, QTableWidget, 
                             QTableWidgetItem, QSizePolicy, QHeaderView)
from PyQt6.QtCore import Qt, QTimer, QDateTime
from PyQt6.QtGui import QGuiApplication, QIcon

from ui.header_widget import HeaderWidget
from ui.betting_widget import BettingWidget
from utils.devtools import DevToolsController
from utils.settings_manager import SettingsManager
from utils.room_manager import RoomManager
from utils.trading_manager import TradingManager
from utils.ui_updater import UIUpdater
from ui.room_log_widget import RoomLogWidget
from datetime import datetime, timedelta

import time
import os
import sys

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
        self.setWindowTitle("JD Soft")
        self.move(x_position, y_position)  # 위치 설정
        
        # 최대/최소 크기를 모두 원하는 크기로 설정하여 크기 고정
        self.setMinimumSize(window_width, window_height)
        self.setMaximumSize(window_width, window_height)
        
        # 사이즈 정책 설정
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        self.setObjectName("MainWindow")
        
        # 아이콘 설정 코드
        try:
            # _internal 폴더에서 먼저 찾기
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
                icon_paths = [
                    os.path.join(base_dir, "_internal", "lover-icon.ico"),
                    os.path.join(base_dir, "lover-icon.ico")  # 백업 경로
                ]
                
                icon_path = None
                for path in icon_paths:
                    if os.path.exists(path):
                        icon_path = path
                        break
            else:
                icon_path = "lover-icon.ico"
            
            if icon_path and os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                print(f"MainWindow 아이콘 설정 완료: {icon_path}")
            else:
                print(f"MainWindow 아이콘 파일을 찾을 수 없음")
        except Exception as e:
            print(f"MainWindow 아이콘 설정 오류: {e}")

        # 유틸리티 클래스 초기화
        self.devtools = DevToolsController()
        self.settings_manager = SettingsManager()
        
        # 사용자 남은 시간(초) 변수 추가
        self.user_remaining_seconds = 0
        self.user_time_active = False
        
        # 사용자 라이센스 타이머 생성
        self.license_timer = QTimer()
        self.license_timer.timeout.connect(self.update_license_time)
        
        # 상태 변수 초기화
        self.start_amount = 0
        self.current_amount = 0
        self.total_bet_amount = 0
        self.profit_amount = 0
        self.username = ""

        # 스타일 적용
        self.apply_stylesheet()

        # UI 구성
        self.setup_ui()
        
        # 매니저 클래스 초기화 (UI 구성 후에 초기화)
        self.room_manager = RoomManager(self)
        self.trading_manager = TradingManager(self)
        self.ui_updater = UIUpdater(self)
        
    def apply_stylesheet(self):
        """스타일시트를 적용합니다."""
        try:
            style_path = self.get_style_path()
            if os.path.exists(style_path):
                with open(style_path, "r", encoding="utf-8") as f:
                    custom_style = f.read()
                    self.setStyleSheet(custom_style)
                    print(f"스타일시트 파일을 성공적으로 읽었습니다: {style_path}")
            else:
                print(f"스타일시트 파일을 찾을 수 없습니다: {style_path}")
                print(f"현재 작업 디렉토리: {os.getcwd()}")
                # 기본 스타일 적용 (간단한 스타일)
                self.setStyleSheet("""
                    QMainWindow {
                        background-color: #F5F5F5;
                    }
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        border-radius: 6px;
                        padding: 5px;
                    }
                    QTableWidget {
                        background-color: white;
                        border: 1px solid #CCCCCC;
                    }
                """)
        except Exception as e:
            print(f"스타일시트 적용 중 오류 발생: {e}")
    
    def get_style_path(self):
        """스타일시트 경로를 가져옵니다."""
        # PyInstaller 번들인지 확인
        if getattr(sys, 'frozen', False):
            # 실행 파일 기준 경로
            base_dir = os.path.dirname(sys.executable)
            paths = [
                os.path.join(base_dir, "ui", "style.qss"),       # 기존 경로
                os.path.join(base_dir, "style.qss"),            # 루트 경로
                os.path.join(base_dir, "_internal", "ui", "style.qss")  # _internal 내부 경로
            ]
            
            # 존재하는 첫 번째 경로 반환
            for path in paths:
                if os.path.exists(path):
                    print(f"[DEBUG] frozen 환경, 스타일 경로 발견: {path}")
                    return path
                    
            style_path = os.path.join(base_dir, "ui", "style.qss")
            print(f"[DEBUG] frozen 환경, 기본 스타일 경로: {style_path}")
            return style_path
        else:
            # 현재 파일의 디렉터리 기준 경로
            current_dir = os.path.dirname(os.path.abspath(__file__))
            style_path = os.path.join(current_dir, "style.qss")
            print(f"[DEBUG] 개발 환경, 스타일 경로: {style_path}")
            return style_path
        
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
        
        # ✅ 남은 라이센스 시간 표시 추가 (중앙 정렬)
        from PyQt6.QtWidgets import QSpacerItem, QSizePolicy

        # ✅ 남은 라이센스 시간 표시 추가 (왼쪽 정렬 + 패딩 추가)
        license_time_layout = QHBoxLayout()
        license_time_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # ✅ 왼쪽 패딩을 위한 SpacerItem 추가
        left_spacer = QSpacerItem(20, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        license_time_layout.addItem(left_spacer)  # 패딩 효과

        # 라벨 텍스트 변경: "사용 가능 기간:" 으로 수정
        self.license_time_label = QLabel("사용 가능 기간:")
        self.license_time_label.setStyleSheet("font-weight: bold; color: #333333;")
        self.license_time_value = QLabel("00 : 00 : 00")
        self.license_time_value.setStyleSheet("font-weight: bold; color: #FF5722;")

        # ✅ 레이아웃에 위젯 추가
        license_time_layout.addWidget(self.license_time_label)
        license_time_layout.addWidget(self.license_time_value)

        # ✅ 패딩이 추가된 `license_time_layout`을 `left_panel`에 추가
        self.left_panel.addLayout(license_time_layout)


        # 배팅 위젯 (현재 진행 상황 표시)
        self.betting_widget = BettingWidget()
        self.betting_widget.setMaximumHeight(230)  # 최대 높이를 100픽셀로 제한
        self.left_panel.addWidget(self.betting_widget)

        # 방 로그 위젯 (새로 추가)
        self.room_log_widget = RoomLogWidget()
        self.left_panel.addWidget(self.room_log_widget)
        

        # 사이트 이동 버튼
        site1, site2, site3 = self.settings_manager.get_sites()
        site_button_layout = QHBoxLayout()
        self.site1_button = QPushButton("사이트 1")
        self.site2_button = QPushButton("사이트 2")
        self.site3_button = QPushButton("사이트 3")

        # 사이트 버튼 클릭 이벤트 연결 - 람다 함수로 변경하여 최신 설정 가져오기
        self.site1_button.clicked.connect(lambda: self.open_site_with_refresh(1))
        self.site2_button.clicked.connect(lambda: self.open_site_with_refresh(2))
        self.site3_button.clicked.connect(lambda: self.open_site_with_refresh(3))

        site_button_layout.addWidget(self.site1_button)
        site_button_layout.addWidget(self.site2_button)
        site_button_layout.addWidget(self.site3_button)
        self.left_panel.addLayout(site_button_layout)

        # 자동 배팅 시작 / 종료 버튼
        start_stop_layout = QHBoxLayout()
        self.start_button = QPushButton("🔵 시작")
        self.stop_button = QPushButton("🔴 종료")

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
        
        # 베팅 위젯 초기화는 제거 - 필요한 경우에만 직접 호출하도록 변경
        # self.betting_widget.clear_results()
        # self.betting_widget.reset_step_markers()
        # self.betting_widget.update_current_room("")
        # self.betting_widget.set_pick("")
        
        # RoomLogWidget 초기화
        if hasattr(self, 'room_log_widget'):
            self.room_log_widget.clear_logs()
            
    def open_site(self, url):
        """
        사이트 열기 - 브라우저 오류 처리 기능 추가
        
        Args:
            url (str): 열 사이트 URL
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 브라우저 상태 확인
            browser_active = self.check_browser_active()
            
            # 브라우저가 실행 중이 아니면 시작
            if not browser_active:
                self.devtools.start_browser()
                
            # URL에 http:// 또는 https:// 프리픽스가 없으면 추가
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
                
            # 사이트 열기
            self.devtools.driver.get(url)
            print(f"[INFO] 사이트 열기 성공: {url}")
            
            # 로딩 대기
            time.sleep(2)  # 페이지 로딩 대기
            return True
            
        except Exception as e:
            print(f"[ERROR] 사이트 열기 실패: {e}")
            QMessageBox.warning(self, "오류", f"사이트를 열지 못했습니다.")
            return False
                
           
           
    def switch_to_casino_window(self):
        """가장 최근에 열린 카지노 창으로 전환"""
        if not self.devtools.driver:
            QMessageBox.warning(self, "알림", "브라우저가 실행되지 않았습니다. 먼저 브라우저를 실행해주세요.")
            return False
            
        # 현재 열린 모든 창의 핸들 가져오기
        window_handles = self.devtools.driver.window_handles
        
        # 창이 2개 이상인지 확인
        if len(window_handles) < 2:
            QMessageBox.warning(self, "알림", "창이 2개 이상 필요합니다. 사이트 버튼으로 카지노 페이지를 열어주세요.")
            return False
        
        # 로그에 모든 창 정보 출력 (디버깅 용도)
        print(f"[INFO] 현재 열려있는 창 개수: {len(window_handles)}")
        
        # 1. 가장 최근에 열린 창으로 전환 (마지막 인덱스의 창)
        # window_handles는 열린 순서대로 리스트에 추가되므로 마지막 요소가 가장 최근 창
        latest_window = window_handles[-1]
        self.devtools.driver.switch_to.window(latest_window)
        
        current_url = self.devtools.driver.current_url
        current_title = self.devtools.driver.title
        print(f"[INFO] 가장 최근에 열린 창 - URL: {current_url}, 제목: {current_title}")
        
        # 2. 전환된 창이 카지노 관련 창인지 확인 (검증용)
        casino_related = any(keyword in current_url.lower() for keyword in 
                            ["evo-games", "evolution", "casino", "live", "game"])
        
        # URL 기반으로 찾지 못한 경우 페이지 제목 확인
        if not casino_related:
            casino_related = any(keyword in current_title.lower() for keyword in 
                                ["casino", "evolution", "evo", "라이브", "카지노"])
        
        if casino_related:
            print(f"[INFO] 성공적으로 카지노 창으로 전환했습니다.")
        else:
            print(f"[WARNING] 마지막 창이 카지노 창이 아닐 수 있습니다. 그래도 이 창을 사용합니다.")
            
        # 현재 창이 iframe을 포함하는지 확인하고 메인 컨텐츠로 전환
        try:
            self.devtools.driver.switch_to.default_content()
            time.sleep(0.5)  # 창 전환 안정화 대기
        except Exception as e:
            print(f"[WARNING] 메인 컨텐츠 전환 중 오류: {e}")
        
        return True

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

    def set_user_info(self, username, days_left):
        """사용자 정보 및 남은 사용 기간 설정"""
        self.username = username
        
        # 현재 날짜 기준으로 만료 날짜 계산 (23:59:59로 고정)
        current_date = datetime.now()
        expiration_date = current_date + timedelta(days=days_left)
        expiration_date = expiration_date.replace(hour=23, minute=59, second=59, microsecond=0)
        
        # 객체 속성에 만료 날짜 저장
        self.expiration_date = expiration_date
        
        # 사용자 정보 UI 업데이트
        self.update_user_data(username=username)
        
        # 남은 시간 설정 및 타이머 시작
        self.set_license_remaining_time(days_left)
        
    def add_days_left_display(self, days_left):
        """남은 사용 기간 표시 영역 추가"""
        # days_left가 None인 경우 기본값으로 대체
        if days_left is None:
            days_left = 0  # 또는 적절한 기본값 설정
        
        # 기존 남은 시간 영역 가져오기 (있으면)
        if hasattr(self, 'remaining_time_layout'):
            layout = self.remaining_time_layout
        else:
            # 없으면 새로 생성
            layout = QHBoxLayout()
            self.remaining_time_layout = layout
        
        # 기존 구성요소가 없으면 (아직 없을 경우에만 추가)
        if not hasattr(self, 'days_left_label'):
            # 사용 기간 레이블과 값 추가
            self.days_left_label = QLabel("남은 사용 기간:")
            self.days_left_value = QLabel(f"{days_left}일")
            
            # 스타일 설정
            self.days_left_label.setStyleSheet("font-weight: bold;")
            if days_left < 7:
                self.days_left_value.setStyleSheet("color: red; font-weight: bold;")
            elif days_left < 15:
                self.days_left_value.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.days_left_value.setStyleSheet("color: green; font-weight: bold;")
            
            # 레이아웃에 추가
            layout.addWidget(self.days_left_label)
            layout.addWidget(self.days_left_value)
            
            # 해당 레이아웃을 메인 레이아웃에 추가 (아직 없다면)
            if hasattr(self, 'left_panel'):
                # 기존 남은 시간 레이아웃 아래에 배치
                self.left_panel.addLayout(layout)
        else:
            # 이미 있으면 값만 업데이트
            self.days_left_value.setText(f"{days_left}일")
    
    def set_license_remaining_time(self, days_left):
        """남은 라이센스 시간 설정 및 타이머 시작"""
        # 실제 운영용 - 일 단위로 설정 (1일 = 24시간)
        self.user_remaining_seconds = days_left * 24 * 60 * 60
        
        print(f"라이센스 타이머 설정: {days_left}일 ({self.user_remaining_seconds}초)")
        
        # 남은 시간 표시 강제 업데이트
        self.update_license_time_display()
        
        # 타이머 시작
        if self.user_remaining_seconds > 0:
            self.user_time_active = True
            self.license_timer.start(1000)  # 1초마다 업데이트
            
            # 버튼 활성화
            self.enable_application_features(True)
            print(f"라이센스 타이머 시작: 남은 시간 {days_left}일")
        else:
            # 시간이 이미 0이하면 기능 비활성화
            self.user_time_active = False
            self.enable_application_features(False)
            QMessageBox.critical(self, "사용 기간 만료", "사용 가능 시간이 만료되었습니다.\n관리자에게 문의하세요.")
            print(f"라이센스 타이머 경고: 남은 시간이 0일 이하 ({days_left}일)")

    def update_license_time(self):
        """타이머에 의해 호출되는 라이센스 남은 시간 업데이트"""
        if self.user_time_active and self.user_remaining_seconds > 0:
            self.user_remaining_seconds -= 1
            self.update_license_time_display()
            
            # 남은 시간이 0이 되면 기능 비활성화
            if self.user_remaining_seconds <= 0:
                self.user_time_active = False
                self.license_timer.stop()
                self.enable_application_features(False)
                QMessageBox.critical(self, "사용 기간 만료", "사용 가능 시간이 만료되었습니다.\n관리자에게 문의하세요.")
    
    def update_license_time_display(self):
        """남은 라이센스 시간 표시 업데이트"""
        # 만약 self.expiration_date가 있다면 해당 날짜 사용
        if hasattr(self, 'expiration_date'):
            current_date = datetime.now()
            remaining_days = (self.expiration_date - current_date).days
            
            # 날짜 포맷 변경: 년/월/일 -> 년년 월월 일일
            expiration_str = self.expiration_date.strftime('%y년 %m월 %d일')
            
            # 남은 기간 및 마감 날짜 표시 (예: 1일(25년 03월 19일))
            time_str = f"{remaining_days}일({expiration_str})"
        else:
            # 기존 로직 유지 (fallback)
            days = self.user_remaining_seconds // (24 * 3600)
            time_str = f"{days}일"
        
        self.license_time_value.setText(time_str)
    
    def enable_application_features(self, enabled=True):
        """애플리케이션 주요 기능 활성화/비활성화"""
        # 시간이 만료되면 비활성화할 버튼들
        self.site1_button.setEnabled(enabled)
        self.site2_button.setEnabled(enabled)
        self.site3_button.setEnabled(enabled)
        self.start_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        self.update_room_button.setEnabled(enabled)
        self.save_room_button.setEnabled(enabled)
        
        if not enabled:
            # 현재 진행 중인 자동 매매가 있다면 중지
            if hasattr(self, 'trading_manager') and self.trading_manager.is_trading_active:
                self.trading_manager.stop_trading()
    
    def save_remaining_time(self):
        """남은 시간 정보를 DB나 파일에 저장 (선택적 구현)"""
        # 여기에 남은 시간을 DB에 저장하는 코드 추가 가능
        # 사용자 종료 후 재접속 시 이어서 사용 가능하도록
        pass
    
    # ui/main_window.py 업데이트 - 로그아웃 부분만

    def closeEvent(self, event):
        """프로그램 종료 시 호출되는 이벤트"""
        # 남은 시간 저장 (선택적 구현)
        if self.user_time_active:
            self.save_remaining_time()
        
        # 타이머 정지
        if self.license_timer.isActive():
            self.license_timer.stop()
        
        # 로그아웃 처리 추가
        if hasattr(self, 'username') and self.username:
            try:
                from utils.db_manager import DBManager
                db_manager = DBManager()
                db_manager.logout_user(self.username)
                print(f"[INFO] 사용자 '{self.username}' 로그아웃 처리 완료")
            except Exception as e:
                print(f"[ERROR] 로그아웃 처리 중 오류 발생: {e}")
        
        # 브라우저 종료
        if hasattr(self, 'devtools') and self.devtools.driver:
            try:
                self.devtools.close_browser()
            except:
                pass
        
        # 기본 이벤트 처리
        super().closeEvent(event)

    def open_site_with_refresh(self, site_number):
        """
        설정을 다시 로드한 후 사이트 열기
        브라우저가 종료된 상태라면 재시작
        
        Args:
            site_number (int): 사이트 번호 (1, 2, 3)
        """
        # 설정 매니저 재초기화 (항상 최신 설정 로드)
        self.settings_manager = SettingsManager()
        
        # 사이트 URL 가져오기
        site1, site2, site3 = self.settings_manager.get_sites()
        
        # 로그 출력
        print(f"[INFO] 설정 다시 로드 후 사이트 {site_number} 열기 시도")
        print(f"[DEBUG] 현재 사이트 설정: 사이트1={site1}, 사이트2={site2}, 사이트3={site3}")
        
        # 사이트 번호에 따라 URL 선택
        site_url = ""
        if site_number == 1:
            site_url = site1
        elif site_number == 2:
            site_url = site2
        elif site_number == 3:
            site_url = site3
            
        # 사이트 열기 전에 브라우저 상태 확인
        browser_active = self.check_browser_active()
        
        # 사이트 열기
        if site_url:
            if not browser_active:
                print("[INFO] 브라우저가 종료되었거나 없음. 새 브라우저 시작")
                self.devtools.start_browser()  # 브라우저 재시작
                
            self.open_site(site_url)
        else:
            QMessageBox.warning(self, "알림", f"사이트 {site_number}의 URL이 설정되지 않았습니다.\n설정 메뉴에서 URL을 설정해주세요.")

    def check_browser_active(self):
        """
        브라우저가 활성 상태인지 확인
        
        Returns:
            bool: 브라우저가 실행 중이고 접근 가능하면 True
        """
        if not self.devtools.driver:
            return False
            
        try:
            # 간단한 명령을 실행하여 브라우저가 응답하는지 확인
            window_handles = self.devtools.driver.window_handles
            return True
        except Exception as e:
            print(f"[WARNING] 브라우저 상태 확인 중 오류: {e}")
            # 브라우저 참조 초기화
            self.devtools.driver = None
            return False

    def on_start_button_clicked(self):
        """진행 버튼 클릭 처리"""
        try:
            # 추가: 중지 플래그 즉시 초기화
            if hasattr(self.trading_manager, 'stop_all_processes'):
                self.trading_manager.stop_all_processes = False
                
            # 추가: 목표 금액 도달 플래그 초기화
            if hasattr(self.trading_manager.balance_service, '_target_amount_reached'):
                delattr(self.trading_manager.balance_service, '_target_amount_reached')
            
            # 추가: 타이머 완전 리셋
            if hasattr(self, 'timer'):
                if self.timer.isActive():
                    self.timer.stop()
                # 새로운 타이머 생성
                from PyQt6.QtCore import QTimer
                self.timer = QTimer()
                self.timer.timeout.connect(self.update_remaining_time)
            
            # 이전 스레드 참조 제거
            if hasattr(self.trading_manager, '_analysis_thread'):
                delattr(self.trading_manager, '_analysis_thread')
            
            # 자동 매매 시작
            self.trading_manager.start_trading()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "오류", f"자동 매매 시작 중 오류가 발생했습니다.\n{str(e)}")
            