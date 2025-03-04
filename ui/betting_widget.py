from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
                             QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt
from utils.settings_manager import SettingsManager

class BettingWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.settings_manager = SettingsManager()
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        self.current_martin_step = 0
        self.total_profit = 0
        self.win_count = 0
        self.lose_count = 0
        
        main_layout = QVBoxLayout()
        
        # 상태 섹션
        status_layout = QHBoxLayout()
        
        # 현재 마틴 단계
        step_layout = QVBoxLayout()
        self.step_label = QLabel("현재 마틴 단계")
        self.step_progress = QProgressBar()
        self.step_progress.setMinimum(0)
        self.step_progress.setMaximum(self.martin_count)
        self.step_progress.setValue(0)
        step_layout.addWidget(self.step_label)
        step_layout.addWidget(self.step_progress)
        status_layout.addLayout(step_layout)
        
        # 승패 현황
        record_layout = QVBoxLayout()
        self.record_label = QLabel("승/패 현황")
        self.record_status = QLabel("승: 0 / 패: 0 (승률: 0%)")
        record_layout.addWidget(self.record_label)
        record_layout.addWidget(self.record_status)
        status_layout.addLayout(record_layout)
        
        main_layout.addLayout(status_layout)
        
        # 현재 배팅 정보
        self.current_bet_label = QLabel(f"현재 배팅: {self.get_current_bet_amount():,}원")
        self.current_bet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_bet_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #007BFF;")
        main_layout.addWidget(self.current_bet_label)
        
        # 마틴 배팅 테이블
        self.betting_table = QTableWidget()
        self.betting_table.setColumnCount(3)
        self.betting_table.setHorizontalHeaderLabels(["단계", "배팅 금액", "상태"])
        self.betting_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 테이블 초기화
        self.update_betting_table()
        main_layout.addWidget(self.betting_table)
        
        self.setLayout(main_layout)
    
    def update_settings(self):
        """설정이 변경되었을 때 호출"""
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        self.step_progress.setMaximum(self.martin_count)
        self.update_betting_table()
        self.update_current_bet_label()
    
    def get_current_bet_amount(self):
        """현재 배팅 금액 반환"""
        if self.current_martin_step < len(self.martin_amounts):
            return self.martin_amounts[self.current_martin_step]
        return 0
    
    def update_current_bet_label(self):
        """현재 배팅 금액 라벨 업데이트"""
        self.current_bet_label.setText(f"현재 배팅: {self.get_current_bet_amount():,}원")
    
    def update_betting_table(self):
        """배팅 테이블 업데이트"""
        self.betting_table.setRowCount(self.martin_count)
        
        for i in range(self.martin_count):
            # 단계 열
            stage_item = QTableWidgetItem(f"{i+1}")
            stage_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.betting_table.setItem(i, 0, stage_item)
            
            # 금액 열
            amount = self.martin_amounts[i] if i < len(self.martin_amounts) else 0
            amount_item = QTableWidgetItem(f"{amount:,}원")
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.betting_table.setItem(i, 1, amount_item)
            
            # 상태 열
            status = ""
            if i < self.current_martin_step:
                status = "패배"
                status_color = "color: red;"
            elif i == self.current_martin_step:
                status = "현재"
                status_color = "color: blue; font-weight: bold;"
            else:
                status = "대기"
                status_color = "color: gray;"
                
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setData(Qt.ItemDataRole.UserRole, status_color)
            self.betting_table.setItem(i, 2, status_item)
            self.betting_table.item(i, 2).setStyleSheet(status_color)
    
    def on_win(self):
        """승리 처리"""
        amount = self.get_current_bet_amount()
        self.total_profit += amount
        self.win_count += 1
        
        # 마틴 단계 초기화
        self.current_martin_step = 0
        
        # UI 업데이트
        self.update_record_status()
        self.update_betting_table()
        self.update_current_bet_label()
        self.step_progress.setValue(self.current_martin_step)
    
    def on_lose(self):
        """패배 처리"""
        amount = self.get_current_bet_amount()
        self.total_profit -= amount
        self.lose_count += 1
        
        # 마틴 단계 증가
        self.current_martin_step += 1
        if self.current_martin_step >= self.martin_count:
            # 마틴 한도 초과: 초기화
            self.current_martin_step = 0
        
        # UI 업데이트
        self.update_record_status()
        self.update_betting_table()
        self.update_current_bet_label()
        self.step_progress.setValue(self.current_martin_step)
    
    def update_record_status(self):
        """승/패 현황 업데이트"""
        total = self.win_count + self.lose_count
        win_rate = (self.win_count / total * 100) if total > 0 else 0
        
        self.record_status.setText(f"승: {self.win_count} / 패: {self.lose_count} (승률: {win_rate:.1f}%)")
        
        # 수익금 상태에 따라 색상 설정
        if self.total_profit > 0:
            profit_color = "color: green;"
        elif self.total_profit < 0:
            profit_color = "color: red;"
        else:
            profit_color = "color: black;"
            
        self.record_status.setStyleSheet(profit_color)