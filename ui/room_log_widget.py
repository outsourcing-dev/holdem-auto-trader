import time
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QGridLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from utils.room_loader import extract_room_base_name

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
        
        # 방문 순서를 추적하는 리스트
        self.visit_order = []
        
        # 전체 통계
        self.total_win_count = 0
        self.total_lose_count = 0
        self.total_tie_count = 0
        
        main_layout = QVBoxLayout()
        
        # 로그 섹션
        log_group = QGroupBox("로그")
        log_layout = QVBoxLayout()
        
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
        
        # ✅ 총 승패 요약 표시 레이아웃을 QGridLayout으로 변경
        summary_layout = QGridLayout()

        # ✅ 총 적중 수
        win_layout = QHBoxLayout()
        win_label = QLabel("적중")
        win_label.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px; font-size: 14px; border-radius: 4px;")
        win_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 🔥 라벨 중앙 정렬
        self.win_count_label = QLabel("0")  # 초기값 0
        self.win_count_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        self.win_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 🔥 숫자 중앙 정렬
        win_layout.addWidget(win_label)
        win_layout.addWidget(self.win_count_label)

        # ✅ 총 실패 수
        lose_layout = QHBoxLayout()
        lose_label = QLabel("실패")
        lose_label.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; padding: 8px; font-size: 14px; border-radius: 4px;")
        lose_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 🔥 라벨 중앙 정렬
        self.lose_count_label = QLabel("0")  # 초기값 0
        self.lose_count_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 8px;")
        self.lose_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 🔥 숫자 중앙 정렬
        lose_layout.addWidget(lose_label)
        lose_layout.addWidget(self.lose_count_label)

        # ✅ QGridLayout에 추가 (한 줄에 적중, 실패 배치)
        summary_layout.addLayout(win_layout, 0, 0)
        summary_layout.addLayout(lose_layout, 0, 1)

        # ✅ 각 열이 동일한 비율로 크기를 차지하도록 설정
        summary_layout.setColumnStretch(0, 1)
        summary_layout.setColumnStretch(1, 1)

        # ✅ 부모 레이아웃에 추가
        log_layout.addLayout(summary_layout)

        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        self.setLayout(main_layout)
        self.has_changed_room = False

    def create_new_visit_id(self, room_name):
        """
        새 방문 ID 생성 - 방 이름 + 카운터
        이미 있는 방 이름이면 카운터만 증가시키고 기존 prefix 유지
        
        Args:
            room_name (str): 방 이름
                
        Returns:
            str: 생성된 방문 ID
        """
        # 이미 방문 중인 방인지 확인 (현재 로그에 있는 방 이름과 동일한지)
        for visit_id, data in self.room_logs.items():
            if data['room_name'] == room_name and visit_id in self.visit_order:
                # 마지막으로 방문한 방인지 확인 (방문 순서의 마지막 요소)
                if self.visit_order and self.visit_order[-1] == visit_id:
                    # 같은 방에 계속 있는 경우, 기존 ID 재사용
                    print(f"[DEBUG] 기존 방문 ID 재사용: {visit_id}, 방: {room_name}")
                    return visit_id
        
        # 새 방문이면 카운터 증가
        self.visit_counter += 1
        
        # 정렬을 위해 숫자 부분을 0으로 패딩 (최대 4자리)
        visit_id = f"{self.visit_counter:04d}_{room_name}"
        
        # 방문 순서 리스트에 추가
        self.visit_order.append(visit_id)
        
        print(f"[DEBUG] 새 방문 ID 생성: {visit_id}, 현재 카운터: {self.visit_counter}")
        return visit_id
    
    # ui/room_log_widget.py의 add_bet_result 메서드 수정
    def add_bet_result(self, room_name, is_win, is_tie):
        """
        베팅 결과 추가 - 중복 방지 로직 강화
        
        Args:
            room_name (str): 방 이름
            is_win (bool): 승리 여부
            is_tie (bool): 무승부 여부
        """
        # 마지막으로 기록된 결과 시간 확인 (중복 방지)
        current_time = time.time()
        if hasattr(self, 'last_recorded_time') and current_time - self.last_recorded_time < 1.0:
            # 1초 이내에 중복 호출되면 무시
            if hasattr(self, 'logger'):
                self.logger.debug("1초 이내 중복 호출 무시")
            else:
                print("[DEBUG] 1초 이내 중복 호출 무시")
            return
            
        # 결과 시간 기록
        self.last_recorded_time = current_time
        
        # 현재 로그 항목 없으면 생성 (중요: 항상 확인하고 필요시 생성)
        if not hasattr(self, 'current_room_name') or self.current_room_name != room_name:
            # 방 이름이 바뀌었을 때만 새로 설정 (방문 플래그는 False로 유지)
            self.set_current_room(room_name, is_new_visit=False)
        
        # 현재 방에 대한 베팅 결과 기록
        result_type = "무승부" if is_tie else "적중" if is_win else "실패"
        
        # 로그 항목 업데이트
        self._update_last_log_item(result_type)
        
        # 디버그 로그 추가
        print(f"[DEBUG] 방 로그 기록: 방={room_name}, 결과={result_type}, 현재 항목 ID={self.current_visit_id}")

    # ui/room_log_widget.py의 set_current_room 메서드 수정
    def set_current_room(self, room_name, is_new_visit=False):
        """
        현재 방 설정 - 중복 방지 로직 강화
        
        Args:
            room_name (str): 방 이름
            is_new_visit (bool): 새 방문 여부
        """
        # 이미 같은 방에 대한 기록이 진행 중이면 has_changed_room 플래그만 업데이트
        if hasattr(self, 'current_room_name') and self.current_room_name == room_name:
            # 방 이름이 같으면 has_changed_room 플래그만 업데이트하고 리턴
            self.has_changed_room = is_new_visit
            return
            
        # 디버그 로그
        print(f"[DEBUG] 방 설정: 이전={getattr(self, 'current_room_name', None)}, 새로운={room_name}, 새방문={is_new_visit}")
        
        # 방 이름 업데이트
        self.current_room_name = room_name
        self.has_changed_room = is_new_visit
        
        # 새 방문일 때만 로그 추가 (같은 방 재방문은 제외)
        if is_new_visit:
            # 방 로그 항목 추가
            self._add_room_log_item(room_name)
        else:
            # 같은 방에 계속 있는 경우에도 로그 항목이 없다면 추가
            if not self.current_visit_id or self.current_visit_id not in self.room_logs:
                self._add_room_log_item(room_name)
                print(f"[DEBUG] 같은 방 계속 있음 (로그 항목 미존재로 추가): {room_name}")
            else:
                print(f"[DEBUG] 같은 방 계속 있음 (로그 항목 존재): {room_name}")
                
    def update_table(self):
        """로그 테이블 업데이트 - 최신 방문 순으로 정렬하되, 번호는 오래된 방이 1번부터 시작"""
        # 테이블 초기화
        self.log_table.setRowCount(0)
        
        # 실제 베팅이 있는 방만 필터링 (시도 횟수가 1 이상인 방)
        valid_logs = {visit_id: data for visit_id, data in self.room_logs.items() 
                    if data['attempts'] > 0}
        
        # 방문 순서를 기준으로 정렬 (최신 방문이 맨 위에 오도록)
        # 방문 순서 리스트를 역순으로 정렬해서 최신 방문이 앞에 오도록 함
        sorted_visit_ids = self.visit_order.copy()
        sorted_visit_ids.reverse()
        
        # 방문 순서가 있는 로그만 먼저 처리
        sorted_logs = []
        for visit_id in sorted_visit_ids:
            if visit_id in valid_logs:
                sorted_logs.append((visit_id, valid_logs[visit_id]))
                # 처리한 로그는 목록에서 제거
                valid_logs.pop(visit_id)
        
        # 방문 순서에 없는 나머지 로그들도 추가 (만약 있다면)
        if valid_logs:
            for visit_id, data in valid_logs.items():
                sorted_logs.append((visit_id, data))
        
        # 표시할 방 개수
        total_rooms = len(sorted_logs)
        
        # 테이블의 행 수 설정
        self.log_table.setRowCount(total_rooms)
        
        # 최신 방문이 테이블 위쪽에 오도록 추가하되, 번호는 가장 오래된 방이 1번
        for index, (visit_id, data) in enumerate(sorted_logs):
            # 항목 생성 - 방 이름에 번호 추가 (가장 오래된 방이 1번)
            # 현재 정렬은 최신 방이 앞에 있으므로, 번호는 반대로 계산
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
                win_item.setForeground(QColor("blue"))
            if data['lose'] > 0:
                lose_item.setForeground(QColor("red"))
            
            # 항목 추가 - 최신 방이 맨 위에 오도록 행 번호 할당
            row = index  # 이제 index가 행 번호가 됨 (정렬된 순서대로)
            self.log_table.setItem(row, 0, name_item)
            self.log_table.setItem(row, 1, attempts_item)
            self.log_table.setItem(row, 2, win_item)
            self.log_table.setItem(row, 3, lose_item)
            self.log_table.setItem(row, 4, success_rate_item)
        
        self.log_table.setVerticalHeaderLabels([str(i) for i in range(total_rooms, 0, -1)])

    def get_room_log(self, visit_id):
        """특정 방문의 로그 데이터 반환"""
        return self.room_logs.get(visit_id, None)
    
    def clear_logs(self):
        """모든 로그 초기화"""
        self.room_logs = {}
        self.current_visit_id = None
        self.visit_counter = 0
        self.visit_order = []  # 방문 순서 리스트도 초기화
        self.total_win_count = 0
        self.total_lose_count = 0
        self.total_tie_count = 0
        self.win_count_label.setText("0")
        self.lose_count_label.setText("0")
        self.log_table.setRowCount(0)

    # ui/room_log_widget.py의 _add_room_log_item 메서드 수정
    def _add_room_log_item(self, room_name):
        """
        방 로그 항목 추가
        
        Args:
            room_name (str): 방 이름
        """
        # 새 방문 ID 생성
        self.current_visit_id = self.create_new_visit_id(room_name)
        
        # 이미 있는 로그 항목인지 확인
        if self.current_visit_id in self.room_logs:
            # 디버그 로그
            print(f"[DEBUG] 이미 존재하는 방문 ID 재사용: {self.current_visit_id}")
            return
        
        # 새 로그 항목 생성
        self.room_logs[self.current_visit_id] = {
            'room_name': room_name,
            'attempts': 0,
            'win': 0,
            'lose': 0,
            'tie': 0
        }
        
        # 테이블 업데이트
        self.update_table()
        
        # 디버그 로그
        print(f"[DEBUG] 새 방 로그 항목 추가: {self.current_visit_id}, 방: {room_name}")

    # ui/room_log_widget.py의 _update_last_log_item 메서드 수정
    def _update_last_log_item(self, result_type):
        """
        현재 방의 로그 항목에 결과 업데이트
        
        Args:
            result_type (str): 결과 타입 ("적중", "실패", "무승부")
        """
        # 현재 방의 로그 항목 확인
        if self.current_visit_id and self.current_visit_id in self.room_logs:
            # 디버그 로그
            prev_win = self.room_logs[self.current_visit_id]['win']
            prev_lose = self.room_logs[self.current_visit_id]['lose']
            prev_tie = self.room_logs[self.current_visit_id]['tie']
            print(f"[DEBUG] 로그 업데이트 전: 승={prev_win}, 패={prev_lose}, 무={prev_tie}")
            
            # 결과 타입에 따라 카운터 증가
            if result_type == "적중":
                self.room_logs[self.current_visit_id]['win'] += 1
                # 전체 카운터도 증가
                self.total_win_count += 1
            elif result_type == "실패":
                self.room_logs[self.current_visit_id]['lose'] += 1
                # 전체 카운터도 증가
                self.total_lose_count += 1
            elif result_type == "무승부":
                self.room_logs[self.current_visit_id]['tie'] += 1
                # 전체 카운터도 증가
                self.total_tie_count += 1
                
            # 시도 횟수 증가
            self.room_logs[self.current_visit_id]['attempts'] += 1
            
            # UI 업데이트
            self.win_count_label.setText(str(self.total_win_count))
            self.lose_count_label.setText(str(self.total_lose_count))
            
            # 테이블 업데이트
            self.update_table()
            
            # 디버그 로그
            new_win = self.room_logs[self.current_visit_id]['win']
            new_lose = self.room_logs[self.current_visit_id]['lose']
            new_tie = self.room_logs[self.current_visit_id]['tie']
            print(f"[DEBUG] 로그 업데이트 후: 승={new_win}, 패={new_lose}, 무={new_tie}")
        else:
            # 로그 항목이 없는 경우 경고
            print(f"[WARNING] 결과 기록 실패: 현재 방문 ID가 없거나 로그 항목이 없음 (ID={self.current_visit_id})")
            
    def should_create_new_visit_id(self, base_room_name):
        """
        새 방문 ID 생성 여부 결정 (무승부 시 현재 방에 계속 있어야 함)
        
        Args:
            base_room_name (str): 방 기본 이름
            
        Returns:
            bool: 새 방문 ID 생성 여부
        """
        # 현재 방문 ID가 없는 경우 항상 새로 생성
        if self.current_visit_id is None:
            return True
            
        # 현재 방문 ID가 있는 경우, 기존 방 이름과 비교
        if self.current_visit_id in self.room_logs:
            # 기본 방 이름만 비교 (첫 단어가 같으면 같은 방으로 간주)
            current_room_name = self.room_logs[self.current_visit_id]['room_name']
            
            # 직접 방 이름 비교 - 방 이름이 완전히 같으면 같은 방
            if current_room_name == base_room_name:
                # 같은 방 이름이면 새 ID를 생성하지 않음
                return False
                
            # 기본 이름만 추출하여 비교 (예: "스피드 바카라 Q"에서 "Q"까지만)
            current_parts = current_room_name.split()
            new_parts = base_room_name.split()
            
            # 기본 방 이름의 길이가 다르면 다른 방
            if len(current_parts) != len(new_parts):
                return True
                
            # 모든 단어가 같은지 확인
            for i in range(min(len(current_parts), len(new_parts))):
                if current_parts[i] != new_parts[i]:
                    return True
                    
            # 모든 비교를 통과했으면 같은 방으로 간주
            return False
            
        return True