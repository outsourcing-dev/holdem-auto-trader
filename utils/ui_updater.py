# 4. ui_updater.py - UI 업데이트 관련 기능
class UIUpdater:
    def __init__(self, main_window):
        self.main_window = main_window
    
    def set_remaining_time(self, hours, minutes, seconds):
        """남은 시간 설정"""
        self.main_window.remaining_seconds = hours * 3600 + minutes * 60 + seconds
        self.update_remaining_time_display()
        
        # 타이머가 작동 중이 아니면 시작
        if not self.main_window.timer.isActive():
            self.main_window.timer.start(1000)  # 1초마다 업데이트
    
    def update_remaining_time(self):
        """타이머에 의해 호출되는 남은 시간 업데이트"""
        if self.main_window.remaining_seconds > 0:
            self.main_window.remaining_seconds -= 1
            self.update_remaining_time_display()
        else:
            # 자동 매매 활성화 상태인지 확인
            if hasattr(self.main_window, 'trading_manager') and self.main_window.trading_manager.is_trading_active:
                # 게임 분석 실행
                self.main_window.trading_manager.analyze_current_game()
                # 다시 타이머 설정 (2초 간격으로 계속 모니터링)
                self.set_remaining_time(0, 0, 2)
            else:
                # 자동 매매가 활성화되지 않은 경우 타이머 정지
                self.main_window.timer.stop()
            
    def update_remaining_time_display(self):
        """남은 시간 표시 업데이트"""
        hours = self.main_window.remaining_seconds // 3600
        minutes = (self.main_window.remaining_seconds % 3600) // 60
        seconds = self.main_window.remaining_seconds % 60
        
        time_str = f"{hours:02} : {minutes:02} : {seconds:02}"
        self.main_window.remaining_time_value.setText(time_str)
    
    def update_user_data(self, username=None, start_amount=None, current_amount=None, profit_amount=None, total_bet=None):
        """사용자 데이터 업데이트 - 내부 변수와 UI 모두 업데이트"""
        if username is not None:
            self.main_window.username = username
            self.main_window.header.update_user_info(username)
            
        if start_amount is not None:
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
    
    def update_betting_status(self, room_name=None, pick=None, step_markers=None):
        """배팅 상태 업데이트"""
        if room_name is not None:
            self.main_window.betting_widget.update_current_room(room_name)
        if pick is not None:
            self.main_window.betting_widget.set_pick(pick)
        if step_markers is not None:
            for step, marker in step_markers.items():
                self.main_window.betting_widget.set_step_marker(step, marker)
    
    def add_betting_result(self, no, room_name, step, result):
        """배팅 결과 추가"""
        self.main_window.betting_widget.add_raw_result(no, room_name, step, result)