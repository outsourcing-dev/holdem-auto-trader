from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
                             QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,QScrollArea)
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
        progress_group.setMinimumHeight(200)  # 최소 높이 설정
        progress_layout = QVBoxLayout()
        
        # 현재 방 표시
        room_layout = QHBoxLayout()
        room_label = QLabel("현재방:")
        room_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.current_room = QLabel("")  # 초기값 비워두기
        self.current_room.setStyleSheet("font-size: 14px;")
        room_layout.addWidget(room_label)
        room_layout.addWidget(self.current_room)
        progress_layout.addLayout(room_layout)
        
        # 진행 테이블 - 스크롤 가능한 테이블 위젯
        self.progress_table = QTableWidget()
        self.progress_table.setMinimumHeight(100)
        self.progress_table.setRowCount(2)  # 2행: 헤더와 마커
        self.progress_table.setColumnCount(1)  # 초기 열 1개 (PICK), 나중에 동적으로 추가
        
        # 헤더 설정
        self.progress_table.setVerticalHeaderLabels(["", ""])  # 행 헤더 비움
        self.progress_table.horizontalHeader().setVisible(False)  # 열 헤더 숨김
        
        # PICK 열 추가
        self.progress_table.setColumnCount(1)
        pick_header_item = QTableWidgetItem("PICK")
        pick_header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        pick_header_item.setBackground(QColor("#f0f0f0"))
        pick_header_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.progress_table.setItem(0, 0, pick_header_item)
        
        # PICK 값 아이템 (초기에는 빈 값)
        self.pick_item = QTableWidgetItem("")
        self.pick_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pick_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.progress_table.setItem(1, 0, self.pick_item)
        
        # 숫자 열 추가 (1부터 20 또는 더 많이)
        max_columns = max(20, self.martin_count + 5)
        self.progress_table.setColumnCount(max_columns + 1)  # PICK + 숫자 열
        
        # 각 열에 대한 설정
        self.step_items = {}
        for i in range(1, max_columns + 1):
            # 헤더 행 - 숫자
            num_item = QTableWidgetItem(str(i))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            num_item.setBackground(QColor("#f0f0f0"))
            num_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            self.progress_table.setItem(0, i, num_item)
            
            # 마커 행 - 초기에는 빈 값
            marker_item = QTableWidgetItem("")
            marker_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            marker_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            self.progress_table.setItem(1, i, marker_item)
            self.step_items[i] = marker_item
        
        # 셀 크기 설정
        self.progress_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.progress_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        # 첫 번째 열 너비 설정
        self.progress_table.setColumnWidth(0, 80)  # PICK 열
        
        # 나머지 열 너비 설정
        for i in range(1, max_columns + 1):
            self.progress_table.setColumnWidth(i, 60)  # 숫자 열
        
        # 행 높이 설정
        self.progress_table.setRowHeight(0, 40)  # 헤더 행
        self.progress_table.setRowHeight(1, 60)  # 마커 행
        
        # 테이블 스타일 설정
        self.progress_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #CCCCCC;
                gridline-color: #DDDDDD;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        
        # 가로 스크롤바 표시
        self.progress_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.progress_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        progress_layout.addWidget(self.progress_table)
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # 결과 테이블 섹션
        results_group = QGroupBox("결과")
        results_layout = QVBoxLayout()
        
        # 결과 테이블
        self.results_table = QTableWidget()
        self.results_table.setMinimumHeight(300)  # 최소 높이 설정
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
        win_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; font-size: 14px; border-radius: 4px;")
        self.win_count_label = QLabel("0")  # 초기값 0
        self.win_count_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        win_layout.addWidget(win_label)
        win_layout.addWidget(self.win_count_label)
        summary_layout.addLayout(win_layout)
        
        # 실패 수
        lose_layout = QHBoxLayout()
        lose_label = QLabel("실패")
        lose_label.setStyleSheet("background-color: #F44336; color: white; padding: 8px; font-size: 14px; border-radius: 4px;")
        self.lose_count_label = QLabel("0")  # 초기값 0
        self.lose_count_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
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
        self.pick_item.setText(pick_value)
        
        # 배경색 설정 (기본: 회색)
        if pick_value == "B":
            self.pick_item.setBackground(QColor("#F44336"))  # 빨간색
            self.pick_item.setForeground(QColor("white"))
        elif pick_value == "P":
            self.pick_item.setBackground(QColor("#2196F3"))  # 파란색
            self.pick_item.setForeground(QColor("white"))
        else:
            self.pick_item.setBackground(QColor("#9E9E9E"))  # 회색
            self.pick_item.setForeground(QColor("white"))
    
    def set_step_marker(self, step, marker):
        """단계별 마커 설정 (X, O, T, 빈칸)"""
        if step in self.step_items:
            item = self.step_items[step]
            item.setText(marker)
            
            # 마커에 따른 색상 설정
            if marker == "X":
                item.setBackground(QColor("#F44336"))  # 빨간색
                item.setForeground(QColor("white"))
            elif marker == "O":
                item.setBackground(QColor("#2196F3"))  # 파란색
                item.setForeground(QColor("white"))
            elif marker == "T":
                item.setBackground(QColor("#4CAF50"))  # 초록색
                item.setForeground(QColor("white"))
            else:
                item.setBackground(QColor("white"))
                item.setForeground(QColor("black"))
    
    def reset_step_markers(self):
        """모든 단계 마커 초기화"""
        for step, item in self.step_items.items():
            item.setText("")
            item.setBackground(QColor("white"))
            item.setForeground(QColor("black"))
    
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