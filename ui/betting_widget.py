# ui/betting_widget.py 수정
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, 
                            QTableWidget, QTableWidgetItem, QHeaderView, 
                            QGroupBox,QSizePolicy,QGridLayout)

from PyQt6.QtCore import Qt,QRect
from PyQt6.QtGui import QColor, QFont
from utils.settings_manager import SettingsManager
from PyQt6.QtWidgets import QStyledItemDelegate, QStyle
from PyQt6.QtGui import QPen, QBrush

class CircleStyleTable(QTableWidget):
    """원 스타일을 지원하는 테이블 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def paintEvent(self, event):
        """기본 paintEvent를 오버라이드하지 않고 별도 처리"""
        super().paintEvent(event)
        
    def drawItemWithCircle(self, painter, option, index):
        """원형 배경으로 아이템 그리기"""
        painter.save()
        
        # 배경 색상 및 텍스트 색상 가져오기
        bgColor = index.data(Qt.ItemDataRole.BackgroundRole)
        fgColor = index.data(Qt.ItemDataRole.ForegroundRole)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        
        # 원 그리기 영역 계산
        rect = option.rect
        diameter = min(rect.width(), rect.height()) - 8  # 마진 8픽셀
        circle_rect = QRect(
            rect.left() + (rect.width() - diameter) // 2,
            rect.top() + (rect.height() - diameter) // 2,
            diameter, diameter
        )
        
        # 원 그리기
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(bgColor))
        painter.drawEllipse(circle_rect)
        
        # 텍스트 그리기
        painter.setPen(QColor(fgColor))
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        
        painter.restore()

# 테이블 아이템 델리게이트 클래스 추가 (원 그리기 기능 구현)
class CircleItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        """아이템 그리기 - B와 P에 따라 색상을 다르게 설정"""
        pick_type = index.data(Qt.ItemDataRole.UserRole)

        # P와 B에 따른 배경색 설정
        if pick_type == "circle-P":
            bgColor = QColor("#2196F3")  # 파란색
            fgColor = QColor("white")    # 흰색 글씨
        elif pick_type == "circle-B":
            bgColor = QColor("#F44336")  # 빨간색
            fgColor = QColor("white")    # 흰색 글씨
        else:
            super().paint(painter, option, index)
            return

        # 선택 상태 처리 (선택 시 강조)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # 원형 영역 계산
        rect = option.rect
        diameter = min(rect.width(), rect.height()) - 8  # 8px 마진
        circle_rect = QRect(
            rect.left() + (rect.width() - diameter) // 2,
            rect.top() + (rect.height() - diameter) // 2,
            diameter, diameter
        )

        # 원 그리기
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bgColor)  # 원 배경색
        painter.drawEllipse(circle_rect)

        # 텍스트 그리기
        text = index.data(Qt.ItemDataRole.DisplayRole)
        painter.setPen(fgColor)  # 글씨색
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()

def create_label(text, bg_color):
    label = QLabel(text)
    label.setStyleSheet(f"background-color: {bg_color}; color: white; padding: 4px; font-size: 12px; border-radius: 4px;")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)  # 너비 균일하게 확장
    return label

def create_count_label():
    label = QLabel("0")
    label.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px;")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return label

class BettingWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.settings_manager = SettingsManager()
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        self.current_martin_step = 0
        self.current_room_results = []  # 현재 방에서의 결과 기록 (O, X, T)
        self.current_bet_amount = 0  # 현재 배팅 금액 저장 변수 추가
        
        # 방 별 순차적 위치 카운터
        self.room_position_counter = 0  # 방마다 초기화되는 마커 위치 카운터
        
        main_layout = QVBoxLayout()
        
        # 진행 섹션 (현재 방 + PICK 표시 + 현재 방 배팅 결과)
        progress_group = QGroupBox("진행")
        # 최소 높이를 80으로 감소 (기존 100에서 축소)
        progress_group.setMinimumHeight(80)  
        progress_layout = QVBoxLayout()
        
        # 상단 정보 영역 (현재방, 현재 배팅 금액)
        info_layout = QHBoxLayout()
        
        # 현재 방 표시 (변경: 하나의 레이아웃에 라벨과 값 함께 배치)
        room_layout = QHBoxLayout()
        room_label = QLabel("현재방:")
        room_label.setStyleSheet("font-weight: bold; font-size: 14px; background-color: white;")
        self.current_room = QLabel("")  # 초기값 비워두기
        self.current_room.setStyleSheet("font-size: 14px; background-color: white;")
        room_layout.addWidget(room_label)
        room_layout.addWidget(self.current_room)
        room_layout.addStretch(1)  # 왼쪽 정렬되도록 오른쪽에 여백 추가
        
        # 현재 배팅 금액 표시 (가운데 정렬)
        bet_amount_layout = QHBoxLayout()
        bet_amount_layout.addStretch(1)  # 왼쪽에 여백 추가 (가운데 정렬을 위해)
        bet_amount_label = QLabel("현재 배팅 금액:")
        bet_amount_label.setStyleSheet("font-weight: bold; font-size: 14px; background-color: white;")
        self.bet_amount_value = QLabel("0")  # 초기값 0
        self.bet_amount_value.setStyleSheet("background-color: white;font-size: 14px; font-weight: bold; color: #F44336; ")  # 강조 표시
        bet_amount_layout.addWidget(bet_amount_label)
        bet_amount_layout.addWidget(self.bet_amount_value)
        bet_amount_layout.addStretch(1)  # 오른쪽에 여백 추가 (가운데 정렬을 위해)
        
        # 모드 표시 추가 
        mode_layout = QHBoxLayout()
        mode_layout.addStretch(1)  # 위젯 앞에 여백 추가 (오른쪽 정렬)
        self.mode_value = QLabel("일반 베팅")  # 초기값
        self.mode_value.setStyleSheet("background-color: white; font-size: 14px; font-weight: bold; color: #4CAF50;")  # 녹색으로 표시
        mode_layout.addWidget(self.mode_value)
        # mode_layout.addStretch(1)  # 왼쪽 정렬되도록 오른쪽에 여백 추가

        # 전체 정보 레이아웃에 세 부분 추가 - 수정된 부분: mode_layout 추가
        info_layout.addLayout(room_layout, 1)      # 비율 1
        info_layout.addLayout(bet_amount_layout, 1)  # 비율 1
        info_layout.addLayout(mode_layout, 1)      # 비율 1 
        
        progress_layout.addLayout(info_layout)
        
        # 진행 테이블 - 스크롤 가능한 테이블 위젯
        self.progress_table = QTableWidget()
        # 테이블 높이도 약간 축소 (최소 높이 100에서 80으로)
        self.progress_table.setMinimumHeight(80)
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
        room_results_layout = QGridLayout()  # 🔥 QGridLayout으로 변경
        
        # 성공(O)
        self.success_count = 0
        success_layout = QHBoxLayout()
        success_label = create_label("성공(O)", "#2196F3")
        self.success_count_label = create_count_label()
        success_layout.addWidget(success_label)
        success_layout.addWidget(self.success_count_label)

        # 실패(X)
        self.fail_count = 0
        fail_layout = QHBoxLayout()
        fail_label = create_label("실패(X)", "#F44336")
        self.fail_count_label = create_count_label()
        fail_layout.addWidget(fail_label)
        fail_layout.addWidget(self.fail_count_label)

        # 타이(T)
        self.tie_count = 0
        tie_layout = QHBoxLayout()
        tie_label = create_label("타이(T)", "#4CAF50")
        self.tie_count_label = create_count_label()
        tie_layout.addWidget(tie_label)
        tie_layout.addWidget(self.tie_count_label)

        # GridLayout에 균일하게 배치
        room_results_layout.addLayout(success_layout, 0, 0)
        room_results_layout.addLayout(fail_layout, 0, 1)
        room_results_layout.addLayout(tie_layout, 0, 2)
        
        # 🔥 각 열이 균일한 비율을 가지도록 설정
        room_results_layout.setColumnStretch(0, 1)
        room_results_layout.setColumnStretch(1, 1)
        room_results_layout.setColumnStretch(2, 1)

        progress_layout.addLayout(room_results_layout)

        # progress_layout.addLayout(room_results_layout)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        self.setLayout(main_layout)
        
    def update_settings(self):
        """설정이 변경되었을 때 호출"""
        # 새로운 마틴 설정 불러오기
        self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
        
        # 테이블 열 개수 업데이트 - 마틴 단계에 맞춰 조정
        # 핵심 변경: 마틴 단계 수만큼만 열 만들기 (추가 여유 공간은 5개로 제한)
        max_columns = self.martin_count  # 마틴 단계 + 10개의 여유 공간
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
        # print(f"[INFO] 마틴 설정 업데이트 - 단계 수: {self.martin_count}, 금액: {self.martin_amounts}")
    
    def update_current_room(self, room_name):
        """현재 방 이름 업데이트"""
        # 이전 방과 지금 방이 다른지 확인 (방 이동 감지)
        current_displayed_name = self.current_room.text()
        
        # 방 이름에서 첫 번째 줄만 추출 (UI 표시용)
        if '\n' in room_name:
            # 방 이름에 게임 수나 베팅 정보가 포함된 경우 처리
            if '(' in room_name and ')' in room_name:
                # "방이름 (게임 수: N, 베팅: X)" 형식인 경우
                parts = room_name.split('(')
                base_name = parts[0].strip()
                info = '(' + parts[1]  # 괄호 정보 유지
                
                # 기본 이름에서 첫 번째 줄만 추출
                base_name = base_name.split('\n')[0]
                
                # 정보와 함께 업데이트
                new_display_name = f"{base_name} {info}"
                
                # 방 이동 감지 - 순수 방 이름만 비교
                if not current_displayed_name.startswith(base_name):
                    # 새로운 방으로 이동한 경우 - 카운터 초기화
                    self.room_position_counter = 0
                    print(f"[INFO] 새 방 이동 감지: '{base_name}'. 마커 위치 카운터 초기화")
                
                # UI 업데이트
                self.current_room.setText(new_display_name)
            else:
                # 단순히 여러 줄로 된 방 이름인 경우
                display_name = room_name.split('\n')[0]
                
                # 방 이동 감지
                if current_displayed_name != display_name:
                    # 새로운 방으로 이동한 경우 - 카운터 초기화
                    self.room_position_counter = 0
                    print(f"[INFO] 새 방 이동 감지: '{display_name}'. 마커 위치 카운터 초기화")
                
                # UI 업데이트
                self.current_room.setText(display_name)
        else:
            # 이미 한 줄인 경우 그대로 표시
            if current_displayed_name != room_name:
                # 새로운 방으로 이동한 경우 - 카운터 초기화
                self.room_position_counter = 0
                print(f"[INFO] 새 방 이동 감지: '{room_name}'. 마커 위치 카운터 초기화")
            
            # UI 업데이트
            self.current_room.setText(room_name)
    
    def update_bet_amount(self, amount):
        """
        현재 배팅 금액 업데이트
        
        Args:
            amount (int): 배팅 금액
        """
        self.current_bet_amount = amount
        
        # 천 단위 구분자로 포맷팅하여 표시
        formatted_amount = f"{amount:,}원"
        self.bet_amount_value.setText(formatted_amount)
        
        # 금액에 따라 색상 변경 (금액이 클수록 더 붉은색으로)
        if amount > 10000:
            self.bet_amount_value.setStyleSheet("background-color:white; font-size: 14px; font-weight: bold; color: #D32F2F;")  # 더 강한 빨간색
        elif amount > 5000:
            self.bet_amount_value.setStyleSheet("background-color:white; font-size: 14px; font-weight: bold; color: #F44336;")  # 일반 빨간색
        else:
            self.bet_amount_value.setStyleSheet("background-color:white; font-size: 14px; font-weight: bold; color: #FF9800;")  # 주황색
            
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
        
        # 배팅 금액도 초기화
        self.update_bet_amount(0)
        
        # 위치 카운터 초기화 - 중요: 방을 이동할 때마다 마커 위치 카운터 초기화
        self.room_position_counter = 0
        print("[INFO] 방 결과 초기화 - 마커 위치 카운터 초기화")
    
    # PICK 값 설정 함수 수정 (P는 파란색 동그라미 안에 흰색 글씨로 P, B도 동일하게)
    def set_pick(self, pick_value):
        """PICK 값 설정 (B, P 등) - 원 안에 문자 표시"""
        # None이나 빈 문자열 처리
        if pick_value is None or pick_value == "":
            pick_value = "N"

        # N 값 처리 (회색)
        if pick_value == "N":
            self.pick_item.setText(pick_value)
            self.pick_item.setBackground(QColor("#9E9E9E"))  # 회색
            self.pick_item.setForeground(QColor("white"))
            self.pick_item.setData(Qt.ItemDataRole.UserRole, None)
            return

        # P와 B는 원 안에 표시
        if pick_value == "P":
            self.pick_item.setText(pick_value)
            self.pick_item.setBackground(QColor("#2196F3"))  # 파란색 배경
            self.pick_item.setForeground(QColor("white"))    # 흰색 글씨
            self.pick_item.setData(Qt.ItemDataRole.UserRole, "circle-P")  # 구분을 위해 "circle-P" 사용
        elif pick_value == "B":
            self.pick_item.setText(pick_value)
            self.pick_item.setBackground(QColor("#F44336"))  # 빨간색 배경
            self.pick_item.setForeground(QColor("white"))    # 흰색 글씨
            self.pick_item.setData(Qt.ItemDataRole.UserRole, "circle-B")  # 구분을 위해 "circle-B" 사용
        else:
            # 기타 값 처리 (기본 회색)
            self.pick_item.setText(pick_value)
            self.pick_item.setBackground(QColor("#9E9E9E"))  # 회색
            self.pick_item.setForeground(QColor("white"))
            self.pick_item.setData(Qt.ItemDataRole.UserRole, None)

        # UI 강제 업데이트
        self.progress_table.viewport().update()

    # 단계별 마커 설정 함수 수정 - 특정 방 안에서 순차적으로 표시하도록 수정
    def set_step_marker(self, step, marker):
        """
        단계별 마커 설정 (X, O, T, 빈칸)
        수정: TIE 결과는 카운터 증가하지만 같은 방에 머무름
        """
        # 단계 번호로 내부 카운터 사용
        display_step = self.room_position_counter + 1
        
        # 마커 설정 - 음수나 0은 1로 처리 (안전 장치)
        if display_step <= 0:
            display_step = 1
        
        # 단계가 너무 큰 경우 동적으로 열 추가
        if display_step >= self.progress_table.columnCount():
            self._ensure_column_exists(display_step)
        
        # 마커 설정
        if display_step in self.step_items:
            item = self.step_items[display_step]
            
            # 마커에 따른 색상 설정
            if marker == "X":
                # X는 빨간색 글씨로 표시
                item.setText(marker)
                item.setBackground(QColor("white"))
                item.setForeground(QColor("#F44336"))
                item.setFont(QFont("Arial", 18, QFont.Weight.Bold))
                # 실패 수 증가
                self.fail_count += 1
                self.fail_count_label.setText(str(self.fail_count))
                # 결과 기록
                self.current_room_results.append("X")
                # 마커 카운터 증가
                self.room_position_counter += 1
            elif marker == "O":
                # O는 파란색 글씨로 표시
                item.setText(marker)
                item.setBackground(QColor("white"))
                item.setForeground(QColor("#2196F3"))
                item.setFont(QFont("Arial", 18, QFont.Weight.Bold))
                # 성공 수 증가
                self.success_count += 1
                self.success_count_label.setText(str(self.success_count))
                # 결과 기록
                self.current_room_results.append("O")
                # 마커 카운터 증가
                self.room_position_counter += 1
            elif marker == "T":
                # T는 녹색으로 표시
                item.setText(marker)
                item.setBackground(QColor("#4CAF50"))
                item.setForeground(QColor("white"))
                # 타이 수 증가
                self.tie_count += 1
                self.tie_count_label.setText(str(self.tie_count))
                # 결과 기록
                self.current_room_results.append("T")
                # 마커 카운터 증가 - TIE도 마커 카운터는 증가시킴
                self.room_position_counter += 1
            else:
                item.setText(marker)
                item.setBackground(QColor("white"))
                item.setForeground(QColor("black"))
            
            # UI 업데이트 강제 실행 (명시적으로 업데이트)
            from PyQt6.QtWidgets import QApplication
            self.progress_table.viewport().update()
            self.progress_table.repaint()
            QApplication.processEvents()
            
            # 테이블 스크롤 위치 조정 - 새로 설정한 마커가 보이도록
            if display_step > 10:  # 어느 정도 오른쪽에 있는 경우에만 스크롤 조정
                try:
                    # 현재 마커가 보이도록 스크롤 조정
                    self.progress_table.horizontalScrollBar().setValue(
                        (display_step - 5) * self.progress_table.columnWidth(1)  # 약간 왼쪽으로 조정
                    )
                except Exception as e:
                    print(f"[WARNING] 스크롤 조정 중 오류: {e}")
            
            print(f"[DEBUG] UI 업데이트 완료: 단계 {display_step}에 {marker} 마커 설정됨")
        else:
            print(f"[WARNING] 잘못된 단계 번호: {display_step} (step_items 키에 없음)")
            print(f"[DEBUG] 가능한 step_items 키: {list(self.step_items.keys())}")
            
            # 동적으로 스텝 추가 시도
            self._ensure_column_exists(display_step)
            
            # 새로 추가된 후 다시 시도
            if display_step in self.step_items:
                print(f"[INFO] 새로 확장된 범위에서 단계 {display_step} 설정 시도")
                # 다시 호출 - 원래 step이 아닌 display_step 전달
                # 재귀적 무한 호출 방지를 위해 마커만 직접 설정
                item = self.step_items[display_step]
                item.setText(marker)
                
                # 마커 표시 및 카운터 증가 로직은 앞의 코드와 동일하게 진행
                if marker == "X":
                    item.setBackground(QColor("white")) 
                    item.setForeground(QColor("#F44336"))
                    self.fail_count += 1
                    self.fail_count_label.setText(str(self.fail_count))
                    self.current_room_results.append("X")
                    self.room_position_counter += 1
                elif marker == "O":
                    item.setBackground(QColor("white"))
                    item.setForeground(QColor("#2196F3"))
                    self.success_count += 1
                    self.success_count_label.setText(str(self.success_count))
                    self.current_room_results.append("O")
                    self.room_position_counter += 1
                elif marker == "T":
                    item.setBackground(QColor("#4CAF50"))
                    item.setForeground(QColor("white"))
                    self.tie_count += 1
                    self.tie_count_label.setText(str(self.tie_count))
                    self.current_room_results.append("T")
                    self.room_position_counter += 1

    def _ensure_column_exists(self, step):
        """필요한 경우 테이블에 열 추가"""
        current_cols = self.progress_table.columnCount()
    
        if step >= current_cols:
            # 마틴 설정 갱신 - 실제 필요한 열 수 확인
            self.martin_count, self.martin_amounts = self.settings_manager.get_martin_settings()
            
            # 필요한 열 수 계산 (최소 5개 여유 공간)
            needed_columns = max(step + 5, self.martin_count + 5)
            
            # 새로 추가할 열 수 계산 (최대 마틴 단계 + 5개)
            new_cols_needed = min(needed_columns - current_cols + 1, self.martin_count + 5)
            print(f"[INFO] 테이블에 새 열 {new_cols_needed}개 추가 중...")
            
            new_total_cols = current_cols + new_cols_needed
            self.progress_table.setColumnCount(new_total_cols)
            
            # 새 열 초기화
            for i in range(current_cols, new_total_cols):
                # 헤더 행 - 숫자
                col_num = i  # PICK(0) 열을 고려하여 조정
                num_item = QTableWidgetItem(str(col_num))
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                num_item.setBackground(QColor("#f0f0f0"))
                num_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                self.progress_table.setItem(0, i, num_item)
                
                # 마커 행 - 초기에는 빈 값
                marker_item = QTableWidgetItem("")
                marker_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                marker_item.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                self.progress_table.setItem(1, i, marker_item)
                self.step_items[col_num] = marker_item
                
                # 열 너비 설정
                self.progress_table.setColumnWidth(i, 60)
                           
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
        
        # 마커 설정 - 실제 배팅한 위치(no)를 사용 
        if marker:
            self.set_step_marker(no, marker)
            
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
        # 열 번호(헤더) 숨기기
        self.progress_table.verticalHeader().setVisible(False)

        # 설정에서 마틴 단계 수 가져오기
        martin_count, _ = self.settings_manager.get_martin_settings()
        
        #마틴 단계 + 여유분 11개 표시
        max_columns = martin_count + 11
        
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
        
        # 추가: 원형 아이템 델리게이트 설정
        self.progress_table.setItemDelegate(CircleItemDelegate(self.progress_table))
        
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
            marker_item.setFont(QFont("Arial", 18, QFont.Weight.Bold))
            self.progress_table.setItem(1, i, marker_item)
            self.step_items[i] = marker_item
        
        # 첫 번째 열 너비 설정
        self.progress_table.setColumnWidth(0, 80)  # PICK 열
        
        # 나머지 열 너비 설정
        for i in range(1, max_columns + 1):
            self.progress_table.setColumnWidth(i, 60)  # 숫자 열
        
        # 행 높이 설정
        self.progress_table.setRowHeight(0, 40)  # 헤더 행
        self.progress_table.setRowHeight(1, 40)  # 마커 행 (기존 60에서 40으로 축소)
        
        # 배팅 금액 초기화
        self.update_bet_amount(0)
        
    def update_mode(self, mode_type):
        """
        현재 베팅 모드를 업데이트합니다.
        
        Args:
            mode_type (str): 모드 유형 ('double', 'half', 또는 'normal')
        """
        if mode_type == 'double':
            self.mode_value.setText("Double Mode")
            self.mode_value.setStyleSheet("background-color: white; font-size: 14px; font-weight: bold; color: #F44336;")  # 빨간색으로 표시
        elif mode_type == 'half':
            self.mode_value.setText("Half Mode")
            self.mode_value.setStyleSheet("background-color: white; font-size: 14px; font-weight: bold; color: #2196F3;")  # 파란색으로 표시
        else:  # 'normal' 또는 기타
            self.mode_value.setText("일반 베팅")
            self.mode_value.setStyleSheet("background-color: white; font-size: 14px; font-weight: bold; color: #4CAF50;") 