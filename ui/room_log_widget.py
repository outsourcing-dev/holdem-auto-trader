from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

class RoomLogWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        # 방별 로그 데이터를 저장하는 딕셔너리
        # {방이름: {'attempts': 시도횟수, 'win': 승리횟수, 'lose': 패배횟수, 'tie': 타이횟수}}
        self.room_logs = {}
        
        # 전체 통계
        self.total_win_count = 0
        self.total_lose_count = 0
        
        main_layout = QVBoxLayout()
        
        # 로그 섹션
        log_group = QGroupBox("방 로그")
        log_layout = QVBoxLayout()
        
        # 로그 테이블
        self.log_table = QTableWidget()
        self.log_table.setMinimumHeight(300)  # 최소 높이 설정
        self.log_table.setColumnCount(5)  # 방 이름, 시도 횟수, 승, 패, 성공률
        self.log_table.setHorizontalHeaderLabels(["방 이름", "시도", "승", "패", "성공률"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.log_table.setRowCount(0)  # 초기에는 데이터 없음
        
        log_layout.addWidget(self.log_table)
        
        # 총 승패 요약 표시
        summary_layout = QHBoxLayout()
        
        # 총 적중 수
        win_layout = QHBoxLayout()
        win_label = QLabel("적중")
        win_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-size: 14px; border-radius: 4px;")
        self.win_count_label = QLabel("0")  # 초기값 0
        self.win_count_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        win_layout.addWidget(win_label)
        win_layout.addWidget(self.win_count_label)
        summary_layout.addLayout(win_layout)
        
        # 총 실패 수
        lose_layout = QHBoxLayout()
        lose_label = QLabel("실패")
        lose_label.setStyleSheet("background-color: #F44336; color: white; padding: 8px; font-size: 14px; border-radius: 4px;")
        self.lose_count_label = QLabel("0")  # 초기값 0
        self.lose_count_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        lose_layout.addWidget(lose_label)
        lose_layout.addWidget(self.lose_count_label)
        summary_layout.addLayout(lose_layout)
        
        log_layout.addLayout(summary_layout)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        self.setLayout(main_layout)
    
    def add_bet_result(self, room_name, is_win, is_tie=False):
        """
        배팅 결과 추가 - 방별로 한 행씩만 표시하고 통계 업데이트
        
        Args:
            room_name (str): 방 이름
            is_win (bool): 승리 여부
            is_tie (bool): 타이(무승부) 여부
        """
        # 방이 로그에 없으면 새로 추가
        if room_name not in self.room_logs:
            self.room_logs[room_name] = {
                'attempts': 0,
                'win': 0,
                'lose': 0,
                'tie': 0
            }
        
        # 시도 횟수 증가
        self.room_logs[room_name]['attempts'] += 1
        
        # 승패 기록
        if is_tie:
            self.room_logs[room_name]['tie'] += 1
        elif is_win:
            self.room_logs[room_name]['win'] += 1
            self.total_win_count += 1
            self.win_count_label.setText(str(self.total_win_count))
        else:
            self.room_logs[room_name]['lose'] += 1
            self.total_lose_count += 1
            self.lose_count_label.setText(str(self.total_lose_count))
        
        # 테이블 업데이트
        self.update_table()
    
    def update_table(self):
        """로그 테이블 업데이트"""
        # 테이블 초기화
        self.log_table.setRowCount(0)
        
        # 각 방의 로그 데이터를 행으로 추가
        for room_name, data in self.room_logs.items():
            row_position = self.log_table.rowCount()
            self.log_table.insertRow(row_position)
            
            # 항목 생성
            name_item = QTableWidgetItem(room_name)
            attempts_item = QTableWidgetItem(str(data['attempts']))
            win_item = QTableWidgetItem(str(data['win']))
            lose_item = QTableWidgetItem(str(data['lose']))
            
            # 성공률 계산 (타이 제외)
            valid_attempts = data['win'] + data['lose']
            if valid_attempts > 0:
                success_rate = (data['win'] / valid_attempts) * 100
                success_rate_item = QTableWidgetItem(f"{success_rate:.1f}%")
            else:
                success_rate_item = QTableWidgetItem("0.0%")
            
            # 정렬 설정
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            attempts_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            win_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            lose_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            success_rate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # 승패에 따른 색상 설정
            if data['win'] > 0:
                win_item.setForeground(QColor("green"))
            if data['lose'] > 0:
                lose_item.setForeground(QColor("red"))
            
            # 항목 추가
            self.log_table.setItem(row_position, 0, name_item)
            self.log_table.setItem(row_position, 1, attempts_item)
            self.log_table.setItem(row_position, 2, win_item)
            self.log_table.setItem(row_position, 3, lose_item)
            self.log_table.setItem(row_position, 4, success_rate_item)
    
    def get_room_log(self, room_name):
        """특정 방의 로그 데이터 반환"""
        return self.room_logs.get(room_name, None)
    
    def clear_logs(self):
        """모든 로그 초기화"""
        self.room_logs = {}
        self.total_win_count = 0
        self.total_lose_count = 0
        self.win_count_label.setText("0")
        self.lose_count_label.setText("0")
        self.log_table.setRowCount(0)
        
    def set_current_room(self, room_name):
        """
        현재 방 이름 설정 (UIUpdater와의 호환성을 위해 추가)
        실제 RoomLogWidget에서는 방 이름을 단순히 기록만 함
        """
        # 실제 로그 업데이트는 add_bet_result 메서드에서 수행
        pass