import random
import time
from PyQt6.QtWidgets import QMessageBox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.parser import HTMLParser

class TradingManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.devtools = main_window.devtools
        self.room_manager = main_window.room_manager
        self.is_trading_active = False
    
    def start_trading(self):
        """자동 매매 시작"""
        if self.is_trading_active:
            print("[INFO] 이미 자동 매매가 진행 중입니다.")
            return

        # 1. 방 목록 체크 여부 확인
        if not self.room_manager.rooms_data:
            QMessageBox.warning(self.main_window, "알림", "방 목록을 먼저 불러와주세요.")
            return
            
        # 2. 체크된 방이 있는지 확인
        checked_rooms = self.room_manager.get_checked_rooms()
        if not checked_rooms:
            QMessageBox.warning(self.main_window, "알림", "자동 매매를 시작할 방을 선택해주세요.")
            return
        
        print(f"[INFO] 선택된 방 {len(checked_rooms)}개: {[room['name'] for room in checked_rooms]}")
        
        # ✅ 랜덤 방 선택 후 검색 입력 및 클릭
        self.enter_room_search_and_click(checked_rooms)
        
        # ✅ 기존 잔액 및 UI 초기화
        self.main_window.reset_ui()

        # ✅ 브라우저 실행 확인
        if not self.devtools.driver:
            self.devtools.start_browser()

        # ✅ 창 개수 확인
        window_handles = self.devtools.driver.window_handles
        if len(window_handles) < 2:
            QMessageBox.warning(self.main_window, "오류", "창 개수가 부족합니다. 최소 2개의 창이 필요합니다.")
            return

        # ✅ 메인 창으로 전환하여 잔액 가져오기
        if not self.main_window.switch_to_main_window():
            QMessageBox.warning(self.main_window, "오류", "메인 창으로 전환할 수 없습니다.")
            return

        # ✅ 잔액 파싱
        html = self.devtools.get_page_source()
        if html:
            parser = HTMLParser(html)
            balance = parser.get_balance()
            if balance is not None:
                print(f"[INFO] 현재 잔액: {balance}원")

                # 시작 금액 및 현재 금액 설정
                self.main_window.update_user_data(
                    start_amount=balance,
                    current_amount=balance
                )

                # 유저 정보 파싱
                username = parser.get_username()
                if username:
                    print(f"[INFO] 유저명: {username}")
                    self.main_window.update_user_data(username=username)
            else:
                QMessageBox.warning(self.main_window, "오류", "잔액 정보를 찾을 수 없습니다. 먼저 사이트에 로그인하세요.")
                return
        else:
            QMessageBox.warning(self.main_window, "오류", "페이지 소스를 가져올 수 없습니다.")
            return

        # ✅ 카지노 창으로 전환
        if not self.main_window.switch_to_casino_window():
            QMessageBox.warning(self.main_window, "오류", "카지노 창으로 전환할 수 없습니다.")
            return

        # ✅ 자동 매매 활성화
        self.is_trading_active = True
        print("[INFO] 자동 매매 시작!")

        # ✅ 남은 시간 설정 (임시: 1시간)
        self.main_window.set_remaining_time(1, 0, 0)

        # ✅ 자동 매매 루프 시작
        self.run_auto_trading()

    def enter_room_search_and_click(self, checked_rooms):
        """✅ 랜덤으로 체크된 방을 선택하여 검색 입력 후 첫 번째 결과 클릭"""
        selected_room = random.choice(checked_rooms)
        room_name = selected_room['name']
        print(f"[INFO] 선택된 방: {room_name}")

        try:
            # ✅ iframe 내부로 이동하여 입력 필드 찾기
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)

            # ✅ 검색 입력 필드 찾기 및 입력
            search_input = self.devtools.driver.find_element(By.CSS_SELECTOR, "input.TableTextInput--464ac")
            search_input.clear()
            search_input.send_keys(room_name)
            print(f"[SUCCESS] 방 이름 '{room_name}' 입력 완료!")

            # ✅ 검색 결과 대기 (최대 5초)
            wait = WebDriverWait(self.devtools.driver, 5)
            first_result = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-role='search-result']"))
            )

            # ✅ 첫 번째 검색 결과 클릭
            first_result.click()
            print("[SUCCESS] 첫 번째 검색 결과 클릭 완료!")

            # ✅ 새로운 창 핸들 감지 후 전환
            time.sleep(2)  # 새 창이 열리는 시간 대기
            new_window_handles = self.devtools.driver.window_handles
            if len(new_window_handles) > 1:
                self.devtools.driver.switch_to.window(new_window_handles[-1])
                print("[INFO] 새로운 방으로 포커스 변경 완료!")
                time.sleep(10)
                # ✅ 방 종료 버튼 클릭
                self.close_room()

        except Exception as e:
            print(f"[ERROR] 방 검색 및 클릭 실패: {e}")
        finally:
            self.devtools.driver.switch_to.default_content()  # 다시 메인 프레임으로 이동

    def close_room(self):
        """✅ 현재 열린 방을 종료"""
        try:
            # ✅ iframe 내부로 이동하여 종료 버튼 찾기
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            print("[INFO] iframe 내부에서 종료 버튼 탐색 중...")

            # ✅ 종료 버튼 찾기 및 클릭
            close_button = WebDriverWait(self.devtools.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-role='close-button']"))
            )
            close_button.click()
            print("[SUCCESS] 방 종료 버튼 클릭 완료!")

            # ✅ 다시 메인 프레임으로 전환
            self.devtools.driver.switch_to.default_content()

        except Exception as e:
            print(f"[ERROR] 방 종료 실패: {e}")



    def run_auto_trading(self):
        """자동 매매 로직"""
        if not self.is_trading_active:
            return
                        
        print("[INFO] 자동 매매 진행 중...")
        
        # 체크된 방 목록 확인
        checked_rooms = self.room_manager.get_checked_rooms()
        print(f"[INFO] 매매 진행할 방 {len(checked_rooms)}개")
        
        # 예시: 첫 번째 체크된 방 정보 UI에 표시
        if checked_rooms:
            first_room = checked_rooms[0]
            self.main_window.update_betting_status(room_name=first_room["name"])
            print(f"[INFO] 현재 진행 중인 방: {first_room['name']}")

