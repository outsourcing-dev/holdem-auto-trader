from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from ui.header_widget import HeaderWidget
from ui.betting_widget import BettingWidget
from utils.devtools import DevToolsController
from utils.settings_manager import SettingsManager
from utils.parser import HTMLParser, CasinoParser
import time

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
        
        # 상태 변수 초기화
        self.start_amount = 0  # 시작 금액
        self.current_amount = 0  # 현재 금액
        self.total_bet_amount = 0  # 누적 배팅 금액
        self.profit_amount = 0  # 수익 금액
        self.username = ""  # 사용자명

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
        
        # UI 초기화 - 모든 값을 0원으로 설정
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
        """iframe 내에서 스크롤하며 모든 방 정보 가져오기"""
        try:
            # iframe으로 전환
            iframe = self.devtools.driver.find_element("css selector", "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            # 콘텐츠 로드 대기
            print("[INFO] iframe 내부 콘텐츠 로드 대기...")
            time.sleep(3)
            
            # 방 이름 요소 직접 찾기
            all_rooms = []
            name_elements = self.devtools.driver.find_elements("css selector", "[data-role='tile-name']")
            
            print(f"[INFO] 발견된 방 이름 요소 수: {len(name_elements)}")
            
            for element in name_elements:
                try:
                    room_name = element.text
                    if room_name:
                        # 방 요소 (상위 요소) 찾기
                        tile_element = element.find_element("xpath", "./ancestor::*[@data-role='table-tile']")
                        
                        room_info = {
                            'name': room_name,
                            'element': tile_element
                        }
                        all_rooms.append(room_info)
                        print(f"[INFO] 방 발견: {room_name}")
                except Exception as e:
                    print(f"[WARNING] 방 정보 처리 중 오류: {e}")
            
            # 메인 프레임으로 돌아가기
            self.devtools.driver.switch_to.default_content()
            
            print(f"[INFO] 총 {len(all_rooms)}개의 방을 찾았습니다.")
            return all_rooms
            
        except Exception as e:
            print(f"[ERROR] 방 정보 수집 중 오류 발생: {e}")
            # 실패 시 메인 프레임으로 복귀 시도
            try:
                self.devtools.driver.switch_to.default_content()
            except:
                pass
            return []
        
    def run_auto_trading(self):
        """자동 매매 로직"""
        if not self.is_trading_active:
            return
                
        # TODO: 파싱 및 자동 매매 로직 구현
        print("[INFO] 자동 매매 진행 중...")
        
        # iframe 내부 콘텐츠 접근
        print("[INFO] iframe 내부 콘텐츠 접근 시도...")
        try:
            # iframe에서 모든 방 정보 가져오기
            all_rooms = self.get_all_rooms()
            
            if all_rooms:
                print("[INFO] 방 목록 수집 성공")
                # 여기서 수집된 방 정보를 활용해 자동 매매 로직 구현
                # 예: 특정 조건의 방 선택, 입장, 베팅 등
                
                # 테스트용: 첫 번째 방 정보 표시
                if len(all_rooms) > 0:
                    first_room = all_rooms[0]
                    self.update_betting_status(
                        room_name=first_room['name'],
                        pick="B",
                        step_markers={1: "X", 2: "X", 3: "X", 4: "O"}
                    )
                    self.add_betting_result(1, first_room['name'], 4, "적중")
            else:
                print("[WARNING] 방 목록을 가져오지 못했습니다.")
                # 기본 테스트 데이터 사용
                # self.update_betting_status(
                #     room_name="스피드바카라 A",
                #     pick="B",
                #     step_markers={1: "X", 2: "X", 3: "X", 4: "O"}
                # )
                # self.add_betting_result(1, "스피드바카라 A", 4, "적중")
            
        except Exception as e:
            print(f"[ERROR] 자동 매매 중 오류 발생: {e}")
            # 오류 발생 시 기본 테스트 데이터 사용
            # self.update_betting_status(
            #     room_name="스피드바카라 A",
            #     pick="B",
            #     step_markers={1: "X", 2: "X", 3: "X", 4: "O"}
            # )
            # self.add_betting_result(1, "스피드바카라 A", 4, "적중")
        
        # 잔액 업데이트 주기적 실행을 위한 타이머 설정
        self.balance_update_timer = QTimer(self)
        self.balance_update_timer.timeout.connect(self.update_balance)
        self.balance_update_timer.start(10000)  # 10초마다 잔액 갱신
        
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