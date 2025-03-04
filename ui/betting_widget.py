from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
                             QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
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
        
        # 진행 섹션 (현재 방 + PICK 표시)
        progress_group = QGroupBox("진행")
        progress_layout = QVBoxLayout()
        
        # 현재 방 표시
        room_layout = QHBoxLayout()
        room_label = QLabel("현재방")
        self.current_room = QLabel("") # 초기값 비워두기
        room_layout.addWidget(room_label)
        room_layout.addWidget(self.current_room)
        progress_layout.addLayout(room_layout)
        
        # PICK 표시와 X/O 체크
        pick_grid = QGridLayout()
        
        # PICK 헤더 설정
        pick_label = QLabel("PICK")
        pick_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pick_grid.addWidget(pick_label, 0, 0)
        
        # 베팅 선택 표시 (B, P 등)
        self.pick_label = QLabel("")
        self.pick_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pick_label.setStyleSheet("color: white; border-radius: 15px; min-width: 30px; min-height: 30px;")
        pick_grid.addWidget(self.pick_label, 1, 0)
        
        # 1-5 칸과 X/O 체크
        self.step_markers = {}
        for i in range(1, 6):
            # 숫자 헤더
            num_label = QLabel(str(i))
            num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pick_grid.addWidget(num_label, 0, i)
            
            # X/O 표시 (초기에는 빈칸)
            mark = QLabel("")
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pick_grid.addWidget(mark, 1, i)
            self.step_markers[i] = mark
        
        progress_layout.addLayout(pick_grid)
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # 결과 테이블 섹션
        results_group = QGroupBox("결과")
        results_layout = QVBoxLayout()
        
        # 결과 테이블
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["NO", "방이름", "단계", "승패"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setRowCount(0)  # 초기에는 데이터 없음
        
        results_layout.addWidget(self.results_table)
        
        # 승패 요약 표시
        summary_layout = QHBoxLayout()
        
        # 적중 수
        win_layout = QHBoxLayout()
        win_label = QLabel("적중")
        win_label.setStyleSheet("background-color: gray; color: white; padding: 5px;")
        self.win_count_label = QLabel("0")  # 초기값 0
        win_layout.addWidget(win_label)
        win_layout.addWidget(self.win_count_label)
        summary_layout.addLayout(win_layout)
        
        # 실패 수
        lose_layout = QHBoxLayout()
        lose_label = QLabel("실패")
        lose_label.setStyleSheet("background-color: gray; color: white; padding: 5px;")
        self.lose_count_label = QLabel("0")  # 초기값 0
        lose_layout.addWidget(lose_label)
        lose_layout.addWidget(self.lose_count_label)
        summary_layout.addLayout(lose_layout)
        
        results_layout.addLayout(summary_layout)
        results_group.setLayout(results_layout)
        main_layout.addWidget(results_group)
        
        self.setLayout(main_layout)
    
    def update_settings(self):
        """설정이 변경되었을 때 호출"""
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
    
    def update_current_room(self, room_name):
        """현재 방 이름 업데이트"""
        self.current_room.setText(room_name)
    
    def set_pick(self, pick_value):
        """PICK 값 설정 (B, P 등)"""
        self.pick_label.setText(pick_value)
        # 배경색 설정 (기본: 빨간색)
        if pick_value == "B":
            self.pick_label.setStyleSheet("background-color: red; color: white; border-radius: 15px; min-width: 30px; min-height: 30px;")
        elif pick_value == "P":
            self.pick_label.setStyleSheet("background-color: blue; color: white; border-radius: 15px; min-width: 30px; min-height: 30px;")
        else:
            self.pick_label.setStyleSheet("background-color: gray; color: white; border-radius: 15px; min-width: 30px; min-height: 30px;")
    
    def set_step_marker(self, step, marker):
        """단계별 마커 설정 (X, O, 빈칸)"""
        if step in self.step_markers:
            self.step_markers[step].setText(marker)
            # 마커에 따른 색상 설정
            if marker == "X":
                self.step_markers[step].setStyleSheet("color: black;")
            elif marker == "O":
                self.step_markers[step].setStyleSheet("color: blue;")
            else:
                self.step_markers[step].setStyleSheet("")
    
    def reset_step_markers(self):
        """모든 단계 마커 초기화"""
        for step in self.step_markers:
            self.step_markers[step].setText("")
            self.step_markers[step].setStyleSheet("")
    
    def clear_results(self):
        """결과 테이블 초기화"""
        self.results_table.setRowCount(0)
        self.win_count = 0
        self.lose_count = 0
        self.win_count_label.setText("0")
        self.lose_count_label.setText("0")
    
    def add_result(self, no, room_name, step, is_win):
        """결과 추가"""
        # 상단에 새 행 추가
        self.results_table.insertRow(0)
        
        # 항목 생성
        no_item = QTableWidgetItem(str(no))
        room_item = QTableWidgetItem(room_name)
        step_item = QTableWidgetItem(str(step))
        result_text = "적중" if is_win else "실패"
        result_item = QTableWidgetItem(result_text)
        
        # 정렬 설정
        no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        room_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        step_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        result_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 승패에 따른 색상 설정
        if is_win:
            result_item.setForeground(QColor("green"))
            self.win_count += 1
            self.win_count_label.setText(str(self.win_count))
        else:
            result_item.setForeground(QColor("red"))
            self.lose_count += 1
            self.lose_count_label.setText(str(self.lose_count))
        
        # 항목 추가
        self.results_table.setItem(0, 0, no_item)
        self.results_table.setItem(0, 1, room_item)
        self.results_table.setItem(0, 2, step_item)
        self.results_table.setItem(0, 3, result_item)
        
        # 최대 100개로 제한
        if self.results_table.rowCount() > 100:
            self.results_table.removeRow(100)
            
    def add_raw_result(self, no, room_name, step, result_text):
        """결과 텍스트 그대로 추가 (적중/실패 문자열을 직접 사용)"""
        # 상단에 새 행 추가
        self.results_table.insertRow(0)
        
        # 항목 생성
        no_item = QTableWidgetItem(str(no))
        room_item = QTableWidgetItem(room_name)
        step_item = QTableWidgetItem(str(step))
        result_item = QTableWidgetItem(result_text)
        
        # 정렬 설정
        no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        room_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        step_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        result_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 승패에 따른 색상 및 카운트 설정
        if result_text == "적중":
            result_item.setForeground(QColor("green"))
            self.win_count += 1
            self.win_count_label.setText(str(self.win_count))
        else:
            result_item.setForeground(QColor("red"))
            self.lose_count += 1
            self.lose_count_label.setText(str(self.lose_count))
        
        # 항목 추가
        self.results_table.setItem(0, 0, no_item)
        self.results_table.setItem(0, 1, room_item)
        self.results_table.setItem(0, 2, step_item)
        self.results_table.setItem(0, 3, result_item)
        
        # 최대 100개로 제한
        if self.results_table.rowCount() > 100:
            self.results_table.removeRow(100)