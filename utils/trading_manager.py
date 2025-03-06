# utils/trading_manager.py
import random
import time
import logging
import openpyxl
from PyQt6.QtWidgets import QMessageBox
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils.parser import HTMLParser
from modules.game_detector import GameDetector
from utils.game_controller import GameController
from services.room_entry_service import RoomEntryService
from services.excel_trading_service import ExcelTradingService

class TradingManager:
    def __init__(self, main_window, logger=None):
        """TradingManager 초기화"""
        # 로거 설정
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # 기본 속성 초기화
        self.main_window = main_window
        self.devtools = main_window.devtools
        self.room_manager = main_window.room_manager
        
        # 상태 관리 속성
        self.is_trading_active = False
        self.current_room_name = ""
        self.game_count = 0
        self.has_bet_current_round = False
        self.result_count = 0
        
        # 게임 관련 모듈
        self.game_detector = GameDetector()
        self.game_controller = None

        # RoomEntryService 초기화
        self.room_entry_service = RoomEntryService(
            devtools=self.devtools, 
            main_window=self.main_window, 
            room_manager=self.room_manager, 
            logger=self.logger
        )

        # ExcelTradingService 초기화
        self.excel_trading_service = ExcelTradingService(
            main_window=self.main_window, 
            logger=self.logger
        )

    def start_trading(self):
        """자동 매매 시작 로직"""
        try:
            # 사전 검증
            if not self._validate_trading_prerequisites():
                return

            # 방 선택 및 입장 (RoomEntryService 사용)
            self.current_room_name = self.room_entry_service.enter_room()
            
            # 방 입장에 실패한 경우
            if not self.current_room_name:
                return

            # 기존 잔액 및 UI 초기화
            self.main_window.reset_ui()

            # 브라우저 실행 확인
            if not self.devtools.driver:
                self.devtools.start_browser()
                
            # 게임 컨트롤러 초기화
            self.game_controller = GameController(self.devtools.driver)

            # 창 개수 확인
            window_handles = self.devtools.driver.window_handles
            if len(window_handles) < 2:
                QMessageBox.warning(self.main_window, "오류", "창 개수가 부족합니다. 최소 2개의 창이 필요합니다.")
                return

            # 메인 창으로 전환하여 잔액 가져오기
            if not self.main_window.switch_to_main_window():
                QMessageBox.warning(self.main_window, "오류", "메인 창으로 전환할 수 없습니다.")
                return

            # 잔액 파싱
            html = self.devtools.get_page_source()
            if html:
                parser = HTMLParser(html)
                balance = parser.get_balance()
                if balance is not None:
                    self.logger.info(f"현재 잔액: {balance}원")

                    # 시작 금액 및 현재 금액 설정
                    self.main_window.update_user_data(
                        start_amount=balance,
                        current_amount=balance
                    )

                    # 유저 정보 파싱
                    username = parser.get_username()
                    if username:
                        self.logger.info(f"유저명: {username}")
                        self.main_window.update_user_data(username=username)
                else:
                    QMessageBox.warning(self.main_window, "오류", "잔액 정보를 찾을 수 없습니다. 먼저 사이트에 로그인하세요.")
                    return
            else:
                QMessageBox.warning(self.main_window, "오류", "페이지 소스를 가져올 수 없습니다.")
                return

            # 카지노 창으로 전환
            if not self.main_window.switch_to_casino_window():
                QMessageBox.warning(self.main_window, "오류", "카지노 창으로 전환할 수 없습니다.")
                return

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info("자동 매매 시작!")

            # 남은 시간 설정 (임시: 1시간)
            self.main_window.set_remaining_time(1, 0, 0)

            # 게임 정보 초기 분석
            self.analyze_current_game()

            # 자동 매매 루프 시작
            self.run_auto_trading()

        except Exception as e:
            # 예외 상세 로깅
            self.logger.error(f"자동 매매 시작 중 오류 발생: {e}", exc_info=True)
            
            # 사용자에게 오류 메시지 표시
            QMessageBox.critical(
                self.main_window, 
                "자동 매매 오류", 
                f"자동 매매를 시작할 수 없습니다.\n오류: {str(e)}"
            )

    def _validate_trading_prerequisites(self):
        """자동 매매 시작 전 사전 검증"""
        if self.is_trading_active:
            self.logger.warning("이미 자동 매매가 진행 중입니다.")
            return False
        
        if not self.room_manager.rooms_data:
            QMessageBox.warning(self.main_window, "알림", "방 목록을 먼저 불러와주세요.")
            return False
        
        checked_rooms = self.room_manager.get_checked_rooms()
        if not checked_rooms:
            QMessageBox.warning(self.main_window, "알림", "자동 매매를 시작할 방을 선택해주세요.")
            return False
        
        self.logger.info(f"선택된 방 {len(checked_rooms)}개: {[room['name'] for room in checked_rooms]}")
        return True

    # trading_manager.py의 analyze_current_game 메서드 수정
    def analyze_current_game(self):
        """현재 게임 상태를 분석하여 게임 수와 결과를 확인"""
        try:
            self.logger.info("현재 게임 상태 분석 중...")
            
            # iframe으로 전환
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            # 페이지 소스 가져오기
            html_content = self.devtools.driver.page_source
            
            # 게임 상태 감지
            game_state = self.game_detector.detect_game_state(html_content)
            
            # 게임 결과 처리 (ExcelTradingService 사용)
            result = self.excel_trading_service.process_game_results(
                game_state, 
                self.game_count, 
                self.current_room_name
            )

            # 결과 처리
            if result[0] is not None:  # last_column이 None이 아닌 경우에만 처리
                last_column, new_game_count, recent_results, next_pick = result

                # 새로운 게임이 시작되면 베팅 상태 초기화
                if new_game_count > self.game_count:
                    self.has_bet_current_round = False
                    self.logger.info(f"새로운 게임 시작: 베팅 상태 초기화 (게임 수: {new_game_count})")

                # UI 업데이트
                self.main_window.update_betting_status(
                    room_name=f"{self.current_room_name} (게임 수: {new_game_count})",
                    pick=next_pick
                )
                
                # PICK 값이 P 또는 B일 경우 베팅 실행
                if next_pick in ['P', 'B'] and not self.has_bet_current_round:
                    self.place_bet(next_pick)
                else:
                    self.logger.info(f"베팅 없음 (PICK 값: {next_pick}, 베팅 상태: {self.has_bet_current_round})")

                # 게임 카운트 및 최근 결과 업데이트
                self.game_count = new_game_count
                self.recent_results = recent_results
            
            # 2초마다 분석 수행
            self.main_window.set_remaining_time(0, 0, 2)
            
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"게임 상태 분석 중 오류 발생: {e}", exc_info=True)
            
            # 스택 트레이스 출력
            import traceback
            traceback.print_exc()
            
    def check_betting_result(self, column, latest_result):
        """
        특정 열의 베팅 결과를 확인하고 UI를 업데이트합니다.
        
        Args:
            column (str): 확인할 열 문자 (예: 'B', 'C', 'D')
            latest_result (str): 최신 게임 결과 ('P', 'B', 'T')
            
        Returns:
            bool: 베팅 성공 여부
        """
        try:
            from utils.excel_manager import ExcelManager
            excel_manager = ExcelManager()
            
            # 현재 PICK 값 확인 (현재 열의 12행)
            _, current_pick = excel_manager.check_betting_needed(column)
            
            # 결과 확인 (현재 열의 16행)
            is_win, result_value = excel_manager.check_result(column)
            
            # 결과 번호 증가
            self.result_count += 1
            
            # UI에 결과 추가
            result_text = "적중" if is_win else "실패"
            self.main_window.add_betting_result(
                no=self.result_count,
                room_name=self.current_room_name,
                step=1,  # 현재는 단계 구현 없음, 향후 마틴 단계 추가 필요
                result=result_text
            )
            
            marker = "O" if is_win else "X"
            self.main_window.update_betting_status(
                step_markers={1: marker}  # 현재는 첫 번째 단계만 표시
            )
            
            self.logger.info(f"베팅 결과 확인 - 열: {column}, PICK: {current_pick}, 결과: {latest_result}, 승패: {result_text}")
            
            return is_win
            
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"베팅 결과 확인 중 오류 발생: {e}", exc_info=True)
            return False
        

    def place_bet(self, bet_type):
        """
        베팅 타입(P 또는 B)에 따라 적절한 베팅 영역을 클릭합니다.
        중복 클릭 방지를 위해 베팅 상태를 기록합니다.
        
        Args:
            bet_type (str): 'P'(플레이어) 또는 'B'(뱅커)
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 자동 매매 활성화 상태 확인
            if not self.is_trading_active:
                self.logger.info("자동 매매가 활성화되지 않았습니다.")
                return False
            
            # 이미 베팅했는지 확인 (중복 베팅 방지)
            if self.has_bet_current_round:
                self.logger.info("이미 현재 라운드에 베팅했습니다.")
                return False
            
            # iframe으로 전환
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            
            # 베팅 대상 선택
            if bet_type == 'P':
                # Player 영역 찾기 및 클릭
                selector = "div.spot--5ad7f[data-betspot-destination='Player']"
                self.logger.info(f"Player 베팅 영역 클릭 시도: {selector}")
            elif bet_type == 'B':
                # Banker 영역 찾기 및 클릭
                selector = "div.spot--5ad7f[data-betspot-destination='Banker']"
                self.logger.info(f"Banker 베팅 영역 클릭 시도: {selector}")
            else:
                self.logger.error(f"잘못된 베팅 타입: {bet_type}")
                return False
            
            # 요소 찾기
            bet_element = WebDriverWait(self.devtools.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            
            # 요소가 활성화되어 있는지 확인
            is_active = 'active--dc7b3' in bet_element.get_attribute('class')
            if is_active:
                self.logger.info(f"이미 {bet_type} 영역이 활성화되어 있습니다.")
            else:
                # 클릭
                bet_element.click()
                self.logger.info(f"{bet_type} 영역 클릭 완료!")
            
            # 베팅 상태 기록 (중복 베팅 방지)
            self.has_bet_current_round = True
            
            # UI 업데이트
            self.main_window.update_betting_status(
                room_name=f"{self.current_room_name} (게임 수: {self.game_count}, 베팅: {bet_type})"
            )
            
            return True
        
        except Exception as e:
            # 오류 로깅
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            return False

    def close_room(self):
        """현재 열린 방을 종료"""
        try:
            # iframe 내부로 이동하여 종료 버튼 찾기
            self.devtools.driver.switch_to.default_content()
            iframe = self.devtools.driver.find_element(By.CSS_SELECTOR, "iframe")
            self.devtools.driver.switch_to.frame(iframe)
            self.logger.info("iframe 내부에서 종료 버튼 탐색 중...")

            # 종료 버튼 찾기 및 클릭
            close_button = WebDriverWait(self.devtools.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-role='close-button']"))
            )
            close_button.click()
            self.logger.info("방 종료 버튼 클릭 완료!")

            # 다시 메인 프레임으로 전환
            self.devtools.driver.switch_to.default_content()

        except Exception as e:
            # 오류 로깅
            self.logger.error(f"방 종료 실패: {e}", exc_info=True)

    def run_auto_trading(self):
        """자동 매매 루프"""
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 비활성화되어 있습니다.")
                return
                        
            self.logger.info("자동 매매 진행 중...")
            
            # 초기 게임 분석
            self.analyze_current_game()
            
            # 게임 모니터링 루프 설정 (게임이 약 10초 간격으로 빠르게 진행됨)
            monitoring_interval = 2  # 2초마다 체크하여 변화 감지
            self.main_window.set_remaining_time(0, 0, monitoring_interval)

        except Exception as e:
            # 오류 로깅
            self.logger.error(f"자동 매매 실행 중 치명적 오류 발생: {e}", exc_info=True)
            
            # 자동 매매 중지
            self.stop_trading()
            
            # 사용자에게 오류 메시지 표시
            QMessageBox.critical(
                self.main_window, 
                "자동 매매 오류", 
                f"자동 매매 중 심각한 오류가 발생했습니다.\n자동 매매가 중지됩니다.\n오류: {str(e)}"
            )

    def stop_trading(self):
        """자동 매매 중지"""
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 이미 중지된 상태입니다.")
                return
                
            self.logger.info("자동 매매 중지 중...")
            
            self.is_trading_active = False
            
            # 타이머 중지
            self.main_window.timer.stop()
            
            # 메시지 표시
            QMessageBox.information(self.main_window, "알림", "자동 매매가 중지되었습니다.")

        except Exception as e:
            # 오류 로깅
            self.logger.error(f"자동 매매 중지 중 오류 발생: {e}", exc_info=True)
            
            # 강제 중지 시도
            self.is_trading_active = False
            if hasattr(self.main_window, 'timer'):
                self.main_window.timer.stop()

            # 사용자에게 오류 메시지 표시
            QMessageBox.warning(
                self.main_window, 
                "중지 오류", 
                f"자동 매매 중지 중 문제가 발생했습니다.\n수동으로 중지되었습니다.\n오류: {str(e)}"
            )

# 사용을 위해 로깅 설정 추가
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 콘솔 출력
        # 필요하다면 파일 로깅 추가 가능
        # logging.FileHandler('trading_manager.log', encoding='utf-8')
    ]
)