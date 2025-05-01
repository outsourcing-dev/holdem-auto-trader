import logging

class UIUpdater:
    def __init__(self, main_window, logger=None):
        self.main_window = main_window
        # logger를 명시적으로 설정. logger가 제공되지 않으면 기본 로거 사용
        self.logger = logger or logging.getLogger(__name__)

    def set_remaining_time(self, hours, minutes, seconds):
        """남은 시간 설정"""
        self.main_window.remaining_seconds = hours * 3600 + minutes * 60 + seconds
        
        if not hasattr(self.main_window, 'timer'):
            from PyQt6.QtCore import QTimer
            self.main_window.timer = QTimer()
            self.main_window.timer.timeout.connect(self.update_remaining_time)
        
        if not self.main_window.timer.isActive():
            self.main_window.timer.start(1000)  # 1초마다 업데이트
    
    def update_remaining_time(self):
        """타이머에 의해 호출되는 남은 시간 업데이트"""
        if not hasattr(self.main_window, 'remaining_seconds'):
            self.main_window.remaining_seconds = 0

        if self.main_window.remaining_seconds > 0:
            self.main_window.remaining_seconds -= 1
        else:
            tm = getattr(self.main_window, 'trading_manager', None)

            if tm and tm._is_processing_result:
                # 분석이 이미 진행 중이라면 추가로 실행하지 않음
                self.logger.info("[UIUpdater] 분석 이미 진행 중 - 다시 호출하지 않음.")
                return
            
            if tm and tm.is_trading_active:
                self.logger.info("[UIUpdater] 분석 시작")
                tm.analyze_current_game()  # 게임 분석 시작

                # 분석이 끝나면 이 플래그를 False로 설정
                tm._is_processing_result = False  # 분석 완료 후 플래그를 False로 설정

                # 첫 번째 결과를 받은 경우 대기 모드를 해제
                if hasattr(tm, 'wait_first_result') and tm.wait_first_result:
                    self.logger.info("[UIUpdater] 첫 번째 결과를 받음 - 대기 모드 해제")
                    tm.wait_first_result = False  # 대기 모드 해제

                # 타이머 중지: 분석을 시작하기 전에 타이머를 중지합니다.
                if hasattr(self.main_window, 'timer') and self.main_window.timer.isActive():
                    self.main_window.timer.stop()
                    self.logger.info("[UIUpdater] 분석 시작 전 타이머 중지")
                
                # 분석 후 2초 뒤 다시 예약
                self.set_remaining_time(0, 0, 2)  # 다음 분석 예약
            else:
                self.logger.info("[UIUpdater] 자동 매매 비활성화 상태로 분석 생략")
                self.main_window.set_remaining_time(0, 0, 2)  # 자동 매매가 비활성화되었으면 타이머 재설정


    def update_remaining_time_display(self):
        pass
    
    def update_user_data(self, username=None, start_amount=None, current_amount=None, profit_amount=None, total_bet=None):
        """사용자 데이터 업데이트 - 내부 변수와 UI 모두 업데이트"""
        if username is not None:
            self.main_window.username = username
            self.main_window.header.update_user_info(username)
            
        if start_amount is not None:
            # 시작 금액은 처음 설정된 경우에만 적용 (이미 값이 있으면 유지)
            if self.main_window.start_amount == 0:
                self.main_window.start_amount = start_amount
                self.main_window.header.update_start_amount(start_amount)
            
        if current_amount is not None:
            self.main_window.current_amount = current_amount
            self.main_window.header.update_current_amount(current_amount)
            
            # 현재 금액이 변경되면 수익 금액도 재계산
            if self.main_window.start_amount > 0:
                new_profit = self.main_window.current_amount - self.main_window.start_amount
                self.main_window.profit_amount = new_profit
                self.main_window.header.update_profit(new_profit)
                
        if profit_amount is not None:
            self.main_window.profit_amount = profit_amount
            self.main_window.header.update_profit(profit_amount)
            
        if total_bet is not None:
            self.main_window.total_bet_amount = total_bet
            self.main_window.header.update_total_bet(total_bet)
    
    def update_betting_status(self, room_name=None, pick=None, step_markers=None, bet_amount=None, reset_counter=False):
        """배팅 상태 업데이트 - 두 위젯 모두 업데이트"""
        if room_name is not None:
            # BettingWidget에 현재 방 이름 설정
            self.main_window.betting_widget.update_current_room(room_name, reset_counter)
            
            # RoomLogWidget에도 현재 방 설정 (내부적으로 필요한 경우 로그 항목 생성)
            if hasattr(self.main_window, 'room_log_widget'):
                self.main_window.room_log_widget.set_current_room(room_name)
        
        if pick is not None:
            # BettingWidget에 PICK 값 설정
            self.main_window.betting_widget.set_pick(pick)
        
        if step_markers is not None:
            # BettingWidget에 단계 마커 설정
            for step, marker in step_markers.items():
                self.main_window.betting_widget.set_step_marker(step, marker)
        
        if bet_amount is not None:
            # BettingWidget에 현재 배팅 금액 설정
            self.main_window.betting_widget.update_bet_amount(bet_amount)
            
    def add_betting_result(self, no, room_name, step, result):
        """배팅 결과 추가 - BettingWidget 업데이트"""
        # BettingWidget에 결과 추가
        self.main_window.betting_widget.add_raw_result(no, room_name, step, result)
        
        # 방 로그 위젯은 TradingManager에서 직접 업데이트합니다.
        # is_win = (result == "적중")
        # if hasattr(self.main_window, 'room_log_widget'):
        #     self.main_window.room_log_widget.add_bet_result(room_name, is_win)
