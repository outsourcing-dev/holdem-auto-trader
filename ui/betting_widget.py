from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
                            QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, 
                            QGroupBox, QScrollArea, QApplication)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from utils.settings_manager import SettingsManager

class BettingWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.settings_manager = SettingsManager()
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        self.current_martin_step = 0
        self.current_room_results = []  # 현재 방에서의 결과 기록 (O, X, T)
        
        main_layout = QVBoxLayout()
        
        # 진행 섹션 (현재 방 + PICK 표시 + 현재 방 배팅 결과)
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
        
        # 셀 크기 설정
        self.progress_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.progress_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
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
        
        # 테이블 초기화
        self.initialize_betting_widget()
        
        progress_layout.addWidget(self.progress_table)
        
        # 현재 방 결과 요약
        room_results_layout = QHBoxLayout()
        
        # 성공(O) 수
        self.success_count = 0
        success_layout = QHBoxLayout()
        success_label = QLabel("성공(O)")
        success_label.setStyleSheet("background-color: #2196F3; color: white; padding: 4px; font-size: 12px; border-radius: 4px;")
        self.success_count_label = QLabel("0")
        self.success_count_label.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px;")
        success_layout.addWidget(success_label)
        success_layout.addWidget(self.success_count_label)
        room_results_layout.addLayout(success_layout)
        
        # 실패(X) 수
        self.fail_count = 0
        fail_layout = QHBoxLayout()
        fail_label = QLabel("실패(X)")
        fail_label.setStyleSheet("background-color: #F44336; color: white; padding: 4px; font-size: 12px; border-radius: 4px;")
        self.fail_count_label = QLabel("0")
        self.fail_count_label.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px;")
        fail_layout.addWidget(fail_label)
        fail_layout.addWidget(self.fail_count_label)
        room_results_layout.addLayout(fail_layout)
        
        # 타이(T) 수
        self.tie_count = 0
        tie_layout = QHBoxLayout()
        tie_label = QLabel("타이(T)")
        tie_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 4px; font-size: 12px; border-radius: 4px;")
        self.tie_count_label = QLabel("0")
        self.tie_count_label.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px;")
        tie_layout.addWidget(tie_label)
        tie_layout.addWidget(self.tie_count_label)
        room_results_layout.addLayout(tie_layout)
        
        progress_layout.addLayout(room_results_layout)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        self.setLayout(main_layout)
        
    def update_settings(self):
        """설정이 변경되었을 때 호출"""
        # 새로운 마틴 설정 불러오기
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        
        # 테이블 열 개수 업데이트
        max_columns = max(20, self.martin_count + 5)
        current_columns = self.progress_table.columnCount() - 1  # PICK 열 제외
        
        # 열 수가 부족하면 추가
        if current_columns < max_columns:
            for i in range(current_columns + 1, max_columns + 1):
                # 열 추가
                self.progress_table.setColumnCount(i + 1)  # +1은 PICK 열 때문
                
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
                
                # 열 너비 설정
                self.progress_table.setColumnWidth(i, 60)  # 숫자 열
                
        # 로그 출력
        print(f"[INFO] 마틴 설정 업데이트 - 단계 수: {self.martin_count}, 금액: {self.martin_amounts}")
    
    def update_current_room(self, room_name):
        """현재 방 이름 업데이트"""
        self.current_room.setText(room_name)
    
    def reset_room_results(self):
        """현재 방 결과 초기화"""
        self.current_room_results = []
        self.success_count = 0
        self.fail_count = 0
        self.tie_count = 0
        self.success_count_label.setText("0")
        self.fail_count_label.setText("0")
        self.tie_count_label.setText("0")
        self.reset_step_markers()
    
    def set_pick(self, pick_value):
        """PICK 값 설정 (B, P 등)"""
        # None이나 빈 문자열 처리
        if pick_value is None or pick_value == "":
            pick_value = "N"
        
        # N 값 처리
        if pick_value == "N":
            self.pick_item.setText(pick_value)
            self.pick_item.setBackground(QColor("#9E9E9E"))  # 회색
            self.pick_item.setForeground(QColor("white"))
            return
            
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
        print(f"[DEBUG] set_step_marker 호출됨 - 단계: {step}, 마커: {marker}")
        
        # 마커 설정
        if step in self.step_items:
            item = self.step_items[step]
            print(f"[DEBUG] step_items에서 해당 단계 항목 찾음: {step}")
            
            # 기존 아이템 텍스트 및 색상 설정
            item.setText(marker)
            
            # 마커에 따른 색상 설정
            if marker == "X":
                item.setBackground(QColor("#F44336"))  # 빨간색
                item.setForeground(QColor("white"))
                # 실패 수 증가
                self.fail_count += 1
                self.fail_count_label.setText(str(self.fail_count))
                # 결과 기록
                self.current_room_results.append("X")
                print(f"[DEBUG] 실패(X) 마커 설정 완료 - 총 실패 수: {self.fail_count}")
            elif marker == "O":
                item.setBackground(QColor("#2196F3"))  # 파란색
                item.setForeground(QColor("white"))
                # 성공 수 증가
                self.success_count += 1
                self.success_count_label.setText(str(self.success_count))
                # 결과 기록
                self.current_room_results.append("O")
                print(f"[DEBUG] 성공(O) 마커 설정 완료 - 총 성공 수: {self.success_count}")
            elif marker == "T":
                item.setBackground(QColor("#4CAF50"))  # 초록색
                item.setForeground(QColor("white"))
                # 타이 수 증가
                self.tie_count += 1
                self.tie_count_label.setText(str(self.tie_count))
                # 결과 기록
                self.current_room_results.append("T")
                print(f"[DEBUG] 무승부(T) 마커 설정 완료 - 총 무승부 수: {self.tie_count}")
            else:
                item.setBackground(QColor("white"))
                item.setForeground(QColor("black"))
                print(f"[DEBUG] 빈 마커 설정 완료")
            
            # UI 업데이트 강제 실행 (명시적으로 업데이트)
            from PyQt6.QtWidgets import QApplication
            self.progress_table.viewport().update()
            self.progress_table.repaint()
            QApplication.processEvents()
            
            print(f"[DEBUG] UI 업데이트 완료: 단계 {step}에 {marker} 마커 설정됨")
        else:
            print(f"[WARNING] 잘못된 단계 번호: {step} (step_items 키에 없음)")
            # 가능한 step 키 목록 출력
            print(f"[DEBUG] 가능한 step_items 키: {list(self.step_items.keys())}")
            
            # 범위를 벗어난 경우 가능한 범위 내에서 설정 시도
            if isinstance(step, int) and step > 0:
                max_step = max(self.step_items.keys()) if self.step_items else 0
                if max_step > 0 and step > max_step:
                    print(f"[INFO] 범위를 벗어난 단계({step})를 최대 단계({max_step})로 설정합니다.")
                    self.set_step_marker(max_step, marker)
                elif 1 in self.step_items and step < 1:
                    print(f"[INFO] 범위를 벗어난 단계({step})를 최소 단계(1)로 설정합니다.")
                    self.set_step_marker(1, marker)
            
    def reset_step_markers(self):
        """모든 단계 마커 초기화"""
        for step, item in self.step_items.items():
            item.setText("")
            item.setBackground(QColor("white"))
            item.setForeground(QColor("black"))
    
    def get_room_results_summary(self):
        """현재 방의 결과 요약 반환"""
        return {
            "success": self.success_count,
            "fail": self.fail_count,
            "tie": self.tie_count,
            "total": len(self.current_room_results)
        }
        
    def clear_results(self):
        """
        호환성을 위한 메서드 - reset_room_results로 대체됨
        """
        self.reset_room_results()
        
    def add_raw_result(self, no, room_name, step, result):
        """
        배팅 결과를 추가하는 메서드
        
        Args:
            no (int): 결과 번호
            room_name (str): 방 이름
            step (int): 마틴 단계
            result (str): 결과 텍스트 ("적중", "실패", "무승부")
        """
        # 결과에 따른 마커 변환
        marker = ""
        if result == "적중":
            marker = "O"
        elif result == "실패":
            marker = "X"
        elif result == "무승부":
            marker = "T"
        
        # 마커 설정 
        if marker:
            self.set_step_marker(step, marker)
            
        # 현재 방 이름 업데이트 (첫 결과인 경우)
        if not self.current_room.text() and room_name:
            self.current_room.setText(room_name)
            
    def initialize_betting_widget(self):
        """
        베팅 위젯을 초기화합니다.
        테이블 셀과 step_items가 모두 제대로 설정되어 있는지 확인합니다.
        """
        print("[DEBUG] 베팅 위젯 초기화 시작")
        
        # 테이블 초기화
        self.progress_table.clear()
        self.progress_table.setRowCount(2)  # 2행: 헤더와 마커
        
        # 숫자 열 추가 (1부터 20 또는 더 많이)
        max_columns = max(20, self.martin_count + 5)
        self.progress_table.setColumnCount(max_columns + 1)  # PICK + 숫자 열
        
        # PICK 열 추가
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
        
        # 초기화된 step_items 딕셔너리
        self.step_items = {}
        
        # 각 열에 대한 설정
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
        
        # 첫 번째 열 너비 설정
        self.progress_table.setColumnWidth(0, 80)  # PICK 열
        
        # 나머지 열 너비 설정
        for i in range(1, max_columns + 1):
            self.progress_table.setColumnWidth(i, 60)  # 숫자 열
        
        # 행 높이 설정
        self.progress_table.setRowHeight(0, 40)  # 헤더 행
        self.progress_table.setRowHeight(1, 60)  # 마커 행
        
        print(f"[DEBUG] 베팅 위젯 초기화 완료 - step_items 키: {list(self.step_items.keys())}")