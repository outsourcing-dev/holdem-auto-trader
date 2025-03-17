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
        self.current_pick = None
        self.should_move_to_next_room = False
        self.processed_rounds = set()

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
        
        # 스레드 객체 관리를 위한 속성
        self.room_entry_thread = None
        self.game_monitoring_thread = None
        self.betting_thread = None
        self.room_change_thread = None
        
    def _check_martin_balance(self, balance):
        """
        현재 잔고가 마틴 배팅을 하기에 충분한지 확인합니다.
        """
        try:
            # 마틴 설정 가져오기 (최신 설정 사용)
            martin_count, martin_amounts = self.settings_manager.get_martin_settings()
            
            # 마틴 1단계(첫 번째 단계) 금액
            first_martin_amount = martin_amounts[0] if martin_amounts else 1000
            
            # 현재 잔액이 마틴 1단계 금액보다 적은지 확인
            if balance < first_martin_amount:
                self.logger.warning(f"현재 잔고({balance:,}원)가 마틴 1단계 금액({first_martin_amount:,}원)보다 적습니다.")
                
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
            return False
        
    def start_trading(self):
        """자동 매매 시작 로직"""
        try:
            # 사전 검증
            if not self._validate_trading_prerequisites():
                return

            # DB에서 남은 일수 재확인
            from utils.db_manager import DBManager
            db_manager = DBManager()
            
            # 현재 로그인된 사용자 이름 가져오기
            username = self.main_window.username
            if not username:
                QMessageBox.warning(self.main_window, "오류", "로그인 정보를 찾을 수 없습니다.")
                return
                
            # 관리자 계정인 경우 무제한 일수 부여
            if username == "coreashield":
                days_left = 99999
            else:
                user_info = db_manager.get_user(username)
                if not user_info:
                    QMessageBox.warning(self.main_window, "오류", "사용자 정보를 DB에서 찾을 수 없습니다.")
                    return
                    
                # 사용 기간 확인
                end_date = user_info[2]
                days_left = db_manager.calculate_days_left(end_date)
            
            # 남은 일수가 없으면 종료
            if days_left <= 0:
                QMessageBox.warning(self.main_window, "사용 기간 만료", "관리자에 의해 사용 기간이 만료되었습니다.")
                self.main_window.set_license_remaining_time(0)
                self.main_window.enable_application_features(False)
                return
                
            self.logger.info(f"DB에서 확인한 남은 사용 기간: {days_left}일")
            
            # 라이센스 시간 재설정
            if hasattr(self.main_window, 'set_license_remaining_time'):
                self.main_window.set_license_remaining_time(days_left)
            
            self.logger.info("자동 매매 시작 전 설정 재로드")
            
            # 설정 매니저 갱신
            self.settings_manager = SettingsManager()
            
            # 잔액/목표금액 서비스 갱신
            if hasattr(self, 'balance_service'):
                self.balance_service.settings_manager = SettingsManager()
                target_amount = self.balance_service.settings_manager.get_target_amount()
                self.logger.info(f"현재 설정된 목표 금액: {target_amount:,}원")

            # 마틴 서비스 초기화 및 갱신
            if hasattr(self, 'martin_service'):
                self.martin_service.reset()
                self.martin_service.settings_manager = self.settings_manager
                self.martin_service.martin_count, self.martin_service.martin_amounts = self.martin_service.settings_manager.get_martin_settings()
                self.logger.info(f"마틴 설정 재로드 - 단계: {self.martin_service.martin_count}, 금액: {self.martin_service.martin_amounts}")

            # 베팅 서비스 상태 초기화
            if hasattr(self, 'betting_service'):
                self.betting_service.reset_betting_state()
                self.logger.info("베팅 상태 초기화 완료")

            # 게임 처리 기록 초기화
            self.processed_rounds = set()
            
            # 브라우저 실행 확인
            if not self.devtools.driver:
                self.devtools.start_browser()
                
            # 창 개수 확인
            window_handles = self.devtools.driver.window_handles
            if len(window_handles) < 2:
                QMessageBox.warning(self.main_window, "오류", "창 개수가 부족합니다. 최소 2개의 창이 필요합니다.")
                return

            # 카지노 로비 창으로 전환 및 잔액 확인
            if len(window_handles) >= 2:
                self.devtools.driver.switch_to.window(window_handles[1])
                self.logger.info("카지노 로비 창으로 포커싱 전환")
            
            balance = self.balance_service.get_lobby_balance()
            
            if balance is None:
                QMessageBox.warning(self.main_window, "오류", "로비에서 잔액 정보를 찾을 수 없습니다.")
                return

            # UI 초기화 및 잔액 표시
            self.main_window.reset_ui()
            self.main_window.update_user_data(
                username=username,
                start_amount=balance,
                current_amount=balance
            )

            # 마틴 배팅을 위한 잔고 확인
            if not self._check_martin_balance(balance):
                return

            # 게임 컨트롤러 초기화
            excel_path = os.environ.get("AUTO_EXCEL_PATH")
            self.logger.info(f"Excel 경로: {excel_path}")
            self.game_controller = GameController(self.devtools.driver, excel_path)

            # 자동 매매 활성화
            self.is_trading_active = True
            self.logger.info("자동 매매 시작!")
            
            # 버튼 상태 업데이트
            self.main_window.start_button.setEnabled(False)
            self.main_window.stop_button.setEnabled(True)
            
            # 목표 금액 체크
            if self.balance_service.check_target_amount(balance):
                self.logger.info("목표 금액에 이미 도달하여 자동 매매를 시작하지 않습니다.")
                return
            
            # 자동 매매가 중지되었는지 확인
            if not self.is_trading_active:
                self.logger.info("목표 금액 도달로 자동 매매가 이미 중지되었습니다.")
                return

            # 방문 순서 초기화
            self.room_manager.generate_visit_order()
            
            # 방 선택 및 입장
            self.current_room_name = self.room_entry_service.enter_room()
            
            # 방 입장에 실패한 경우
            if not self.current_room_name:
                self.stop_trading()
                return
            
            # 남은 시간 설정
            self.main_window.set_remaining_time(1, 0, 0)

            # 게임 정보 초기 분석
            self.analyze_current_game()

            # 자동 매매 루프 시작
            self.run_auto_trading()

        except Exception as e:
            self.logger.error(f"자동 매매 시작 중 오류 발생: {e}", exc_info=True)
            
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
        
        self.logger.info(f"선택된 방 {len(checked_rooms)}개")
        return True

    def analyze_current_game(self):
        """현재 게임 상태를 분석하여 게임 수와 결과를 확인"""
        try:
            # 방 이동 플래그 확인
            if self.should_move_to_next_room:
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
                
                # 첫 입장 시 방 정보 출력
                if previous_game_count == 0 and current_game_count > 0:
                    display_room_name = self.current_room_name.split('\n')[0] if '\n' in self.current_room_name else self.current_room_name
                    self.logger.info(f"방 '{display_room_name}'의 현재 게임 수: {current_game_count}")
            
            # 엑셀 처리 및 PICK 값 확인
            result = self.excel_trading_service.process_game_results(
                game_state, 
                self.game_count, 
                self.current_room_name,
                log_on_change=True
            )

            # 결과 처리
            if result[0] is not None:
                last_column, new_game_count, recent_results, next_pick = result
                
                # 새 게임 시작 시 이전 게임 결과 확인
                if new_game_count > self.game_count:
                    self._process_previous_game_result(game_state, new_game_count)
                    
                    # 타이(T) 결과 확인
                    if latest_result == 'T':
                        self.should_move_to_next_room = False
                    
                    # PICK 값에 따른 베팅 실행
                    if not self.should_move_to_next_room and next_pick in ['P', 'B'] and not self.betting_service.has_bet_current_round:
                        self.main_window.update_betting_status(pick=next_pick)

                        # 첫 입장 시 바로 베팅하지 않음
                        if previous_game_count > 0:
                            self._place_bet(next_pick, new_game_count)
                        else:
                            self.logger.info(f"첫 입장 후 게임 상황 파악 중 (PICK: {next_pick})")
                            self.current_pick = next_pick

                    # 게임 카운트 및 최근 결과 업데이트
                    self.game_count = new_game_count
                    self.recent_results = recent_results
                
                # 첫 입장 후 일정 시간 경과 시 베팅
                elif previous_game_count == 0 and self.game_count > 0 and not self.betting_service.has_bet_current_round:
                    if hasattr(self, '_first_entry_time'):
                        elapsed = time.time() - self._first_entry_time
                        if elapsed > 1.0 and next_pick in ['P', 'B']:
                            self.logger.info(f"첫 입장 후 {elapsed:.1f}초 경과, 베팅 실행: {next_pick}")
                            self.current_pick = next_pick
                            self.main_window.update_betting_status(pick=next_pick)
                            self._place_bet(next_pick, self.game_count)
                            delattr(self, '_first_entry_time')
                    else:
                        self._first_entry_time = time.time()
            
            # 무승부(T) 결과 시 베팅 시도
            if (latest_result == 'T' and 
                not self.betting_service.has_bet_current_round and 
                self.current_pick in ['P', 'B'] and
                not self.should_move_to_next_room and
                self.game_count > 0):
                
                # 베팅 상태 초기화
                self.betting_service.has_bet_current_round = False
                
                self.logger.info(f"무승부(T) 감지, 이전 PICK 값({self.current_pick})으로 베팅 시도")
                time.sleep(3)

                bet_success = self._place_bet(self.current_pick, self.game_count)
                
                if bet_success:
                    self.logger.info(f"TIE 이후 베팅 성공: {self.current_pick}")
                else:
                    self.logger.warning(f"TIE 이후 베팅 실패. 다음 상태 확인에서 재시도")
                    self.main_window.set_remaining_time(0, 0, 1)
            
            # 다음 분석 간격 설정
            self.main_window.set_remaining_time(0, 0, 2)
                    
        except Exception as e:
            self.logger.error(f"게임 상태 분석 중 오류 발생: {e}", exc_info=True)
            self.main_window.set_remaining_time(0, 0, 2)
            
    def _process_previous_game_result(self, game_state, new_game_count):
        """이전 게임 결과 처리 및 배팅 상태 초기화"""
        # 이전 베팅 정보 가져오기
        last_bet = self.betting_service.get_last_bet()
        
        # 이전 게임에 베팅했는지 확인
        if last_bet and last_bet['round'] == self.game_count:
            bet_type = last_bet['type']
            latest_result = game_state.get('latest_result')
            
            self.logger.info(f"[결과검증] 라운드: {self.game_count}, 베팅: {bet_type}, 결과: {latest_result}")
            
            if bet_type in ['P', 'B'] and latest_result:
                # 결과 판정
                is_tie = (latest_result == 'T')
                is_win = (not is_tie and bet_type == latest_result)
                
                # 결과 설정
                if is_tie:
                    result_text = "무승부"
                    result_marker = "T"
                    result_status = "tie"
                    # 타이 결과는 배팅 상태 초기화 및 방 이동 안함
                    self.betting_service.has_bet_current_round = False
                    self.betting_service.reset_betting_state(new_round=new_game_count)
                    self.should_move_to_next_room = False
                    self.logger.info("타이(T) 결과: 같은 방에서 재시도")
                elif is_win:
                    result_text = "적중"
                    result_marker = "O"
                    result_status = "win"
                    # 승리 시 즉시 방 이동
                    self.should_move_to_next_room = True
                    self.logger.info("베팅 성공: 방 이동 필요")
                else:
                    result_text = "실패"
                    result_marker = "X"
                    result_status = "lose"
                    # 실패 시도 즉시 방 이동
                    self.should_move_to_next_room = True
                    self.logger.info("베팅 실패: 방 이동 필요")
                
                # 결과 카운트 증가
                self.result_count += 1
                
                # 마틴 베팅 단계 업데이트
                result = self.martin_service.process_bet_result(
                    result_status, 
                    game_count=self.game_count
                )
                
                current_step, consecutive_losses, result_position = result
                
                # 베팅 위젯에 결과 표시
                self.main_window.betting_widget.set_step_marker(result_position, result_marker)
                
                # 방 로그 위젯에 결과 추가
                self.main_window.room_log_widget.add_bet_result(
                    room_name=self.current_room_name,
                    is_win=is_win,
                    is_tie=is_tie
                )
                
                # 잔액 업데이트
                current_balance = None
                
                # 잔액 확인 시도 1: balance_service 사용
                current_balance = self.balance_service.update_balance_after_bet_result(is_win=is_win)
                
                # 잔액 확인 시도 2: iframe 직접 확인
                if current_balance is None:
                    self.logger.warning("첫 번째 방법으로 잔액 업데이트 실패, 두 번째 방법 시도...")
                    current_balance = self.balance_service.get_iframe_balance()
                    
                    if current_balance is not None:
                        self.main_window.update_user_data(current_amount=current_balance)
                
                # 잔액 확인 시도 3: 페이지 소스에서 확인
                if current_balance is None:
                    self.logger.warning("두 번째 방법으로 잔액 업데이트 실패, 세 번째 방법 시도...")
                    balance, _ = self.balance_service.get_current_balance_and_username()
                    if balance is not None:
                        current_balance = balance
                        self.main_window.update_user_data(current_amount=current_balance)
                
                # 목표 금액 확인
                if current_balance is not None:
                    self.logger.info(f"베팅 결과 후 잔액: {current_balance:,}원")
                    
                    if self.balance_service.check_target_amount(current_balance):
                        self.logger.info("목표 금액 도달로 자동 매매를 중지합니다.")
                        return
                else:
                    self.logger.error("베팅 결과 후 잔액을 업데이트할 수 없습니다.")
                
                # 무승부 시 방 이동 안함 재확인
                if is_tie:
                    self.should_move_to_next_room = False
                else:
                    self.should_move_to_next_room = True
                
                # 마틴 단계 로그
                self.logger.info(f"현재 마틴 단계: {current_step+1}/{self.martin_service.martin_count}")
                    
        elif last_bet:
            # 라운드가 달라진 경우 로그만 남김
            self.logger.info(f"이전 베팅({last_bet['round']})과 현재 게임({self.game_count})의 라운드가 불일치합니다.")
            self.betting_service.has_bet_current_round = False
            self.betting_service.current_bet_round = new_game_count
        
        # 타이(T) 결과를 제외하고 베팅 상태 초기화
        if game_state.get('latest_result') != 'T':
            self.betting_service.reset_betting_state(new_round=new_game_count)
            self.logger.info(f"새로운 게임 시작: 베팅 상태 초기화 (게임 수: {new_game_count})")
        
        # UI 업데이트
        display_room_name = self.current_room_name.split('\n')[0] if '\n' in self.current_room_name else self.current_room_name
        self.main_window.update_betting_status(
            room_name=f"{display_room_name} (게임 수: {new_game_count})",
            pick=self.current_pick
        )
        
    def _place_bet(self, pick_value, game_count):
        """베팅 실행"""
        try:
            # 현재 방에서 이미 배팅한 경우 즉시 방 이동
            if self.martin_service.has_bet_in_current_room:
                self.logger.info("현재 방에서 이미 배팅했으므로 방 이동 플래그 설정")
                self.should_move_to_next_room = True
                return False
            
            # 마틴 설정 갱신
            self.martin_service.settings_manager = SettingsManager()
            self.martin_service.martin_count, self.martin_service.martin_amounts = self.martin_service.settings_manager.get_martin_settings()
            
            # 잔액 확인 및 목표 금액 체크
            balance = self.balance_service.get_iframe_balance()
            if balance:
                # 현재 잔액 업데이트
                self.main_window.update_user_data(current_amount=balance)
                
                # 마틴 배팅을 위한 잔고 확인
                if not self._check_martin_balance(balance):
                    self.stop_trading()
                    return False
                
                # 목표 금액 체크
                if self.balance_service.check_target_amount(balance):
                    self.logger.info("목표 금액 도달로 베팅을 중단합니다.")
                    return False
            
            # 마틴 단계 배팅 금액 가져오기
            bet_amount = self.martin_service.get_current_bet_amount()
            self.logger.info(f"마틴 단계 {self.martin_service.current_step + 1}/{self.martin_service.martin_count}: {bet_amount:,}원 베팅")
            
            # UI 업데이트
            self.main_window.update_betting_status(
                pick=pick_value, 
                bet_amount=bet_amount
            )
            
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
            
            # 베팅 성공 시 처리
            if bet_success:
                self.martin_service.has_bet_in_current_room = True
                self.logger.info("베팅 성공: 한 방에서 한 번 배팅 완료 표시")
                
                # 누적 배팅 금액 업데이트
                self.martin_service.total_bet_amount += bet_amount
                if hasattr(self.main_window, 'total_bet_amount'):
                    self.main_window.total_bet_amount += bet_amount
                else:
                    self.main_window.total_bet_amount = bet_amount
                
                # UI 업데이트
                self.main_window.update_user_data(total_bet=self.main_window.total_bet_amount)
                self.logger.info(f"누적 배팅 금액 업데이트: {self.main_window.total_bet_amount:,}원 (+{bet_amount:,}원)")
            
            # PICK 값을 UI에 표시
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
                
                # 게임방에 있는지 확인
                in_game_room = "game" in current_url.lower() or "live" in current_url.lower()
                
                if in_game_room:
                    self.logger.info("현재 게임방에서 나가기 시도 중...")
                    self.game_monitoring_service.close_current_room()
                    self.logger.info("게임방에서 나가고 로비로 이동 완료")
                else:
                    self.logger.info("이미 카지노 로비에 있습니다.")
            except Exception as e:
                self.logger.warning(f"방 나가기 중 오류 발생: {e}")
            
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
                f"자동 매매 중지 중 문제가 발생했습니다.\n수동으로 중지되었습니다.\n오류: {str(e)}"
            )

    def change_room(self):
        """현재 방을 나가고 새로운 방으로 이동합니다."""
        try:
            self.logger.info("방 이동 준비 중...")
            if self.current_room_name:
                self.room_manager.mark_room_visited(self.current_room_name)
            
            # 방 이동 플래그 초기화
            self.should_move_to_next_room = False
            
            # 현재 방 닫기
            if not self.game_monitoring_service.close_current_room():
                self.logger.error("현재 방을 닫는데 실패했습니다.")
                return False
            
            # Excel 파일 초기화
            try:
                self.logger.info("Excel 파일 초기화 중...")
                self.excel_trading_service.excel_manager.initialize_excel()
                self.logger.info("Excel 파일 초기화 완료")
            except Exception as e:
                self.logger.error(f"Excel 파일 초기화 중 오류 발생: {e}")
            
            # 상태 초기화
            self.game_count = 0
            self.result_count = 0
            self.current_pick = None
            self.betting_service.reset_betting_state()
            
            # 현재 방 배팅 상태 초기화
            if hasattr(self, 'martin_service'):
                self.martin_service.reset_room_bet_status()
                self.logger.info(f"마틴 단계 유지 - 현재 단계: {self.martin_service.current_step+1}")
            
            # processed_rounds 초기화
            self.processed_rounds = set()
            
            # 새 방 입장
            new_room_name = self.room_entry_service.enter_room()
            
            # 방 입장 실패 시 처리
            if not new_room_name:
                # 방문 큐 리셋
                if self.room_manager.reset_visit_queue():
                    self.logger.info("방 입장 실패. 방문 큐를 리셋하고 다시 시도합니다.")
                    return self.change_room()  # 재귀적으로 다시 시도
                else:
                    self.stop_trading()
                    QMessageBox.warning(self.main_window, "오류", "체크된 방이 없거나 모든 방 입장에 실패했습니다.")
                    return False
            
            # 베팅 위젯 초기화
            self.main_window.betting_widget.reset_step_markers()
            self.main_window.betting_widget.reset_room_results()
            self.logger.info("새 방 입장: 베팅 위젯 초기화 완료")
            
            # UI 업데이트
            self.current_room_name = new_room_name
            self.main_window.update_betting_status(
                room_name=self.current_room_name,
                pick=""
            )

            # 게임 상태 확인 및 최근 결과 기록
            try:
                self.logger.info("새 방 입장 후 최근 결과 확인 중...")
                game_state = self.game_monitoring_service.get_current_game_state(log_always=True)
                
                if game_state:
                    self.game_count = game_state.get('round', 0)
                    self.logger.info(f"새 방 게임 카운트: {self.game_count}")
                    
                    # Excel에 기록
                    temp_game_count = 0
                    
                    result = self.excel_trading_service.process_game_results(
                        game_state, 
                        temp_game_count,
                        self.current_room_name,
                        log_on_change=True
                    )
                    
                    if result[0] is not None:
                        self.logger.info(f"새 방에 최근 결과 기록 완료")
                        
                        if result[0] is not None:
                            last_column, _, _, next_pick = result
                            
                            if next_pick in ['P', 'B']:
                                self.logger.info(f"새 방 입장 후 첫 배팅 설정: {next_pick}")
                                self.current_pick = next_pick
                                
                                # 즉시 배팅 유도
                                self._first_entry_time = time.time() - 5
                                
                                # UI에 PICK 값 표시
                                self.main_window.update_betting_status(
                                    pick=next_pick,
                                    bet_amount=self.martin_service.get_current_bet_amount()
                                )
        
            except Exception as e:
                self.logger.error(f"새 방 최근 결과 기록 중 오류 발생: {e}", exc_info=True)

            self.logger.info(f"새 방으로 이동 완료, 게임 카운트: {self.game_count}")
            return True
        except Exception as e:
            self.logger.error(f"방 이동 중 오류 발생: {e}", exc_info=True)
            QMessageBox.warning(self.main_window, "경고", f"방 이동 실패: {str(e)}")
            return False