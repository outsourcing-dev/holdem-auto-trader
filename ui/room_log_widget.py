from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

class RoomLogWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        # 방별 로그 데이터를 저장하는 딕셔너리
        # {방문 ID: {'room_name': 방이름, 'attempts': 시도횟수, 'win': 승리횟수, 'lose': 패배횟수, 'tie': 타이횟수}}
        self.room_logs = {}
        
        # 현재 방문 ID (방 입장 시마다 새로 생성)
        self.current_visit_id = None
        
        # 방문 카운터 (방 이동 시에만 증가)
        self.visit_counter = 0
        
        # 전체 통계
        self.total_win_count = 0
        self.total_lose_count = 0
        
        main_layout = QVBoxLayout()
        
        # 로그 섹션
        log_group = QGroupBox("방 로그")
        log_layout = QVBoxLayout()
        
        # 로그 테이블
        # self.log_table = QTableWidget()
        # self.log_table.setMinimumHeight(300)  # 최소 높이 설정
        # self.log_table.setColumnCount(5)  # 방 이름, 시도 횟수, 승, 패, 성공률
        # self.log_table.setHorizontalHeaderLabels(["방 이름", "시도", "승", "패", "성공률"])
        # self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # self.log_table.setRowCount(0)  # 초기에는 데이터 없음
        
        self.log_table = QTableWidget()
        self.log_table.setMinimumHeight(300)  # 최소 높이 설정
        self.log_table.setColumnCount(5)  # 방 이름, 시도 횟수, 승, 패, 성공률
        self.log_table.setHorizontalHeaderLabels(["방 이름", "시도", "승", "패", "성공률"])

        # 각 컬럼의 너비를 명시적으로 설정
        self.log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # 방 이름 컬럼은 남은 공간을 모두 차지
        self.log_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # 시도 컬럼은 고정 너비
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # 승 컬럼은 고정 너비
        self.log_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # 패 컬럼은 고정 너비
        self.log_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # 성공률 컬럼은 고정 너비

        # 각 열의 너비 설정 (픽셀 단위)
        self.log_table.setColumnWidth(1, 80)  # 시도 열 너비
        self.log_table.setColumnWidth(2, 80)  # 승 열 너비
        self.log_table.setColumnWidth(3, 80)  # 패 열 너비
        self.log_table.setColumnWidth(4, 110)  # 성공률 열 너비

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
    
    def create_new_visit_id(self, room_name):
        """
        새 방문 ID 생성 - 방 이름 + 카운터
        
        Args:
            room_name (str): 방 이름
            
        Returns:
            str: 생성된 방문 ID
        """
        self.visit_counter += 1
        visit_id = f"{self.visit_counter}_{room_name}"
        return visit_id
    
    def add_bet_result(self, room_name, is_win, is_tie=False):
        """
        배팅 결과 추가 - 방별로 한 행씩만 표시하고 통계 업데이트
        
        Args:
            room_name (str): 방 이름
            is_win (bool): 승리 여부
            is_tie (bool): 타이(무승부) 여부
        """
        # 방문 ID가 없는 경우 아무 작업도 하지 않음
        if self.current_visit_id is None or self.current_visit_id not in self.room_logs:
            return
        
        # 현재 방문 로그 카운트 증가
        self.room_logs[self.current_visit_id]['attempts'] += 1
        
        # 승패 기록
        if is_tie:
            self.room_logs[self.current_visit_id]['tie'] += 1
        elif is_win:
            self.room_logs[self.current_visit_id]['win'] += 1
            self.total_win_count += 1
            self.win_count_label.setText(str(self.total_win_count))
        else:
            self.room_logs[self.current_visit_id]['lose'] += 1
            self.total_lose_count += 1
            self.lose_count_label.setText(str(self.total_lose_count))
        
        # 테이블 업데이트
        self.update_table()
    
    def update_table(self):
        """로그 테이블 업데이트"""
        # 테이블 초기화
        self.log_table.setRowCount(0)
        
        # 각 방의 로그 데이터를 행으로 추가 (최신 방문부터 표시)
        sorted_logs = sorted(self.room_logs.items(), 
                            key=lambda x: x[0], 
                            reverse=True)
        
        for visit_id, data in sorted_logs:
            row_position = self.log_table.rowCount()
            self.log_table.insertRow(row_position)
            
            # 항목 생성
            name_item = QTableWidgetItem(data['room_name'])
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
    
    def get_room_log(self, visit_id):
        """특정 방문의 로그 데이터 반환"""
        return self.room_logs.get(visit_id, None)
    
    def clear_logs(self):
        """모든 로그 초기화"""
        self.room_logs = {}
        self.current_visit_id = None
        self.total_win_count = 0
        self.total_lose_count = 0
        self.win_count_label.setText("0")
        self.lose_count_label.setText("0")
        self.log_table.setRowCount(0)
        
    def set_current_room(self, room_name):
        """
        현재 방 이름 설정 - 방 이름이 변경된 경우에만 새 방문 ID 생성
        
        Args:
            room_name (str): 방 이름
        """
        # 방 이름에서 게임 수와 베팅 정보 제거 (첫 줄만 사용)
        if room_name:
            base_room_name = room_name.split('\n')[0].split('(')[0].strip()
        else:
            base_room_name = "알 수 없는 방"
        
        # 이전 방문이 없거나 방 이름이 변경된 경우에만 새 방문 ID 생성
        create_new_visit = False
        
        if self.current_visit_id is None:
            create_new_visit = True
        elif self.current_visit_id in self.room_logs:
            # 기본 방 이름만 비교 (게임 수와 베팅 정보 무시)
            current_base_name = self.room_logs[self.current_visit_id]['room_name'].split('\n')[0].split('(')[0].strip()
            create_new_visit = current_base_name != base_room_name
        
        if create_new_visit:
            self.current_visit_id = self.create_new_visit_id(base_room_name)
            # 새 방문 로그 초기화
            self.room_logs[self.current_visit_id] = {
                'room_name': base_room_name,
                'attempts': 0,
                'win': 0,
                'lose': 0,
                'tie': 0
            }
            
            # 테이블 업데이트
            self.update_table()