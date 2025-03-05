from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt, QTimer
from ui.header_widget import HeaderWidget
from ui.betting_widget import BettingWidget
from utils.devtools import DevToolsController
from utils.settings_manager import SettingsManager
from utils.parser import HTMLParser, CasinoParser
import time
import re

def clean_text(text):
    """숨겨진 특수 문자 제거"""
    text = re.sub(r'[\u200c\u2066\u2069]', '', text)  # 보이지 않는 문자 삭제
    return text.strip()
    
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("홀덤 자동 매매")
        self.setGeometry(100, 100, 1000, 600)  # 🌟 창 크기 확장 (기존보다 넓게 설정)
        self.setObjectName("MainWindow")  # QSS 스타일 적용을 위한 ID 지정

        # DevToolsController 및 설정 매니저 초기화
        self.devtools = DevToolsController()
        self.settings_manager = SettingsManager()
        self.is_trading_active = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_remaining_time)
        self.remaining_seconds = 0  # 초기 남은 시간 (초 단위)
        
        # 상태 변수 초기화
        self.start_amount = 0  # 시작 금액
        self.current_amount = 0  # 현재 금액
        self.total_bet_amount = 0  # 누적 배팅 금액
        self.profit_amount = 0  # 수익 금액
        self.username = ""  # 사용자명

        # 스타일 적용
        with open("ui/style.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        # 🌟 메인 위젯 및 레이아웃 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 전체 레이아웃 (왼쪽 기존 UI + 오른쪽 방 목록 패널)
        self.layout = QHBoxLayout()
        central_widget.setLayout(self.layout)

        # ✅ 왼쪽 UI (기존 UI 유지)
        self.left_panel = QVBoxLayout()
        self.layout.addLayout(self.left_panel, 3)  # 비율 3:1

        # ✅ 상단 정보바
        self.header = HeaderWidget()
        self.left_panel.addWidget(self.header)
        
        # ✅ 배팅 위젯 (현재 진행 상황 표시)
        self.betting_widget = BettingWidget()
        self.left_panel.addWidget(self.betting_widget)

        # ✅ 남은 시간 표시
        remaining_time_layout = QHBoxLayout()
        self.remaining_time_label = QLabel("남은시간")
        self.remaining_time_value = QLabel("00 : 00 : 00")
        remaining_time_layout.addWidget(self.remaining_time_label)
        remaining_time_layout.addWidget(self.remaining_time_value)
        self.left_panel.addLayout(remaining_time_layout)

        # ✅ 사이트 이동 버튼
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

        # ✅ 자동 매매 시작 / 종료 버튼
        start_stop_layout = QHBoxLayout()
        self.start_button = QPushButton("🔵 자동 매매 시작")
        self.stop_button = QPushButton("🔴 자동 매매 종료")

        self.start_button.clicked.connect(self.start_trading)
        self.stop_button.clicked.connect(self.stop_trading)

        start_stop_layout.addWidget(self.start_button)
        start_stop_layout.addWidget(self.stop_button)
        self.left_panel.addLayout(start_stop_layout)

        # 🌟 오른쪽 UI (방 목록 패널 추가)
        self.room_panel = QVBoxLayout()
        self.layout.addLayout(self.room_panel, 1)  # 비율 3:1

        # 🏠 "방 목록" 제목 추가
        self.room_label = QLabel("📋 방 목록")
        self.room_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.room_panel.addWidget(self.room_label)

        # 📊 방 목록 테이블 추가
        self.room_table = QTableWidget()
        self.room_table.setColumnCount(1)
        self.room_table.setHorizontalHeaderLabels(["방 이름"])
        self.room_table.setColumnWidth(0, 200)  # 컬럼 크기 조정
        self.room_panel.addWidget(self.room_table)

        # 🔄 방 목록 업데이트 버튼
        self.update_room_button = QPushButton("방 목록 불러오기")
        self.update_room_button.clicked.connect(self.load_rooms_into_table)
        self.room_panel.addWidget(self.update_room_button)

        # ✅ UI 초기화
        self.reset_ui()

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
        """사용자 데이터 업데이트 - 내부 변수와 UI 모두 업데이트"""
        if username is not None:
            self.username = username
            self.header.update_user_info(username)
            
        if start_amount is not None:
            self.start_amount = start_amount
            self.header.update_start_amount(start_amount)
            
        if current_amount is not None:
            self.current_amount = current_amount
            self.header.update_current_amount(current_amount)
            
            # 현재 금액이 변경되면 수익 금액도 재계산
            if self.start_amount > 0:
                new_profit = self.current_amount - self.start_amount
                self.profit_amount = new_profit
                self.header.update_profit(new_profit)
                
        if profit_amount is not None:
            self.profit_amount = profit_amount
            self.header.update_profit(profit_amount)
            
        if total_bet is not None:
            self.total_bet_amount = total_bet
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
        
        # 초기화: 모든 값을 0으로 리셋
        self.reset_ui()
        self.is_trading_active = True

        # ✅ 브라우저 실행 확인
        if not self.devtools.driver:
            self.devtools.start_browser()

        # ✅ 현재 열린 창 목록 확인
        print("[DEBUG] 창 목록 확인 중...")
        window_handles = self.devtools.driver.window_handles
        for i, handle in enumerate(window_handles):
            print(f"[DEBUG] 창 {i+1} - 핸들: {handle}")

        if len(window_handles) < 2:
            QMessageBox.warning(self, "오류", "창 개수가 부족합니다. 최소 2개의 창이 필요합니다.")
            self.is_trading_active = False
            return  # 🚨 창이 하나뿐이면 중단

        # ✅ 1번 창에서 잔액 먼저 가져오기
        print("[INFO] 1번 창(기본 사이트)에서 잔액 가져오기 시도...")
        self.devtools.driver.switch_to.window(window_handles[0])  # 1번 창 전환
        time.sleep(2)

        # ✅ 현재 페이지 HTML 가져오기
        html = self.devtools.get_page_source()
        if html:
            # ✅ HTML 저장 (디버깅용)
            with open("debug_main_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("[INFO] 1번 창 HTML 저장 완료 (debug_main_page.html)")

            # ✅ 잔액 파싱 시도
            parser = HTMLParser(html)
            balance = parser.get_balance()
            if balance is not None:
                print(f"[INFO] 현재 잔액: {balance}원")
                
                # 시작 금액 및 현재 금액 설정 (최초 시작 시 동일)
                self.update_user_data(
                    start_amount=balance,
                    current_amount=balance
                )
                
                # 유저 정보 파싱 추가
                username = parser.get_username()
                if username:
                    print(f"[INFO] 유저명: {username}")
                    self.update_user_data(username=username)
            else:
                QMessageBox.warning(self, "오류", "잔액 정보를 찾을 수 없습니다. 먼저 사이트에 로그인하세요.")
                self.is_trading_active = False
                return  # 🚨 잔액 정보를 못 찾으면 중단
        else:
            QMessageBox.warning(self, "오류", "페이지 소스를 가져올 수 없습니다.")
            self.is_trading_active = False
            return  # 🚨 HTML을 못 가져오면 중단

        # ✅ 2번 창(카지노 창)으로 전환
        print("[INFO] 카지노 창으로 전환 시도...")
        self.devtools.driver.switch_to.window(window_handles[1])  # 2번 창 전환
        time.sleep(2)

        # ✅ 전환 후 현재 URL 확인
        current_url = self.devtools.driver.current_url
        print(f"[INFO] 전환 후 현재 창 URL: {current_url}")

        # ✅ 2번 창의 HTML 저장 (새로 추가)
        casino_html = self.devtools.get_page_source()
        if casino_html:
            # ✅ HTML 저장 (디버깅용)
            with open("debug_casino_page.html", "w", encoding="utf-8") as f:
                f.write(casino_html)
            print("[INFO] 2번 창 HTML 저장 완료 (debug_casino_page.html)")
        
        if "evo-games.com" in current_url:
            print("[INFO] 카지노 창으로 정상 전환됨")
        else:
            print("[WARNING] 카지노 창이 아닐 수 있습니다 - URL: " + current_url)
            # 경고만 표시하고 계속 진행

        # ✅ 남은 시간 설정 (임시: 1시간)
        self.set_remaining_time(1, 0, 0)

        # ✅ 자동 매매 루프 시작
        self.run_auto_trading()


    def get_all_rooms(self):
        """iframe 내에서 처음 보이는 30개의 방 정보만 가져오기"""
        try:
            # iframe으로 전환
            iframe = self.devtools.driver.find_element("css selector", "iframe")
            self.devtools.driver.switch_to.frame(iframe)

            print("[INFO] iframe 내부 콘텐츠 로드 대기...")
            time.sleep(3)

            all_rooms = set()

            # ✅ 특정 클래스(tile--5d2e6) 방 이름 요소 찾기
            name_elements = self.devtools.driver.find_elements("css selector", ".tile--5d2e6")
            print(f"[INFO] 현재 보이는 방 개수: {len(name_elements)}")

            for idx, element in enumerate(name_elements):
                try:
                    full_text = element.text.strip()
                    clean_full_text = clean_text(full_text)  # ✅ 숨겨진 문자 제거
                    lines = [line.strip() for line in clean_full_text.splitlines() if line.strip()]

                    if lines:
                        room_name = clean_text(lines[0])  # ✅ 첫 번째 줄(방 이름)만 추출 후 클리닝

                        print(f"[DEBUG] room[{idx}] 원본 데이터: {repr(full_text)}")  
                        print(f"[DEBUG] room[{idx}] 첫 줄 (클린): {repr(room_name)}")  

                        if room_name:
                            all_rooms.add(room_name)
                    else:
                        print(f"[WARNING] room[{idx}] 비어있는 값 감지! -> {repr(full_text)}")

                except Exception as e:
                    print(f"[ERROR] 방 이름 가져오는 중 오류 발생: {e}")

            final_rooms = list(all_rooms)
            print(f"[INFO] 최종적으로 찾은 방 개수: {len(final_rooms)}")

            return final_rooms

        except Exception as e:
            print(f"[ERROR] get_all_rooms 실행 중 오류 발생: {e}")
            return []


    def run_auto_trading(self):
        """자동 매매 로직"""
        if not self.is_trading_active:
            return
                        
        print("[INFO] 자동 매매 진행 중...")

        try:
            print("[DEBUG] get_all_rooms() 실행 전")
            all_rooms = self.get_all_rooms()  # ✅ 여기서만 실행
            print("[DEBUG] get_all_rooms() 실행 완료, 반환된 방 개수:", len(all_rooms))

            if all_rooms:
                print("[INFO] 방 목록 수집 성공")
                self.load_rooms_into_table(all_rooms)  # ✅ 이제 방 목록을 직접 전달
            else:
                print("[WARNING] 방 목록을 가져오지 못했습니다.")
            
        except Exception as e:
            print(f"[ERROR] 자동 매매 중 오류 발생: {e}")


    def update_balance(self):
        """잔액 정보 주기적 업데이트"""
        if not self.is_trading_active or not self.devtools.driver:
            return
            
        try:
            # 현재 열린 창 목록 확인
            window_handles = self.devtools.driver.window_handles
            
            # 현재 창 저장
            current_handle = self.devtools.driver.current_window_handle
            
            # 1번 창으로 전환
            self.devtools.driver.switch_to.window(window_handles[0])
            
            # HTML 가져오기
            html = self.devtools.get_page_source()
            if html:
                # 잔액 파싱
                parser = HTMLParser(html)
                balance = parser.get_balance()
                if balance is not None:
                    print(f"[INFO] 현재 잔액 업데이트: {balance}원")
                    self.update_user_data(current_amount=balance)
            
            # 원래 창으로 복귀
            self.devtools.driver.switch_to.window(current_handle)
            
        except Exception as e:
            print(f"[ERROR] 잔액 업데이트 중 오류 발생: {e}")

    def stop_trading(self):
        """자동 매매 종료"""
        self.is_trading_active = False
        self.timer.stop()
        
        # 잔액 업데이트 타이머가 있다면 중지
        if hasattr(self, 'balance_update_timer') and self.balance_update_timer.isActive():
            self.balance_update_timer.stop()
            
        print("[INFO] 자동 매매 종료!")
        
        # 종료 시 마지막 잔액 정보 확인하여 UI 업데이트
        try:
            if self.devtools.driver:
                window_handles = self.devtools.driver.window_handles
                current_handle = self.devtools.driver.current_window_handle
                
                # 1번 창으로 전환
                self.devtools.driver.switch_to.window(window_handles[0])
                
                # 최종 HTML 가져오기
                html = self.devtools.get_page_source()
                if html:
                    parser = HTMLParser(html)
                    balance = parser.get_balance()
                    if balance is not None:
                        print(f"[INFO] 최종 잔액: {balance}원")
                        self.update_user_data(current_amount=balance)
                
                # 원래 창으로 복귀
                self.devtools.driver.switch_to.window(current_handle)
        except Exception as e:
            print(f"[ERROR] 종료 시 잔액 확인 중 오류 발생: {e}")
            
    def load_rooms_into_table(self, rooms):
        """방 목록을 테이블에 업데이트"""
        print("[DEBUG] load_rooms_into_table() 실행됨")

        if not rooms:
            QMessageBox.warning(self, "알림", "방 목록을 불러올 수 없습니다.")
            return

        self.room_table.setRowCount(len(rooms))  # 테이블 행 개수 설정

        for row, room in enumerate(rooms):
            self.room_table.setItem(row, 0, QTableWidgetItem(room))  # ✅ 받은 데이터만 사용!