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
from services.betting_service import BettingService
from services.game_monitoring_service import GameMonitoringService
from services.balance_service import BalanceService
from services.martin_service import MartinBettingService

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
        self.result_count = 0
        self.current_pick = None  # 현재 베팅 타입 저장 변수 추가
        self.should_move_to_next_room = False  # 방 이동 예약 플래그 추가

        # 서비스 클래스 초기화
        self.betting_service = BettingService(
            devtools=self.devtools,
            main_window=self.main_window,
            logger=self.logger
        )
        
        self.game_monitoring_service = GameMonitoringService(
            devtools=self.devtools,
            main_window=self.main_window,
            logger=self.logger
        )
        
        self.balance_service = BalanceService(
            devtools=self.devtools,
            main_window=self.main_window,
            logger=self.logger
        )
        
        self.room_entry_service = RoomEntryService(
            devtools=self.devtools, 
            main_window=self.main_window, 
            room_manager=self.room_manager, 
            logger=self.logger
        )

        self.excel_trading_service = ExcelTradingService(
            main_window=self.main_window, 
            logger=self.logger
        )
        
        # 마틴 베팅 서비스 추가
        self.martin_service = MartinBettingService(
            main_window=self.main_window,
            logger=self.logger
        )
        
        # 게임 컨트롤러
        self.game_controller = None

    # utils/trading_manager.py의 start_trading 함수 수정 (간소화 버전)
    def start_trading(self):
        """자동 매매 시작 로직"""
        try:
            # 사전 검증
            if not self._validate_trading_prerequisites():
                return

            # 방문 순서 초기화 및 생성
            self.room_manager.generate_visit_order()
            
            # 방 선택 및 입장
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

            balance = self.balance_service.get_iframe_balance()

            if balance is None:
                QMessageBox.warning(self.main_window, "오류", "게임 내 잔액 정보를 찾을 수 없습니다.")
                return

            # 사용자 이름은 기본값 사용
            username = self.main_window.username or "사용자"
                    
            # UI에 잔액 및 사용자 정보 업데이트
            self.balance_service.update_balance_and_user_data(balance, username)

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info("자동 매매 시작!")

            # 버튼 상태 업데이트
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(True)
            
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
    
    # 2. analyze_current_game 메서드 수정
    def analyze_current_game(self):
        """현재 게임 상태를 분석하여 게임 수와 결과를 확인"""
        try:
            # 1. 방 이동 플래그 확인 - 항상 가장 먼저 체크
            if self.should_move_to_next_room:
                self.logger.info("방 이동 플래그가 설정되어 있어 방 이동을 실행합니다.")
                self.should_move_to_next_room = False  # 플래그 초기화
                self.change_room()
                return  # 방 이동 후 첫 분석은 건너뛰기
                
            # 2. 게임 상태 가져오기
            previous_game_count = self.game_count
            game_state = self.game_monitoring_service.get_current_game_state(log_always=False)
            
            if not game_state:
                self.logger.error("게임 상태를 가져올 수 없습니다.")
                return
            
            # 3. 게임 카운트 및 변경 확인
            current_game_count = game_state.get('round', 0)
            
            if current_game_count != previous_game_count:
                self.logger.info(f"게임 카운트 변경: {previous_game_count} -> {current_game_count}")
                if previous_game_count == 0 and current_game_count > 0:
                    self.logger.info(f"방 {self.current_room_name}의 현재 게임 수: {current_game_count}")
            
            # 4. 엑셀 처리 및 PICK 값 확인
            result = self.excel_trading_service.process_game_results(
                game_state, 
                self.game_count, 
                self.current_room_name,
                log_on_change=True
            )

            # 5. 결과 처리 (last_column이 None이 아닌 경우에만)
            if result[0] is not None:
                last_column, new_game_count, recent_results, next_pick = result
                
                # 6. 새 게임 시작 시 이전 게임 결과 확인
                if new_game_count > self.game_count:
                    self._process_previous_game_result(game_state, new_game_count)
                    
                    # 7. PICK 값에 따른 베팅 실행 (방 이동 예정이 아닐 때만)
                    if not self.should_move_to_next_room and next_pick in ['P', 'B'] and not self.betting_service.has_bet_current_round:
                        self.main_window.update_betting_status(pick=next_pick)
                        self._place_bet(next_pick, new_game_count)

                    # 8. 게임 카운트 및 최근 결과 업데이트
                    self.game_count = new_game_count
                    self.recent_results = recent_results
            
            # 9. 2초마다 분석 수행
            self.main_window.set_remaining_time(0, 0, 2)
                
        except Exception as e:
            self.logger.error(f"게임 상태 분석 중 오류 발생: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            
    def _process_previous_game_result(self, game_state, new_game_count):
        """이전 게임 결과 처리 및 배팅 상태 초기화"""
        # 이전 베팅 정보 가져오기
        last_bet = self.betting_service.get_last_bet()
        
        # 이전 게임에 베팅했고, 그 베팅이 현재 라운드에 대한 것이었는지 확인
        if last_bet and last_bet['round'] == self.game_count:
            bet_type = last_bet['type']
            latest_result = game_state.get('latest_result')
            
            if bet_type in ['P', 'B'] and latest_result:
                self.logger.info(f"베팅 결과 확인 - 베팅: {bet_type}, 결과: {latest_result}")
                
                # 현재 마틴 단계 가져오기
                current_step = self.martin_service.current_step + 1  # 0부터 시작하므로 +1
                
                # 결과 판정
                is_tie = (latest_result == 'T')
                is_win = (not is_tie and bet_type == latest_result)
                
                # 승패 결과 텍스트
                if is_tie:
                    result_text = "무승부"
                    result_marker = "T"
                    result_status = "tie"
                elif is_win:
                    result_text = "적중"
                    result_marker = "O"
                    result_status = "win"
                else:
                    result_text = "실패"
                    result_marker = "X"
                    result_status = "lose"
                
                # 결과 카운트 증가
                self.result_count += 1
                
                # 1. 현재 방의 진행 테이블에 결과 표시 (BettingWidget)
                self.main_window.betting_widget.set_step_marker(current_step, result_marker)
                
                # 2. 방 로그 테이블에 결과 추가 (RoomLogWidget)
                self.main_window.room_log_widget.add_bet_result(
                    room_name=self.current_room_name,
                    is_win=is_win,
                    is_tie=is_tie
                )
                
                # 마틴 베팅 단계 업데이트
                self.martin_service.process_bet_result(result_status)
                
                # 현재 잔액 업데이트 (베팅 결과 확인 후)
                self.balance_service.update_balance_after_bet_result()
                
                # 방 이동이 필요한지 확인 (승리 시에만)
                if result_status == "win" and self.martin_service.should_change_room():
                    self.logger.info("배팅 성공으로 방 이동이 필요합니다.")
                    time.sleep(1)  # 1초 대기
                    self.should_move_to_next_room = True
        
        # 베팅 상태 초기화 (새 라운드 번호로)
        self.betting_service.reset_betting_state(new_round=new_game_count)
        self.logger.info(f"새로운 게임 시작: 베팅 상태 초기화 (게임 수: {new_game_count})")
        
        # UI 업데이트
        self.main_window.update_betting_status(
            room_name=f"{self.current_room_name} (게임 수: {new_game_count})",
            pick=self.current_pick
        )
        
    def _place_bet(self, pick_value, game_count):
        """베팅 실행"""
        # 마틴 서비스에서 현재 베팅 금액 가져오기
        bet_amount = self.martin_service.get_current_bet_amount()
        self.logger.info(f"마틴 단계 {self.martin_service.current_step + 1}/{self.martin_service.martin_count}: {bet_amount:,}원 베팅")
        
        # 베팅 전에 PICK 값 UI 업데이트
        self.main_window.update_betting_status(pick=pick_value)
        
        # 베팅 실행
        bet_success = self.betting_service.place_bet(
            pick_value, 
            self.current_room_name, 
            game_count, 
            self.is_trading_active
        )
        
        # 현재 베팅 타입 저장
        self.current_pick = pick_value
        
        # 베팅 성공 여부와 관계없이 PICK 값을 UI에 표시
        if not bet_success:
            self.logger.warning(f"베팅 실패했지만 PICK 값은 유지: {pick_value}")
            self.main_window.update_betting_status(pick=pick_value)
        
        return bet_success

         
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

    # utils/trading_manager.py의 stop_trading 메서드 수정
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
            
            # 버튼 상태 업데이트
            self.main_window.start_button.setEnabled(True)
            self.main_window.stop_button.setEnabled(False)
            
            # 메시지 표시
            QMessageBox.information(self.main_window, "알림", "자동 매매가 중지되었습니다.")

        except Exception as e:
            # 오류 로깅
            self.logger.error(f"자동 매매 중지 중 오류 발생: {e}", exc_info=True)
            
            # 강제 중지 시도
            self.is_trading_active = False
            if hasattr(self.main_window, 'timer'):
                self.main_window.timer.stop()
                
            # 버튼 상태 업데이트 시도
            try:
                self.main_window.start_button.setEnabled(True)
                self.main_window.stop_button.setEnabled(False)
            except:
                pass

            # 사용자에게 오류 메시지 표시
            QMessageBox.warning(
                self.main_window, 
                "중지 오류", 
                f"자동 매매 중지 중 문제가 발생했습니다.\n수동으로 중지되었습니다.\n오류: {str(e)}"
            )
            
    def change_room(self):
        """
        현재 방을 나가고 새로운 방으로 이동합니다.
        """
        try:
            self.logger.info("배팅 성공 후 방 이동 준비 중...")

            # 방 이동 플래그 초기화
            self.should_move_to_next_room = False
            
            # 현재 방 닫기
            if not self.game_monitoring_service.close_current_room():
                self.logger.error("현재 방을 닫는데 실패했습니다.")
                return False
            
            # 방 이동 전 상태 초기화
            self.game_count = 0
            self.result_count = 0
            self.current_pick = None
            self.betting_service.reset_betting_state()
            
            # 이 시점에서 카지노 로비 창으로 포커싱이 전환됨
            
            # 새 방 입장 (방문 큐에서 다음 방 선택)
            self.current_room_name = self.room_entry_service.enter_room()
            
            # 방 입장 실패 시 매매 중단
            if not self.current_room_name:
                self.stop_trading()
                QMessageBox.warning(self.main_window, "오류", "새 방 입장에 실패했습니다. 자동 매매를 중지합니다.")
                return False
            
            # UI 업데이트 - 진행 상황 초기화
            self.main_window.update_betting_status(
                room_name=self.current_room_name,
                pick=""
            )
            self.main_window.betting_widget.reset_step_markers()
            
            self.logger.info(f"새 방 '{self.current_room_name}'으로 이동 완료, 게임 카운트 초기화: {self.game_count}")
            return True
                
        except Exception as e:
            self.logger.error(f"방 이동 중 오류 발생: {e}", exc_info=True)
            QMessageBox.warning(self.main_window, "경고", f"방 이동 실패: {str(e)}")
            return False
        
# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)