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
        
        # 초기화: 모든 값을 0으로 리셋
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
            
        # 자동 매매 활성화
        self.is_trading_active = True
        print("[INFO] 자동 매매 시작!")

        # ✅ 남은 시간 설정 (임시: 1시간)
        self.main_window.set_remaining_time(1, 0, 0)

        # ✅ 자동 매매 루프 시작
        self.run_auto_trading()
    
    def run_auto_trading(self):
        """자동 매매 로직"""
        if not self.is_trading_active:
            return
                        
        print("[INFO] 자동 매매 진행 중...")
        
        # 체크된 방 목록 확인
        checked_rooms = self.room_manager.get_checked_rooms()
        print(f"[INFO] 매매 진행할 방 {len(checked_rooms)}개")
        
        # 여기에 체크된 방들에 대한 매매 로직 구현
        # ...

        # 예시: 첫 번째 체크된 방 정보 UI에 표시
        if checked_rooms:
            first_room = checked_rooms[0]
            self.main_window.update_betting_status(room_name=first_room["name"])
            print(f"[INFO] 현재 진행 중인 방: {first_room['name']}")
    
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
            # 메인 창으로 전환하여 잔액 확인
            if self.main_window.switch_to_main_window():
                html = self.devtools.get_page_source()
                if html:
                    parser = HTMLParser(html)
                    balance = parser.get_balance()
                    if balance is not None:
                        print(f"[INFO] 최종 잔액: {balance}원")
                        self.main_window.update_user_data(current_amount=balance)
                
                # 다시 카지노 창으로 전환
                self.main_window.switch_to_casino_window()
        except Exception as e:
            print(f"[ERROR] 종료 시 잔액 확인 중 오류 발생: {e}")
    
    def update_balance(self):
        """잔액 정보 주기적 업데이트"""
        if not self.is_trading_active or not self.devtools.driver:
            return
            
        try:
            # 현재 창 저장
            current_handle = self.devtools.driver.current_window_handle
            
            # 메인 창으로 전환
            if self.main_window.switch_to_main_window():
                # 잔액 파싱
                html = self.devtools.get_page_source()
                if html:
                    parser = HTMLParser(html)
                    balance = parser.get_balance()
                    if balance is not None:
                        print(f"[INFO] 현재 잔액 업데이트: {balance}원")
                        self.main_window.update_user_data(current_amount=balance)
            
            # 원래 창으로 복귀
            self.devtools.driver.switch_to.window(current_handle)
            
        except Exception as e:
            print(f"[ERROR] 잔액 업데이트 중 오류 발생: {e}")