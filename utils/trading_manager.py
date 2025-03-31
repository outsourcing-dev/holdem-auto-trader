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
from utils.analysis_thread import GameAnalysisThread
from PyQt6.QtWidgets import QApplication  # 추가된 import

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
            # 브라우저 드라이버 확인 - 메시지 표시 없이 조용히 종료
            if not self.devtools.driver:
                # 메시지 대화상자 없이 그냥 종료
                print("[INFO] 브라우저가 실행되지 않았습니다. 자동 매매를 시작하지 않습니다.")
                return
                
            # 시작 전 설정 새로고침
            self.refresh_settings()
            
            # 목표 금액 도달 플래그 초기화
            if hasattr(self.balance_service, '_target_amount_reached'):
                del self.balance_service._target_amount_reached
                self.logger.info("목표 금액 도달 플래그 초기화")
            
            # stop_all_processes 플래그 초기화
            self.stop_all_processes = False
            
            # 사전 검증
            if not self.helpers.validate_trading_prerequisites():
                return

            # 사용자 확인 및 라이센스 검증
            if not self.helpers.verify_license():
                return
                    
            # 설정 초기화
            self.helpers.init_trading_settings()
            
            # 창 개수 확인 - 목표 금액 달성 후 2번 창이 닫혔을 수 있으므로 다시 확인
            window_handles = self.devtools.driver.window_handles
            
            # 1번 창만 있는 경우 (카지노 창이 닫힌 경우) 카지노 재접속 필요 알림
            if len(window_handles) < 2:
                QMessageBox.information(
                    self.main_window, 
                    "카지노 접속 필요", 
                    "카지노 창이 닫혀있습니다. 사이트 버튼을 눌러 카지노에 다시 접속해주세요."
                )
                return
            
            # 브라우저 및 카지노 로비 확인
            if not self.helpers.setup_browser_and_check_balance():
                return

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info("자동 매매 시작!")
            
            # UI 업데이트 - 시작 버튼 비활성화, 중지 버튼은 여전히 비활성화 (방 입장 전까지)
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(False)
            # 스타일 강제 업데이트 추가
            self.main_window.update_button_styles()
            QApplication.processEvents()  # 이벤트 처리 강제
            
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
            
    # 2. 클래스 내에 새로운 analyze_current_game 메서드 추가 (기존 메서드 대체)
    def analyze_current_game(self):
        """현재 게임 상태를 분석하여 게임 수와 결과를 확인 (멀티스레드 구현 - 동기화 문제 수정)"""
        try:
                    # 중지 플래그 확인 (가장 먼저 확인)
            if hasattr(self, 'stop_all_processes') and self.stop_all_processes:
                self.logger.info("중지 명령으로 인해 게임 분석을 중단합니다.")
                return
                
            # 목표 금액 도달 확인도 추가
            if hasattr(self.balance_service, '_target_amount_reached') and self.balance_service._target_amount_reached:
                self.logger.info("목표 금액 도달로 인해 게임 분석을 중단합니다.")
                return

            # 활성화 상태가 아니면 분석 시작하지 않음
            if not self.is_trading_active:
                self.logger.info("자동 매매가 비활성화되어 게임 분석을 시작하지 않습니다.")
                return

            # 이미 실행 중인 분석 스레드가 있는지 확인
            if hasattr(self, '_analysis_thread') and self._analysis_thread.isRunning():
                self.logger.info("이전 분석 스레드가 아직 실행 중입니다.")
                return
                
            # 분석 스레드 생성
            self._analysis_thread = GameAnalysisThread(self)
            
            # 신호 연결
            self._analysis_thread.analysis_complete.connect(self._handle_analysis_result)
            self._analysis_thread.analysis_error.connect(self._handle_analysis_error)
            self._analysis_thread.room_change_needed.connect(self._handle_room_change)
            
            # 스레드 시작
            # self.logger.info("게임 분석 스레드 시작")
            self._analysis_thread.start()
            # 중지 버튼 활성화 (스레드 시작 후)
            # self.main_window.stop_button.setEnabled(True)
            self.main_window.update_button_styles()
            # self.logger.info("게임 분석 스레드 시작 후 중지 버튼 활성화")
        
        except Exception as e:
            self.logger.error(f"게임 분석 스레드 시작 오류: {e}", exc_info=True)
            self.main_window.set_remaining_time(0, 0, 2)

    def _handle_analysis_result(self, result):
        """분석 결과 처리 핸들러"""
        try:
            # 목표 금액 도달 확인 - 이미 도달했으면 처리 중단
            if hasattr(self.balance_service, '_target_amount_reached') and self.balance_service._target_amount_reached:
                self.logger.info("목표 금액 도달이 감지되어 분석 결과를 처리하지 않습니다.")
                return
                
            game_state = result['game_state']
            previous_game_count = result['previous_game_count']
            
            # 게임 카운트 변화 로깅
            current_game_count = game_state.get('round', 0)
            # ✅ 게임 수 역행 감지
            if current_game_count < previous_game_count and previous_game_count >= 10:
                self.logger.warning(f"[❗게임 수 역행 감지] 이전: {previous_game_count} → 현재: {current_game_count} → 방 이동 시도")
                self.change_room()
                return

            # ✅ 결과 없음 감지용 카운터
            if not hasattr(self, 'no_result_counter'):
                self.no_result_counter = 0

            if current_game_count == previous_game_count:
                self.no_result_counter += 1
            else:
                self.no_result_counter = 0  # 게임 수 바뀌면 초기화

            if self.no_result_counter >= 20:
                self.logger.warning(f"[⚠️ 결과 없음 누적] 25회 이상 동일한 게임 수 → 방 이동")
                self.no_result_counter = 0
                self.change_room()
                return

            latest_result = game_state.get('latest_result')
                        
            # 첫 입장 시 방 정보 출력
            if previous_game_count == 0 and current_game_count > 0:
                display_room_name = self.current_room_name.split('\n')[0] if '\n' in self.current_room_name else self.current_room_name
                self.logger.info(f"방 '{display_room_name}'의 현재 게임 수: {current_game_count}")
        
            # Excel 처리는 메인 스레드에서 수행
            excel_result = self.excel_trading_service.process_game_results(
                game_state, 
                self.game_count, 
                self.current_room_name
            )
            
            # 결과 처리
            if excel_result[0] is not None:
                self.game_helper.process_excel_result(excel_result, game_state, previous_game_count)
            
            # 무승부(T) 결과 시 베팅 시도
            self.game_helper.handle_tie_result(latest_result, game_state)
            
            # 방 이동 판단 (60판 도달 or 초기화 감지 등)
            if self.should_move_to_next_room and not self.betting_service.has_bet_current_round:
                self.logger.info("방 이동 조건 충족 - change_room 실행")
                self.change_room()
                return

        except Exception as e:
            self.logger.error(f"분석 결과 처리 오류: {e}", exc_info=True)
        finally:
            # 자동 매매가 여전히 활성화된 경우에만 다음 분석 예약
            if self.is_trading_active:
                # 목표 금액에 도달했는지 다시 확인
                if hasattr(self.balance_service, '_target_amount_reached') and self.balance_service._target_amount_reached:
                    self.logger.info("목표 금액 도달 확인됨: 다음 분석을 예약하지 않습니다.")
                    return
                    
                # 다음 분석 간격 설정
                self.main_window.set_remaining_time(0, 0, 2)
            else:
                self.logger.info("자동 매매 비활성화됨: 다음 분석을 예약하지 않습니다.")
                
    def _handle_analysis_error(self, error_msg):
        """분석 오류 처리 핸들러"""
        self.logger.error(f"분석 스레드 오류: {error_msg}")
        self.main_window.set_remaining_time(0, 0, 2)  # 다음 시도 스케줄링

    def _handle_room_change(self):
        """방 이동 요청 처리 핸들러 - 중지 상태 확인 추가"""
        # 중요: 중지 명령이 내려진 경우 방 이동 처리하지 않음
        if hasattr(self, 'stop_all_processes') and self.stop_all_processes:
            self.logger.info("중지 명령이 활성화되어 방 이동 요청을 무시합니다.")
            return
            
        # 자동 매매가 비활성화된 경우에도 방 이동 처리하지 않음
        if not self.is_trading_active:
            self.logger.info("자동 매매가 비활성화되어 방 이동 요청을 무시합니다.")
            return
            
        self.logger.info("스레드에서 방 이동 요청 수신")
        # self.should_move_to_next_room = False  # 플래그 초기화
        self.change_room()  # 방 이동 프로세스 시작
        
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
        """자동 매매 중지 - 스레드 안전하게 종료"""
        from PyQt6.QtWidgets import QApplication
        try:
            if not self.is_trading_active:
                self.logger.info("자동 매매가 이미 중지된 상태입니다.")
                return
                
            self.logger.info("자동 매매 중지 중...")
            
            # 중요: 먼저 중지 플래그 설정 - 모든 진행 중인 작업이 이를 확인해야 함
            self.stop_all_processes = True
            
            # 실행 중인 모든 타이머 이벤트 취소
            if hasattr(self.main_window, 'timer') and self.main_window.timer.isActive():
                self.main_window.timer.stop()
                # QApplication의 이벤트 큐 처리 강제
                QApplication.processEvents()
                self.logger.info("타이머 중지 및 이벤트 큐 처리 완료")
            
            # 1초 대기하여 진행 중인 작업들이 중지 플래그를 확인할 시간 제공
            time.sleep(1)
            
            # 그 다음 trading_active 플래그 비활성화
            self.is_trading_active = False
            
            # 방 이동 플래그 초기화
            # self.should_move_to_next_room = False
            
            # 타이머 중지 - 분석 스레드 예약 중단
            if hasattr(self.main_window, 'timer') and self.main_window.timer.isActive():
                self.main_window.timer.stop()
                self.logger.info("타이머 중지 완료")
            
            # 진행 중인 분석 스레드 중지
            if hasattr(self, '_analysis_thread') and hasattr(self._analysis_thread, 'isRunning'):
                if self._analysis_thread.isRunning():
                    try:
                        self.logger.info("진행 중인 분석 스레드 강제 종료")
                        self._analysis_thread.terminate()  # 강제 종료
                        self._analysis_thread.wait(1000)  # 최대 1초 대기
                    except Exception as e:
                        self.logger.warning(f"분석 스레드 종료 중 오류: {e}")
                        
            # 진행 중인 방 입장 스레드 중지
            if hasattr(self.room_entry_service, 'entry_thread') and self.room_entry_service.entry_thread:
                if self.room_entry_service.entry_thread.isRunning():
                    self.logger.info("진행 중인 방 입장 스레드 강제 종료")
                    try:
                        self.room_entry_service.entry_thread.terminate()  # 강제 종료
                        self.room_entry_service.entry_thread.wait(1000)  # 최대 1초 대기
                    except Exception as e:
                        self.logger.warning(f"방 입장 스레드 종료 중 오류: {e}")
            
            # 베팅 상태 초기화
            if hasattr(self, 'betting_service'):
                self.betting_service.reset_betting_state()
            
            # 마틴 서비스 초기화
            if hasattr(self, 'martin_service'):
                self.martin_service.reset()
            
            # 게임 상태 완전 초기화
            self.game_count = 0
            self.result_count = 0
            self.current_pick = None
            self.processed_rounds = set()  # 처리된 라운드 기록 초기화
            
            # 게임 모니터링 서비스 카운트 초기화
            if hasattr(self, 'game_monitoring_service'):
                if hasattr(self.game_monitoring_service, 'last_detected_count'):
                    self.game_monitoring_service.last_detected_count = 0
                if hasattr(self.game_monitoring_service, 'game_detector'):
                    from modules.game_detector import GameDetector
                    self.game_monitoring_service.game_detector = GameDetector()  # 새로운 인스턴스로 교체
            
            # 중요: 이전에 예약된 타이머 이벤트를 모두 취소 (추가)
            if hasattr(self.main_window, 'timer'):
                if self.main_window.timer.isActive():
                    self.main_window.timer.stop()
                # 이벤트 큐 처리
                QApplication.processEvents()
            
            # 버튼 상태 업데이트
            self.main_window.start_button.setEnabled(True)
            self.main_window.stop_button.setEnabled(False)  # 중지 버튼 항상 비활성화
            
            # 현재 게임방에서 나가기 시도
            self.logger.info("현재 방에서 나가기만 수행")
            self.game_helper.exit_current_game_room()

            # 목표 금액에 도달했는지 확인하여 메시지 표시 결정
            target_reached = hasattr(self.balance_service, '_target_amount_reached') and self.balance_service._target_amount_reached
            
            # 목표 금액 도달로 인한 중지가 아닌 경우에만 메시지 표시
            if not target_reached:
                QMessageBox.information(self.main_window, "알림", "자동 매매가 중지되었습니다.")

        except Exception as e:
            self.logger.error(f"자동 매매 중지 중 오류 발생: {e}", exc_info=True)
            
            # 강제 중지 시도
            self.is_trading_active = False
            if hasattr(self.main_window, 'timer'):
                self.main_window.timer.stop()
                
            # 게임 카운트 강제 초기화
            self.game_count = 0
            
            # 버튼 상태 업데이트 시도
            try:
                self.main_window.start_button.setEnabled(True)
                self.main_window.stop_button.setEnabled(False)  # 중지 버튼 항상 비활성화
            except:
                pass

            QMessageBox.warning(
                self.main_window, 
                "중지 오류", 
                f"자동 매매 중지 중 문제가 발생했습니다.\n수동으로 중지되었습니다."
            )        
            
