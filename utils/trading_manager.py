# 3. trading_manager.py - 자동 매매 관련 기능
from PyQt6.QtWidgets import QMessageBox
from utils.parser import HTMLParser
import time

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

        print("[INFO] 자동 매매 시작!")
        
        # 초기화: 모든 값을 0으로 리셋
        self.main_window.reset_ui()
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
            QMessageBox.warning(self.main_window, "오류", "창 개수가 부족합니다. 최소 2개의 창이 필요합니다.")
            self.is_trading_active = False
            return  # 🚨 창이 하나뿐이면 중단

        # ✅ 1번 창에서 잔액 먼저 가져오기
        print("[INFO] 1번 창(기본 사이트)에서 잔액 가져오기 시도...")
        self.devtools.driver.switch_to.window(window_handles[0])  # 1번 창 전환
        time.sleep(2)

        # ✅ 현재 페이지 HTML 가져오기
        html = self.devtools.get_page_source()
        if html:
            # ✅ 잔액 파싱 시도
            parser = HTMLParser(html)
            balance = parser.get_balance()
            if balance is not None:
                print(f"[INFO] 현재 잔액: {balance}원")
                
                # 시작 금액 및 현재 금액 설정 (최초 시작 시 동일)
                self.main_window.update_user_data(
                    start_amount=balance,
                    current_amount=balance
                )
                
                # 유저 정보 파싱 추가
                username = parser.get_username()
                if username:
                    print(f"[INFO] 유저명: {username}")
                    self.main_window.update_user_data(username=username)
            else:
                QMessageBox.warning(self.main_window, "오류", "잔액 정보를 찾을 수 없습니다. 먼저 사이트에 로그인하세요.")
                self.is_trading_active = False
                return  # 🚨 잔액 정보를 못 찾으면 중단
        else:
            QMessageBox.warning(self.main_window, "오류", "페이지 소스를 가져올 수 없습니다.")
            self.is_trading_active = False
            return  # 🚨 HTML을 못 가져오면 중단

        # ✅ 2번 창(카지노 창)으로 전환
        print("[INFO] 카지노 창으로 전환 시도...")
        self.devtools.driver.switch_to.window(window_handles[1])  # 2번 창 전환
        time.sleep(2)

        # ✅ 전환 후 현재 URL 확인
        current_url = self.devtools.driver.current_url
        print(f"[INFO] 전환 후 현재 창 URL: {current_url}")

        # ✅ 2번 창의 HTML 가져오기
        casino_html = self.devtools.get_page_source()
        
        if "evo-games.com" in current_url:
            print("[INFO] 카지노 창으로 정상 전환됨")
        else:
            print("[WARNING] 카지노 창이 아닐 수 있습니다 - URL: " + current_url)
            # 경고만 표시하고 계속 진행

        # ✅ 남은 시간 설정 (임시: 1시간)
        self.main_window.set_remaining_time(1, 0, 0)

        # ✅ 자동 매매 루프 시작
        self.run_auto_trading()
    
    def run_auto_trading(self):
        """자동 매매 로직"""
        if not self.is_trading_active:
            return
                        
        print("[INFO] 자동 매매 진행 중...")

        try:
            print("[DEBUG] 방 목록 가져오기 실행 전")
            all_rooms = self.room_manager.get_all_rooms()
            print("[DEBUG] 방 목록 가져오기 실행 완료, 반환된 방 개수:", len(all_rooms))

            if all_rooms:
                print("[INFO] 방 목록 수집 성공")
                self.room_manager.load_rooms_into_table(all_rooms)
            else:
                print("[WARNING] 방 목록을 가져오지 못했습니다.")
            
        except Exception as e:
            print(f"[ERROR] 자동 매매 중 오류 발생: {e}")
    
    def stop_trading(self):
        """자동 매매 종료"""
        self.is_trading_active = False
        self.main_window.timer.stop()
        
        # 잔액 업데이트 타이머가 있다면 중지
        if hasattr(self.main_window, 'balance_update_timer') and self.main_window.balance_update_timer.isActive():
            self.main_window.balance_update_timer.stop()
            
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
                        self.main_window.update_user_data(current_amount=balance)
                
                # 원래 창으로 복귀
                self.devtools.driver.switch_to.window(current_handle)
        except Exception as e:
            print(f"[ERROR] 종료 시 잔액 확인 중 오류 발생: {e}")
    
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
                    self.main_window.update_user_data(current_amount=balance)
            
            # 원래 창으로 복귀
            self.devtools.driver.switch_to.window(current_handle)
            
        except Exception as e:
            print(f"[ERROR] 잔액 업데이트 중 오류 발생: {e}")