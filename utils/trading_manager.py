# utils/trading_manager.py
import random
import time
import logging
import os
from PyQt6.QtWidgets import QMessageBox
from utils.game_controller import GameController
from services.room_entry_service import RoomEntryService
from services.excel_trading_service import ExcelTradingService
from services.betting_service import BettingService
from services.game_monitoring_service import GameMonitoringService
from services.balance_service import BalanceService
from services.martin_service import MartinBettingService
from utils.settings_manager import SettingsManager
from utils.target_amount_checker import TargetAmountChecker

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
        
        
        # 설정 매니저 추가
        self.settings_manager = SettingsManager()
        
        # 상태 관리 속성
        self.is_trading_active = False
        self.current_room_name = ""
        self.game_count = 0
        self.result_count = 0
        self.current_pick = None  # 현재 베팅 타입 저장 변수 추가
        self.should_move_to_next_room = False  # 방 이동 예약 플래그 추가
        self.target_checker = TargetAmountChecker(main_window)
        self.processed_rounds = set()  # 이미 처리한 라운드 ID 세트


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

    def _check_martin_balance(self, balance):
        """
        현재 잔고가 마틴 배팅을 하기에 충분한지 확인합니다.
        
        Args:
            balance (int): 현재 잔고
            
        Returns:
            bool: 마틴 배팅 가능 여부 (True: 가능, False: 불가능)
        """
        try:
            # 마틴 설정 가져오기 (최신 설정 사용)
            martin_count, martin_amounts = self.settings_manager.get_martin_settings()
            
            # 마틴 1단계(첫 번째 단계) 금액
            first_martin_amount = martin_amounts[0] if martin_amounts else 1000
            
            # 현재 잔액이 마틴 1단계 금액보다 적은지 확인
            if balance < first_martin_amount:
                self.logger.warning(f"현재 잔고({balance:,}원)가 마틴 1단계 금액({first_martin_amount:,}원)보다 적습니다.")
                
                # 적절한 메시지를 QMessageBox로 표시
                QMessageBox.warning(
                    self.main_window, 
                    "잔액 부족",
                    f"현재 잔고({balance:,}원)가 마틴 1단계 금액({first_martin_amount:,}원)보다 적습니다."
                )
                return False
            
            self.logger.info(f"마틴 배팅 가능: 현재 잔고 {balance:,}원, 마틴 1단계 금액: {first_martin_amount:,}원")
            return True
        
        except Exception as e:
            self.logger.error(f"마틴 잔고 확인 중 오류 발생: {e}", exc_info=True)
            return False  # 오류 발생 시 안전하게 False 반환
        
    def start_trading(self):
        """자동 매매 시작 로직"""
        try:
            # 사전 검증
            if not self._validate_trading_prerequisites():
                return

            # 중요: 설정을 강제로 다시 로드
            self.logger.info("[INFO] 자동 매매 시작 전 설정 강제 재로드")
            
            # 설정 매니저 새로 생성하여 파일에서 설정 다시 로드
            self.settings_manager = SettingsManager()
            if hasattr(self, 'balance_service') and hasattr(self.balance_service, 'settings_manager'):
                self.balance_service.settings_manager = SettingsManager()
                
                # 현재 목표 금액 로그 출력
                target_amount = self.balance_service.settings_manager.get_target_amount()
                self.logger.info(f"[INFO] 현재 설정된 목표 금액: {target_amount:,}원")

            # 마틴 서비스의 설정 매니저 갱신
            if hasattr(self, 'martin_service'):
                # 마틴 서비스 완전 초기화 - 중요 수정 사항: 매번 새로 시작할 때 마틴 단계 리셋
                self.martin_service.reset()
                
                self.martin_service.settings_manager = self.settings_manager
                self.martin_service.martin_count, self.martin_service.martin_amounts = self.martin_service.settings_manager.get_martin_settings()
                self.logger.info(f"[INFO] 마틴 설정 재로드 - 단계: {self.martin_service.martin_count}, 금액: {self.martin_service.martin_amounts}")
                self.logger.info(f"[INFO] 마틴 단계 초기화 완료 - 현재 단계: {self.martin_service.current_step} (0 = 1단계)")

            # 브라우저 실행 확인
            if not self.devtools.driver:
                self.devtools.start_browser()
                
            # 창 개수 확인
            window_handles = self.devtools.driver.window_handles
            if len(window_handles) < 2:
                QMessageBox.warning(self.main_window, "오류", "창 개수가 부족합니다. 최소 2개의 창이 필요합니다.")
                return

            # 중요 변경: 자동 매매 시작 전에 로비 창에서 잔액 가져오기
            # 카지노 로비 창(2번 창)으로 전환
            if len(window_handles) >= 2:
                self.devtools.driver.switch_to.window(window_handles[1])
                self.logger.info("카지노 로비 창으로 포커싱 전환")
            
            # 로비 iframe에서 잔액 가져오기
            balance = self.balance_service.get_lobby_balance()
            
            if balance is None:
                QMessageBox.warning(self.main_window, "오류", "로비에서 잔액 정보를 찾을 수 없습니다.")
                return

            # UI에 현재 잔액 표시 (이 부분을 마틴 검증 전으로 이동)
            self.main_window.reset_ui()  # UI 초기화
            self.main_window.update_user_data(
                username=self.main_window.username,
                start_amount=balance,
                current_amount=balance
            )

            # 마틴 배팅을 위한 잔고 충분한지 확인
            # (_check_martin_balance 메서드 내에서 이미 경고 메시지를 표시함)
            if not self._check_martin_balance(balance):
                return

            # 기존 잔액 및 UI 초기화
            self.main_window.reset_ui()
                    
            # 게임 컨트롤러 초기화
                    # 중요: os.environ에서 Excel 파일 경로를 가져와 전달
            excel_path = os.environ.get("AUTO_EXCEL_PATH")
            self.logger.info(f"GameController에 Excel 경로 전달: {excel_path}")
            self.game_controller = GameController(self.devtools.driver, excel_path)

            # 사용자 이름은 기본값 사용
            username = self.main_window.username
                    
            # 자동 매매 활성화 - 잔액 업데이트 전에 활성화하여 목표 금액 도달 시 중지 가능하도록 함
            self.is_trading_active = True
            self.logger.info("자동 매매 시작!")
            
            # 버튼 상태 업데이트
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(True)
            
            # UI에 잔액 및 사용자 정보 업데이트
            self.main_window.update_user_data(
                username=username,
                start_amount=balance,
                current_amount=balance
            )
            
            # 중요: 최초 입장 시 목표 금액 체크 추가
            if self.balance_service.check_target_amount(balance):
                self.logger.info("목표 금액에 이미 도달하여 자동 매매를 시작하지 않습니다.")
                return
            
            # 추가 검증: 자동 매매가 중지되었는지 확인
            if not self.is_trading_active:
                self.logger.info("목표 금액 도달로 자동 매매가 이미 중지되었습니다.")
                return

            # 방문 순서 초기화 및 생성
            self.room_manager.generate_visit_order()
            
            # 중요: 이전 게임 처리 기록 초기화
            self.processed_rounds = set()
            
            # 방 선택 및 입장
            self.current_room_name = self.room_entry_service.enter_room()
            
            # 방 입장에 실패한 경우
            if not self.current_room_name:
                self.stop_trading()
                return
            
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
                # 다음에 다시 시도하기 위해 2초 대기 설정
                self.main_window.set_remaining_time(0, 0, 2)
                return
            
            # 3. 게임 카운트 및 변경 확인
            current_game_count = game_state.get('round', 0)
            
            # 게임 상태 로깅
            if current_game_count != previous_game_count:
                self.logger.info(f"게임 카운트 변경: {previous_game_count} -> {current_game_count}")
                
                # 첫 입장 시 방 정보 출력
                if previous_game_count == 0 and current_game_count > 0:
                    display_room_name = self.current_room_name.split('\n')[0] if '\n' in self.current_room_name else self.current_room_name
                    self.logger.info(f"방 '{display_room_name}'의 현재 게임 수: {current_game_count}")
            
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

                        # 첫 입장 시 바로 베팅하지 않고 대기 (중요 변경 사항)
                        if previous_game_count > 0:  # 이미 한 번 이상 게임 카운트를 확인한 경우에만 베팅
                            self._place_bet(next_pick, new_game_count)
                        else:
                            self.logger.info(f"첫 입장 후 즉시 베팅 방지: 먼저 게임 상황 파악 중 (PICK: {next_pick})")
                            self.current_pick = next_pick  # PICK 값은 저장

                    # 8. 게임 카운트 및 최근 결과 업데이트
                    self.game_count = new_game_count
                    self.recent_results = recent_results
                
                # 9. 첫 입장 후 일정 시간 경과 시 베팅 (2-3초 후)
                elif previous_game_count == 0 and self.game_count > 0 and not self.betting_service.has_bet_current_round:
                    if hasattr(self, '_first_entry_time'):
                        elapsed = time.time() - self._first_entry_time
                        if elapsed > 3.0 and next_pick in ['P', 'B']:  # 3초 이상 지난 경우에만 베팅
                            self.logger.info(f"첫 입장 후 {elapsed:.1f}초 경과, 베팅 실행: {next_pick}")
                            self.current_pick = next_pick
                            self.main_window.update_betting_status(pick=next_pick)
                            self._place_bet(next_pick, self.game_count)
                            delattr(self, '_first_entry_time')  # 초기 타이머 제거
                    else:
                        # 첫 입장 시간 기록
                        self._first_entry_time = time.time()
                        self.logger.info(f"첫 입장 타이머 시작: PICK={next_pick}")
            
            # 추가: 현재 결과가 무승부(T)이고, 아직 배팅하지 않았으며, PICK 값이 있는 경우 베팅 시도
            latest_result = game_state.get('latest_result')
            if (latest_result == 'T' and 
                not self.betting_service.has_bet_current_round and 
                self.current_pick in ['P', 'B'] and
                not self.should_move_to_next_room and
                self.game_count > 0):
                
                self.logger.info(f"무승부(T) 감지, 이전 PICK 값({self.current_pick})으로 베팅 시도")
                self._place_bet(self.current_pick, self.game_count)
            
            # 10. 2초마다 분석 수행 (기본 간격)
            self.main_window.set_remaining_time(0, 0, 2)
                    
        except Exception as e:
            self.logger.error(f"게임 상태 분석 중 오류 발생: {e}")
            # 오류 발생 시에도 계속 모니터링하기 위해 타이머 설정
            self.main_window.set_remaining_time(0, 0, 2)
            
    def _process_previous_game_result(self, game_state, new_game_count):
        """이전 게임 결과 처리 및 배팅 상태 초기화"""
        # 이전 베팅 정보 가져오기
        last_bet = self.betting_service.get_last_bet()
        
        # 이전 게임에 베팅했고, 그 베팅이 현재 라운드에 대한 것이었는지 확인
        if last_bet and last_bet['round'] == self.game_count:
            bet_type = last_bet['type']
            latest_result = game_state.get('latest_result')
            
            self.logger.info(f"[결과검증] 라운드: {self.game_count}, 베팅: {bet_type}, 결과: {latest_result}")
            
            if bet_type in ['P', 'B'] and latest_result:
                # 결과 판정 - 더 명확하고 상세한 로깅 추가
                is_tie = (latest_result == 'T')
                # 베팅과 결과가 정확히 일치할 때만 승리로 처리
                is_win = (not is_tie and bet_type == latest_result)
                
                # 승패 결과 텍스트
                if is_tie:
                    result_text = "무승부"
                    result_marker = "T"
                    result_status = "tie"
                    self.betting_service.has_bet_current_round = False
                    self.logger.info(f"타이(T) 결과 감지: 현재 라운드({self.game_count})에 재베팅 가능하도록 상태 초기화")

                elif is_win:
                    result_text = "적중"
                    result_marker = "O"
                    result_status = "win"
                else:
                    result_text = "실패"
                    result_marker = "X"
                    result_status = "lose"
                
                # 전과정 상세 로깅 (디버깅용)
                self.logger.info(f"[결과과정] 베팅: {bet_type}, 결과: {latest_result}, 판정: {result_status}")
                
                # 특이 케이스(반대로 처리) 감지를 위한 추가 검증
                if (bet_type == 'P' and latest_result == 'P' and result_status != 'win') or \
                (bet_type == 'B' and latest_result == 'B' and result_status != 'win'):
                    self.logger.error(f"[심각] 판정 오류 감지! 동일 타입인데 패배로 처리: {bet_type}={latest_result}")
                    # 강제로 승리 처리
                    result_status = "win"
                    result_marker = "O"
                    result_text = "적중"
                    self.logger.info(f"[결과교정] 동일 타입 판정 오류 수정: {result_status}")
                
                # 결과 카운트 증가
                self.result_count += 1
                
                # 마틴 베팅 단계 업데이트 및 결과 위치 가져오기
                # 수정: 실제 배팅 결과에 해당하는 위치 값 가져오기
                current_step, consecutive_losses, result_position = self.martin_service.process_bet_result(
                    result_status, 
                    game_count=self.game_count
                )
                
                # 베팅 위젯에 결과 표시 - 실제 배팅 횟수 기준 위치 사용
                self.main_window.betting_widget.set_step_marker(result_position, result_marker)
                
                # 방 로그 위젯에 결과 추가
                self.main_window.room_log_widget.add_bet_result(
                    room_name=self.current_room_name,
                    is_win=is_win,
                    is_tie=is_tie
                )
                
                # 수정: 승패 여부에 따라 잔액 업데이트 (성공 시 지연)
                # 여러 방법으로 잔액 확인을 시도합니다.
                current_balance = None
                
                # 1. 가장 정확한 방법: balance_service의 update_balance_after_bet_result 메서드 사용
                current_balance = self.balance_service.update_balance_after_bet_result(is_win=is_win)
                
                # 2. 첫 번째 방법이 실패한 경우, get_iframe_balance 메서드 직접 시도
                if current_balance is None:
                    self.logger.warning("첫 번째 방법으로 잔액 업데이트 실패, 두 번째 방법 시도...")
                    current_balance = self.balance_service.get_iframe_balance()
                    
                    # 잔액을 가져왔으면 UI에 업데이트
                    if current_balance is not None:
                        self.main_window.update_user_data(current_amount=current_balance)
                
                # 3. 이것도 실패한 경우, 현재 페이지 소스에서 잔액 찾기 시도
                if current_balance is None:
                    self.logger.warning("두 번째 방법으로 잔액 업데이트 실패, 세 번째 방법 시도...")
                    balance, _ = self.balance_service.get_current_balance_and_username()
                    if balance is not None:
                        current_balance = balance
                        self.main_window.update_user_data(current_amount=current_balance)
                
                # 잔액을 성공적으로 가져왔는지 확인
                if current_balance is not None:
                    self.logger.info(f"베팅 결과 후 업데이트된 잔액: {current_balance:,}원")
                    
                    # 중요: 목표 금액 체크 - 잔액이 제대로 가져와진 경우에만
                    if self.balance_service.check_target_amount(current_balance):
                        self.logger.info("목표 금액 도달로 자동 매매를 중지합니다.")
                        return  # 여기서 함수 종료 - 더 이상 처리하지 않음
                else:
                    self.logger.error("베팅 결과 후 잔액을 업데이트할 수 없습니다.")
                
                # 방 이동이 필요한지 확인 (승리 시에만 확인)
                if result_status == "win":
                    if self.martin_service.should_change_room():
                        self.logger.info("배팅 성공으로 방 이동이 필요합니다.")
                        time.sleep(1)  # 1초 대기
                        self.should_move_to_next_room = True
                        self.logger.info("방 이동 플래그 설정됨: should_move_to_next_room = True")
        
        # 베팅 상태 초기화 (새 라운드 번호로)
        self.betting_service.reset_betting_state(new_round=new_game_count)
        self.logger.info(f"새로운 게임 시작: 베팅 상태 초기화 (게임 수: {new_game_count})")
        
        # UI 업데이트 (방 이름과 게임 수 갱신, 결과는 그대로 유지)
        # 방 이름에서 첫 번째 줄만 추출 (UI 표시용)
        display_room_name = self.current_room_name.split('\n')[0] if '\n' in self.current_room_name else self.current_room_name
        self.main_window.update_betting_status(
            room_name=f"{display_room_name} (게임 수: {new_game_count})",
            pick=self.current_pick
        )
        
    def _place_bet(self, pick_value, game_count):
        """베팅 실행"""
        try:
            # 매 베팅마다 설정을 파일에서 강제로 다시 로드
            if hasattr(self, 'martin_service'):
                # 설정 매니저 새로 생성하여 파일에서 설정 다시 로드
                self.martin_service.settings_manager = SettingsManager()
                self.martin_service.martin_count, self.martin_service.martin_amounts = self.martin_service.settings_manager.get_martin_settings()
                self.logger.info(f"[INFO] 베팅 전 마틴 설정 재로드 - 단계: {self.martin_service.martin_count}, 금액: {self.martin_service.martin_amounts}")
                
                # 현재 마틴 단계 디버깅
                self.logger.info(f"[DEBUG] 현재 마틴 단계: {self.martin_service.current_step} (0부터 시작)")
                self.logger.info(f"[DEBUG] 현재 베팅 단계 (UI 표시용): {self.martin_service.current_step + 1}")
                self.logger.info(f"[DEBUG] 진행 중인 step_items 키: {list(self.main_window.betting_widget.step_items.keys())}")
            
            # 중요: 베팅 전 현재 잔액 확인 및 목표 금액 체크
            balance = self.balance_service.get_iframe_balance()
            if balance:
                # 현재 잔액 업데이트
                self.main_window.update_user_data(current_amount=balance)
                
                # 마틴 배팅을 위한 잔고 충분한지 확인
                if not self._check_martin_balance(balance):
                    # 자동 매매 중지 (_check_martin_balance 함수에서 이미 경고 메시지를 표시)
                    self.stop_trading()
                    return False
                
                # 목표 금액 체크 (체크 결과가 True면 베팅 중단)
                if self.balance_service.check_target_amount(balance):
                    self.logger.info("목표 금액 도달로 베팅을 중단합니다.")
                    return False
            
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
                self.is_trading_active,
                bet_amount
            )
            
            # 현재 베팅 타입 저장
            self.current_pick = pick_value
            
            # 베팅 성공 여부와 관계없이 PICK 값을 UI에 표시
            if not bet_success:
                self.logger.warning(f"베팅 실패했지만 PICK 값은 유지: {pick_value}")
                self.main_window.update_betting_status(pick=pick_value)
            
            return bet_success
        
        except Exception as e:
            self.logger.error(f"베팅 중 오류 발생: {e}", exc_info=True)
            return False
        
        
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
            
            # 버튼 상태 업데이트
            self.main_window.start_button.setEnabled(True)
            self.main_window.stop_button.setEnabled(False)
            
            # 현재 게임방에서 나가기 시도
            try:
                # 현재 URL 확인
                current_url = self.devtools.driver.current_url
                
                # 게임방에 있는지 확인 (URL로 판단)
                in_game_room = "game" in current_url.lower() or "live" in current_url.lower()
                
                if in_game_room:
                    self.logger.info("현재 게임방에서 나가기 시도 중...")
                    # 게임방에서 나가는 함수 호출
                    self.game_monitoring_service.close_current_room()
                    self.logger.info("게임방에서 나가고 로비로 이동 완료")
                else:
                    self.logger.info("이미 카지노 로비에 있습니다.")
            except Exception as e:
                self.logger.warning(f"방 나가기 중 오류 발생: {e}")
                # 오류가 발생해도 자동 매매 종료 프로세스는 계속 진행
            
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
            if self.current_room_name:
                self.room_manager.mark_room_visited(self.current_room_name)
            # 방 이동 플래그 초기화
            self.should_move_to_next_room = False
            
            # 현재 방 닫기
            if not self.game_monitoring_service.close_current_room():
                self.logger.error("현재 방을 닫는데 실패했습니다.")
                return False
            
            # 방 이동 전 Excel 파일 초기화 (추가된 부분)
            try:
                self.logger.info("방 이동을 위해 Excel 파일 초기화 중...")
                self.excel_trading_service.excel_manager.initialize_excel()
                self.logger.info("Excel 파일 초기화 완료")
            except Exception as e:
                self.logger.error(f"Excel 파일 초기화 중 오류 발생: {e}")
                # 초기화 실패해도 계속 진행
            
            # 방 이동 전 상태 초기화 (베팅 위젯의 결과는 유지)
            self.game_count = 0
            self.result_count = 0
            self.current_pick = None
            self.betting_service.reset_betting_state()
            
            # 중요: martin_service의 베팅 카운터 및 결과 카운터 초기화
            self.logger.info("방 이동 시 마틴 서비스 초기화 중...")
            if hasattr(self, 'martin_service'):
                self.martin_service.reset()  # 마틴 베팅 상태 초기화
                # 추가 로그로 초기화 상태 확인
                self.logger.info(f"마틴 서비스 초기화 완료 - current_step: {self.martin_service.current_step}, "
                                f"배팅 카운터: {self.martin_service.betting_counter}, "
                                f"결과 카운터: {self.martin_service.result_counter}")
            
            # 중요: processed_rounds 세트 초기화 - 새 방 입장 시 이전 방의 결과 정보 제거
            self.processed_rounds = set()
            self.logger.info("처리된 결과 추적 세트 초기화")

            # 이 시점에서 카지노 로비 창으로 포커싱이 전환됨
            
            # 새 방 입장 (방문 큐에서 다음 방 선택)
            new_room_name = self.room_entry_service.enter_room()
            
            # 방 입장 실패 시 매매 중단
            if not new_room_name:
                self.stop_trading()
                QMessageBox.warning(self.main_window, "오류", "새 방 입장에 실패했습니다. 자동 매매를 중지합니다.")
                return False
            
            # 이제 확실히 새 방에 입장했으므로 이 시점에서 베팅 위젯 초기화 (이전 방의 결과 기록 보존은 끝)
            self.main_window.betting_widget.reset_step_markers()
            self.main_window.betting_widget.reset_room_results()
            
            # 입장한 새 방 정보로 UI 업데이트
            self.current_room_name = new_room_name
            self.main_window.update_betting_status(
                room_name=self.current_room_name,
                pick=""
            )

            # 새 방 입장 후 게임 상태 확인 및 최근 결과 기록
            try:
                self.logger.info("새 방 입장 후 최근 결과 확인 중...")
                # 게임 상태 확인 (충분한 시간 대기 후)
                game_state = self.game_monitoring_service.get_current_game_state(log_always=True)
                
                if game_state:
                    self.game_count = game_state.get('round', 0)
                    self.logger.info(f"새 방 게임 카운트: {self.game_count}")
                    
                    # 첫 입장 시 Excel에 기록하기 위해 game_count를 0으로 전달
                    temp_game_count = 0
                    
                    # 최근 결과 가져와서 Excel에 기록
                    result = self.excel_trading_service.process_game_results(
                        game_state, 
                        temp_game_count,  # 첫 입장으로 인식시키기 위해 0 전달
                        self.current_room_name,
                        log_on_change=True
                    )
                    
                    if result[0] is not None:
                        self.logger.info(f"새 방에 최근 결과 기록 완료: {result[2]}")
                        # 새 방 입장 후 강제로 첫 배팅 설정
                if result[0] is not None:
                    last_column, _, _, next_pick = result
                    
                    if next_pick in ['P', 'B']:
                        self.logger.info(f"새 방 입장 후 첫 배팅 설정: {next_pick}")
                        self.current_pick = next_pick
                        
                        # 첫 배팅을 위한 타이머 설정 (바로 배팅하도록 설정)
                        self._first_entry_time = time.time() - 5  # 이미 5초가 지난 것처럼 설정하여 즉시 배팅 유도
                        
                        # UI에 PICK 값 표시
                        self.main_window.update_betting_status(pick=next_pick)
        
            except Exception as e:
                self.logger.error(f"새 방 최근 결과 기록 중 오류 발생: {e}", exc_info=True)

            self.logger.info(f"새 방 '{self.current_room_name}'으로 이동 완료, 테이블 초기화됨, 게임 카운트 초기화: {self.game_count}")
            return True
        except Exception as e:
            self.logger.error(f"방 이동 중 오류 발생: {e}", exc_info=True)
            QMessageBox.warning(self.main_window, "경고", f"방 이동 실패: {str(e)}")
            return False
            
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )