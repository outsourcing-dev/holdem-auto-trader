# utils/trading_manager.py
import random
import time
import openpyxl
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
        
        # 베팅 상태 초기화
        self.has_bet_current_round = False
    
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
            
            # 새로운 게임 결과가 있는지 확인
            new_game_count = game_state['round']
            latest_result = game_state.get('latest_result')
            
            # 최근 결과 업데이트
            recent_results = game_state.get('recent_results', [])
            actual_results = game_state.get('actual_results', [])
            
            print(f"\n[INFO] 현재 게임 수: {new_game_count}")
            print(f"[INFO] 최신 결과: {latest_result}")
            
            # ExcelManager 인스턴스 생성
            from utils.excel_manager import ExcelManager
            excel_manager = ExcelManager()
            
            # 전에 없던 새로운 결과가 있는지 확인 (최신 결과가 있고 이전 게임 수보다 증가했는지)
            has_new_result = new_game_count > self.game_count and latest_result is not None
            
            if has_new_result:
                print(f"[INFO] 새로운 게임 결과 감지: {latest_result}")
                
                # 새 라운드 시작 시 베팅 상태 초기화
                self.has_bet_current_round = False
                
                # 첫 실행 여부 확인 (self.game_count가 0이면 첫 실행)
                is_first_run = self.game_count == 0
                
                if is_first_run and actual_results:
                    # 1. 최초 입장 시: 10개 결과를 처음부터 기록
                    print("[INFO] 첫 실행 감지: 엑셀에 최근 10개 결과 기록")
                    excel_manager.write_filtered_game_results([], actual_results)
                    print(f"[INFO] 엑셀에 게임 결과 {len(actual_results)}개 기록 완료")
                else:
                    # 2. 이후 실행: 마지막 열 다음에 결과 추가
                    # 현재 열(마지막으로 결과가 입력된 열 다음) 찾기
                    current_column = excel_manager.get_current_column()
                    
                    if current_column:
                        # 2-1. 새 결과 기록
                        print(f"[INFO] {current_column}3에 새 결과 '{latest_result}' 기록 중...")
                        excel_manager.write_game_result(current_column, latest_result)
                        print(f"[INFO] {current_column}3에 '{latest_result}' 기록 완료")
                    else:
                        print("[WARNING] 기록할 빈 열을 찾을 수 없음. 엑셀 초기화 필요할 수 있음")
                
                # 새 결과를 기록한 후 엑셀 저장
                save_success = excel_manager.save_with_app()
                
                if save_success:
                    # 마지막으로 입력된 열 찾기
                    if is_first_run:
                        # 첫 실행 시: 입력한 결과 수에 따라 마지막 열 계산
                        last_column_idx = 1 + len(actual_results)  # B(2) + results_count - 1
                        last_column = openpyxl.utils.get_column_letter(last_column_idx)
                    else:
                        # 이후 실행 시: current_column이 마지막 입력된 열
                        last_column = current_column
                    
                    # 3. 다음 열의 PICK 값 확인 (마지막 열 + 1의 12행)
                    next_pick = excel_manager.check_next_column_pick(last_column)
                    
                    # UI 업데이트
                    self.main_window.update_betting_status(
                        room_name=f"{self.current_room_name} (게임 수: {new_game_count})",
                        pick=next_pick
                    )
                    
                    print(f"[INFO] 다음 배팅: {next_pick}")
                    
                    # PICK 값이 P 또는 B일 경우 베팅 실행
                    if next_pick in ['P', 'B']:
                        self.place_bet(next_pick)
                    else:
                        print(f"[INFO] 베팅 없음 (PICK 값: {next_pick})")
                else:
                    # 수동 저장 안내
                    print("\n" + "=" * 50)
                    print("자동 Excel 저장에 실패했습니다.")
                    print("엑셀 파일을 수동으로 저장해주세요.")
                    print("=" * 50)
            else:
                # 새로운 결과가 없으면 기존 정보로 UI만 업데이트
                print("[INFO] 새로운 게임 결과 없음, 이전 상태 유지")
                
                # UI 업데이트 (방 이름만 업데이트)
                self.main_window.update_betting_status(
                    room_name=f"{self.current_room_name} (게임 수: {new_game_count})"
                )
            
            # 게임 카운트 업데이트
            self.game_count = new_game_count
            self.recent_results = recent_results
            
            # 2초마다 분석 수행
            self.main_window.set_remaining_time(0, 0, 2)
            
        except Exception as e:
            print(f"[ERROR] 게임 상태 분석 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            
    def place_bet(self, bet_type):
        """
        베팅 타입(P 또는 B)에 따라 적절한 베팅 영역을 클릭합니다.
        중복 클릭 방지를 위해 베팅 상태를 기록합니다.
        
        Args:
            bet_type (str): 'P'(플레이어) 또는 'B'(뱅커)
        
        Returns:
            bool: 성공 여부
        """
        if not self.is_trading_active:
            print("[INFO] 자동 매매가 활성화되지 않았습니다.")
            return False
        
        # 이미 베팅했는지 확인 (중복 베팅 방지)
        if hasattr(self, 'has_bet_current_round') and self.has_bet_current_round:
            print("[INFO] 이미 현재 라운드에 베팅했습니다.")
            return False
        
        try:
            # iframe으로 전환
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            # 베팅 대상 선택
            if bet_type == 'P':
                # Player 영역 찾기 및 클릭
                selector = "div.spot--5ad7f[data-betspot-destination='Player']"
                print(f"[INFO] Player 베팅 영역 클릭 시도: {selector}")
            elif bet_type == 'B':
                # Banker 영역 찾기 및 클릭
                selector = "div.spot--5ad7f[data-betspot-destination='Banker']"
                print(f"[INFO] Banker 베팅 영역 클릭 시도: {selector}")
            else:
                print(f"[ERROR] 잘못된 베팅 타입: {bet_type}")
                return False
            
            # 요소 찾기
            bet_element = WebDriverWait(self.devtools.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            
            # 요소가 활성화되어 있는지 확인 (클래스에 'active--dc7b3'가 있는지)
            is_active = 'active--dc7b3' in bet_element.get_attribute('class')
            if is_active:
                print(f"[INFO] 이미 {bet_type} 영역이 활성화되어 있습니다.")
            else:
                # 클릭
                bet_element.click()
                print(f"[SUCCESS] {bet_type} 영역 클릭 완료!")
            
            # 베팅 상태 기록 (중복 베팅 방지)
            self.has_bet_current_round = True
            
            # UI 업데이트
            self.main_window.update_betting_status(
                room_name=f"{self.current_room_name} (게임 수: {self.game_count}, 베팅: {bet_type})"
            )
            
            return True
        
        except Exception as e:
            print(f"[ERROR] 베팅 중 오류 발생: {e}")
            return False
            
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

    def stop_trading(self):
        """자동 매매 중지"""
        if not self.is_trading_active:
            print("[INFO] 자동 매매가 이미 중지된 상태입니다.")
            return
            
        print("[INFO] 자동 매매 중지 중...")
        self.is_trading_active = False
        
        # 타이머 중지
        self.main_window.timer.stop()
        
        # 메시지 표시
        QMessageBox.information(self.main_window, "알림", "자동 매매가 중지되었습니다.")