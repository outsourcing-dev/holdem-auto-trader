# utils/trading_manager.py
import random
import time
from PyQt6.QtWidgets import QMessageBox
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.parser import HTMLParser, CasinoParser
from modules.game_detector import GameDetector

class TradingManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.devtools = main_window.devtools
        self.room_manager = main_window.room_manager
        self.is_trading_active = False
        
        # 게임 상태 감지 모듈 초기화
        self.game_detector = GameDetector()
        
        # 현재 게임 정보 초기화
        self.current_room_name = ""
        self.game_count = 0
        self.recent_results = []
    
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

        # ✅ 게임 정보 초기 분석
        self.analyze_current_game()

        # ✅ 자동 매매 루프 시작 (여기서는 결과 출력만 시연)
        self.run_auto_trading()

    def enter_room_search_and_click(self, checked_rooms):
        """✅ 랜덤으로 체크된 방을 선택하여 검색 입력 후 첫 번째 결과 클릭"""
        selected_room = random.choice(checked_rooms)
        room_name = selected_room['name']
        self.current_room_name = room_name
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
                time.sleep(5)  # 게임 로딩 대기
                
                # UI 업데이트
                self.main_window.update_betting_status(room_name=room_name)

        except Exception as e:
            print(f"[ERROR] 방 검색 및 클릭 실패: {e}")
            
    def analyze_current_game(self):
        """현재 게임 상태를 분석하여 게임 수와 결과를 확인"""
        try:
            print("[INFO] 현재 게임 상태 분석 중...")
            
            # iframe으로 전환
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            # 페이지 소스 가져오기
            html_content = self.devtools.driver.page_source
            
            # 게임 상태 감지
            game_state = self.game_detector.detect_game_state(html_content)
            
            # 게임 수와 최근 결과 저장
            self.game_count = game_state['round']
            self.recent_results = game_state.get('recent_results', [])
            
            # TIE를 제외한 결과 가져오기 (필터링된 결과)
            filtered_results = game_state.get('filtered_results', [])
            
            # TIE 포함 실제 사용할 결과 (TIE 개수에 따라 동적으로 조정됨)
            actual_results = game_state.get('actual_results', [])
            tie_count = game_state.get('tie_count', 0)
            total_needed = game_state.get('total_needed', 0)
            
            print(f"\n[INFO] 현재 게임 수: {self.game_count}")
            if game_state.get('latest_game_coords'):
                print(f"[INFO] 최신 게임 좌표: ({game_state['latest_game_coords'][0]}, {game_state['latest_game_coords'][1]})")
            print(f"[INFO] 최신 결과: {game_state.get('latest_result', 'None')}")
            
            # TIE 개수와 필요한 총 결과 개수 출력
            print(f"[INFO] TIE 개수: {tie_count}, 필요한 총 결과 개수: {total_needed}")
            
            # 최근 결과 (TIE 포함)
            recent_display = self.recent_results[-10:] if len(self.recent_results) > 10 else self.recent_results
            print(f"[INFO] 최근 게임 결과 (최대 10개): {recent_display}")
            
            # TIE 포함 실제 사용할 결과 (10 + TIE 개수)
            print(f"[INFO] 실제 사용 결과 (TIE 포함, {len(actual_results)}개): {actual_results}")
            
            # TIE를 제외한 결과
            print(f"[INFO] TIE 제외 결과 (정확히 {len(filtered_results)}개): {filtered_results}")
            
            # 결과를 엑셀에 기록할 경우, filtered_results를 사용
            
            # game_results 정보 출력 (게임 번호와 결과)
            if 'game_results' in game_state:
                print("\n[INFO] 게임 번호별 결과:")
                for game_number, result in game_state['game_results'][-10:]:  # 최근 10개만 출력
                    print(f"  게임 #{game_number}: {result}")
            
            # 사용자 인터페이스 업데이트
            self.main_window.update_betting_status(
                room_name=f"{self.current_room_name} (게임 수: {self.game_count})",
                pick=game_state.get('latest_result', '')
            )
            
            # 2초마다 자동으로 분석 수행
            self.main_window.set_remaining_time(0, 0, 2)  # 2초 타이머 설정
            
        except Exception as e:
            print(f"[ERROR] 게임 상태 분석 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            
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
        """자동 매매 루프"""
        if not self.is_trading_active:
            return
                        
        print("[INFO] 자동 매매 진행 중...")
        
        # 초기 게임 분석
        self.analyze_current_game()
        
        # 게임 모니터링 루프 설정 (게임이 약 10초 간격으로 빠르게 진행됨)
        monitoring_interval = 2  # 2초마다 체크하여 변화 감지
        self.main_window.set_remaining_time(0, 0, monitoring_interval)