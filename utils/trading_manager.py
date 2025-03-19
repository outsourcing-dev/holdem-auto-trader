# utils/trading_manager.py
import time
import logging
import os
from PyQt6.QtWidgets import QMessageBox
from services.room_entry_service import RoomEntryService
from services.excel_trading_service import ExcelTradingService
from services.betting_service import BettingService
from services.game_monitoring_service import GameMonitoringService
from services.balance_service import BalanceService
from services.martin_service import MartinBettingService
from utils.settings_manager import SettingsManager
from utils.trading_manager_helpers import TradingManagerHelpers

class TradingManager:
    # utils/trading_manager.py의 __init__ 메서드 수정 부분
    def __init__(self, main_window, logger=None):
        """TradingManager 초기화"""
        # 로거 설정
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # 기본 속성 초기화
        self.main_window = main_window
        self.devtools = main_window.devtools
        self.room_manager = main_window.room_manager
        self.settings_manager = SettingsManager()
        
        # 상태 관리 속성
        self.is_trading_active = False
        self.current_room_name = ""
        self.game_count = 0
        self.result_count = 0
        self.current_pick = None
        self.should_move_to_next_room = False
        self.processed_rounds = set()

        # 서비스 클래스 초기화
        self._init_services()
        
        # 헬퍼 클래스들 초기화 - 모듈 임포트
        from utils.trading_manager_helpers import TradingManagerHelpers
        from utils.trading_manager_bet import TradingManagerBet
        from utils.trading_manager_game import TradingManagerGame
        
        self.helpers = TradingManagerHelpers(self)
        self.bet_helper = TradingManagerBet(self)
        self.game_helper = TradingManagerGame(self)
        
    def _init_services(self):
        """서비스 객체들을 초기화"""
        try:
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
            
            self.martin_service = MartinBettingService(
                main_window=self.main_window,
                logger=self.logger
            )
        except Exception as e:
            self.logger.error(f"서비스 초기화 중 오류 발생: {e}", exc_info=True)
    
    def start_trading(self):
        """자동 매매 시작"""
        try:
            # 사전 검증
            if not self.helpers.validate_trading_prerequisites():
                return

            # 사용자 확인 및 라이센스 검증
            if not self.helpers.verify_license():
                return
                
            # 설정 초기화
            self.helpers.init_trading_settings()
            
            # 브라우저 및 카지노 로비 확인
            if not self.helpers.setup_browser_and_check_balance():
                return

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info("자동 매매 시작!")
            
            # UI 업데이트
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(True)
            
            # 목표 금액 체크
            balance = self.main_window.current_amount
            if self.balance_service.check_target_amount(balance):
                self.logger.info("목표 금액에 이미 도달")
                return
            
            # 방문 순서 초기화 및 첫 방 입장
            self.game_helper.enter_first_room()

        except Exception as e:
            self.logger.error(f"자동 매매 시작 오류: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window, 
                "자동 매매 오류", 
                f"자동 매매를 시작할 수 없습니다.\n오류: {str(e)}"
            )
            
    def analyze_current_game(self):
        """현재 게임 상태를 분석하여 게임 수와 결과를 확인"""
        try:
            # 방 이동 필요시 처리
            if self.should_move_to_next_room:
                # 마지막 베팅 정보 확인
                last_bet = self.betting_service.get_last_bet()
                
                # 베팅을 했고 결과가 없으면 아직 기다려야 함
                if last_bet and self.betting_service.has_bet_current_round:
                    # 베팅 완료 시간 확인
                    if hasattr(self.betting_service, 'last_bet_time'):
                        elapsed = time.time() - self.betting_service.last_bet_time
                        # 최소 10초는 결과를 기다림
                        if elapsed < 8.0:
                            self.logger.info(f"베팅 후 {elapsed:.1f}초 경과, 결과 기다리는 중...")
                            self.main_window.set_remaining_time(0, 0, 2)
                            return
                
                self.logger.info("방 이동 실행")
                self.should_move_to_next_room = False
                self.change_room()
                return
                        
            # 게임 상태 가져오기
            previous_game_count = self.game_count
            game_state = self.game_monitoring_service.get_current_game_state(log_always=True)
            
            if not game_state:
                self.logger.error("게임 상태를 가져올 수 없습니다.")
                self.main_window.set_remaining_time(0, 0, 2)
                return
            
            # 게임 카운트 및 변화 확인
            current_game_count = game_state.get('round', 0)
            latest_result = game_state.get('latest_result')
            
            # 게임 상태 변화 로깅
            if current_game_count != previous_game_count:
                self.logger.info(f"게임 카운트 변경: {previous_game_count} -> {current_game_count}")
            
            # 엑셀 처리 및 PICK 값 확인
            result = self.excel_trading_service.process_game_results(
                game_state, 
                self.game_count, 
                self.current_room_name
            )

            # 결과 처리
            if result[0] is not None:
                self.game_helper.process_excel_result(result, game_state, previous_game_count)
            
            # 무승부(T) 결과 시 베팅 시도
            self.game_helper.handle_tie_result(latest_result, game_state)
            
            # 다음 분석 간격 설정
            self.main_window.set_remaining_time(0, 0, 2)
                        
        except Exception as e:
            self.logger.error(f"게임 상태 분석 오류: {e}", exc_info=True)
            self.main_window.set_remaining_time(0, 0, 2)
            
    def run_auto_trading(self):
        """자동 매매 루프"""
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 비활성화되어 있습니다.")
                return
                
            self.logger.info("자동 매매 진행 중...")
            
            # 초기 게임 분석
            self.analyze_current_game()
            
            # 게임 모니터링 루프 설정
            monitoring_interval = 2  # 2초마다 체크
            self.main_window.set_remaining_time(0, 0, monitoring_interval)

        except Exception as e:
            self.logger.error(f"자동 매매 실행 중 오류 발생: {e}", exc_info=True)
            self.stop_trading()
            
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
            
            # 자동 매매 비활성화 상태 설정
            self.is_trading_active = False
            
            # 방 이동 플래그 초기화
            self.should_move_to_next_room = False
            
            # 타이머 중지
            if hasattr(self.main_window, 'timer') and self.main_window.timer.isActive():
                self.main_window.timer.stop()
                self.logger.info("타이머 중지 완료")
            
            # 베팅 상태 초기화
            if hasattr(self, 'betting_service'):
                self.betting_service.reset_betting_state()
            
            # 마틴 서비스 초기화
            if hasattr(self, 'martin_service'):
                self.martin_service.reset()
            
            # 버튼 상태 업데이트
            self.main_window.start_button.setEnabled(True)
            self.main_window.stop_button.setEnabled(False)
            
            # 현재 게임방에서 나가기 시도
            self.game_helper.exit_current_game_room()

            # 메시지 표시
            QMessageBox.information(self.main_window, "알림", "자동 매매가 중지되었습니다.")

        except Exception as e:
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

            QMessageBox.warning(
                self.main_window, 
                "중지 오류", 
                f"자동 매매 중지 중 문제가 발생했습니다.\n수동으로 중지되었습니다."
            )

    def change_room(self):
        """현재 방을 나가고 새로운 방으로 이동"""
        try:
            self.logger.info("방 이동 준비 중...")
            if self.current_room_name:
                self.room_manager.mark_room_visited(self.current_room_name)
            
            # 방 이동 플래그 초기화
            self.should_move_to_next_room = False
            
            # 현재 방 닫기 시도
            room_closed = self.game_monitoring_service.close_current_room()
            if not room_closed:
                self.logger.warning("현재 방을 닫는데 실패했습니다. 계속 진행합니다.")
            
            # Excel 파일 초기화
            try:
                self.logger.info("Excel 파일 초기화 중...")
                self.excel_trading_service.excel_manager.initialize_excel()
            except Exception as e:
                self.logger.error(f"Excel 파일 초기화 오류: {e}")
            
            # 상태 초기화
            self.game_helper.reset_room_state()
            
            # 새 방 입장
            new_room_name = self.room_entry_service.enter_room()
            
            # 방 입장 실패 시 처리
            if not new_room_name:
                return self.game_helper.handle_room_entry_failure()

            
            # 방 입장 성공 시 처리
            return self.game_helper.handle_successful_room_entry(new_room_name)

        except Exception as e:
            self.logger.error(f"방 이동 중 오류 발생: {e}", exc_info=True)
            QMessageBox.warning(self.main_window, "경고", f"방 이동 실패")
            return False