# utils/trading_manager.py에서 change_room 메서드 수정
    def change_room(self):
        """현재 방을 나가고 새로운 방으로 이동"""
        try:
            # 중요: stop_all_processes 플래그 확인 - 도중에 중지 명령이 내려졌는지 확인
            if hasattr(self, 'stop_all_processes') and self.stop_all_processes:
                self.logger.info("중지 명령으로 인해 방 이동을 중단합니다.")
                return False
                
            # 목표 금액 도달 확인도 추가
            if hasattr(self.balance_service, '_target_amount_reached') and self.balance_service._target_amount_reached:
                self.logger.info("목표 금액 도달로 인해 방 이동을 중단합니다.")
                return False
                
            # 자동 매매가 활성화된 상태인지 다시 한번 확인
            if not self.is_trading_active:
                self.logger.info("자동 매매 비활성화 상태로 방 이동 중단")
                return False

            self.logger.info("방 이동 준비 중...")
            
            # 방 이동 시 중지 버튼 비활성화 (추가된 부분 - 방 이동 중에는 비활성화)
            self.main_window.stop_button.setEnabled(False)
            self.main_window.update_button_styles()
            self.logger.info("방 이동 중: 중지 버튼 비활성화됨")
            
            # 방 이동 플래그 설정 - room_log_widget에 방 변경 알림
            if hasattr(self.main_window, 'room_log_widget'):
                self.main_window.room_log_widget.has_changed_room = True
                self.logger.info("방 이동 플래그 설정됨")
            
            if self.current_room_name:
                self.room_manager.mark_room_visited(self.current_room_name)
            
            # 방 이동 플래그 초기화
            # self.should_move_to_next_room = False
            
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
            # 실패 시 중지 버튼 비활성화 (추가된 부분)
            self.main_window.stop_button.setEnabled(False)
            # 스타일 강제 업데이트 추가
            self.main_window.update_button_styles()
            self.logger.info("방 이동 실패: 중지 버튼 비활성화 상태 유지")
            QMessageBox.warning(self.main_window, "경고", f"방 이동 실패")
            return False
        
    # utils/trading_manager.py에 설정 업데이트 메서드 추가
    def update_settings(self):
        """설정이 변경된 경우 호출될 설정 업데이트 메서드"""
        try:
            # 설정 매니저 갱신 - 파일에서 다시 로드
            self.settings_manager = SettingsManager()
            self.settings_manager.load_settings()
            
            # 각 서비스의 설정 매니저도 갱신
            if hasattr(self, 'balance_service'):
                self.balance_service.settings_manager = self.settings_manager
            
            # 마틴 서비스의 설정 업데이트
            if hasattr(self, 'martin_service'):
                # 설정 매니저 갱신
                self.martin_service.settings_manager = self.settings_manager
                # 마틴 설정 업데이트 메서드 호출
                if hasattr(self.martin_service, 'update_settings'):
                    self.martin_service.update_settings()
            
            # 설정 업데이트 로깅
            martin_count, martin_amounts = self.settings_manager.get_martin_settings()
            target_amount = self.settings_manager.get_target_amount()
            double_half_start, double_half_stop = self.settings_manager.get_double_half_settings()
            
            self.logger.info(f"설정 업데이트 완료 - 마틴 설정: {martin_count}단계, {martin_amounts}")
            self.logger.info(f"목표 금액: {target_amount:,}원, Double & Half: 시작={double_half_start}, 중지={double_half_stop}")
            
            return True
        except Exception as e:
            self.logger.error(f"설정 업데이트 중 오류 발생: {e}")
            return False
        
    def refresh_settings(self):
        """설정을 파일에서 새로 로드하여 적용합니다."""
        try:
            # 설정 매니저 재생성 (항상 파일에서 다시 로드)
            self.settings_manager = SettingsManager()
            
            # 각 서비스의 설정 매니저도 갱신
            services = ['balance_service', 'martin_service', 'room_entry_service', 'excel_trading_service']
            for service_name in services:
                if hasattr(self, service_name):
                    service = getattr(self, service_name)
                    if hasattr(service, 'settings_manager'):
                        # 기존 객체가 있으면 업데이트
                        service.settings_manager = self.settings_manager
            
            # 마틴 서비스는 특별 처리 (update_settings 메서드 호출)
            if hasattr(self, 'martin_service') and hasattr(self.martin_service, 'update_settings'):
                self.martin_service.update_settings()
                
            # 설정 로그 출력
            martin_count, martin_amounts = self.settings_manager.get_martin_settings()
            site1, site2, site3 = self.settings_manager.get_sites()
            
            self.logger.info(f"설정 새로고침 완료 - 마틴 설정: {martin_count}단계, {martin_amounts}")
            self.logger.info(f"사이트 설정: site1={site1}, site2={site2}, site3={site3}")
            
            return True
        except Exception as e:
            self.logger.error(f"설정 새로고침 중 오류 발생: {e}")
            return False
        
    @property
    def should_move_to_next_room(self):
        """
        현재 방을 이동해야 하는 조건을 판단합니다.
        """
        return self.game_count >= 60