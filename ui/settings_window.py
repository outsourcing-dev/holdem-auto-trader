# ui/settings_window.py에 목표 금액 설정 UI 추가
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QGroupBox, QHBoxLayout, QSpinBox, 
                             QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from utils.settings_manager import SettingsManager

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("설정")
        self.setGeometry(200, 200, 600, 800)
        self.setObjectName("SettingsWindow")  # QSS 스타일 적용을 위한 ID 지정
        
        # 스타일 적용
        with open("ui/style.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

        self.settings_manager = SettingsManager()
        site1, site2, site3 = self.settings_manager.get_sites()
        martin_count, martin_amounts = self.settings_manager.get_martin_settings()
        target_amount = self.settings_manager.get_target_amount()

        # 메인 레이아웃
        main_layout = QVBoxLayout()

        # 폰트 설정
        label_font = QFont("Arial", 11, QFont.Weight.Bold)
        
        # 사이트 설정 그룹
        site_group = QGroupBox("사이트 설정")
        site_group.setFont(label_font)
        site_layout = QVBoxLayout()

        self.label1 = QLabel("사이트 1:")
        self.label1.setFont(label_font)
        self.site1_input = QLineEdit(site1)
        site_layout.addWidget(self.label1)
        site_layout.addWidget(self.site1_input)

        self.label2 = QLabel("사이트 2:")
        self.label2.setFont(label_font)
        self.site2_input = QLineEdit(site2)
        site_layout.addWidget(self.label2)
        site_layout.addWidget(self.site2_input)

        self.label3 = QLabel("사이트 3:")
        self.label3.setFont(label_font)
        self.site3_input = QLineEdit(site3)
        site_layout.addWidget(self.label3)
        site_layout.addWidget(self.site3_input)

        site_group.setLayout(site_layout)
        main_layout.addWidget(site_group)
        
        # 목표 금액 설정 그룹
        target_group = QGroupBox("목표 금액 설정")
        target_group.setFont(label_font)
        target_layout = QVBoxLayout()
        
        # 목표 금액 설명 레이블
        target_info_label = QLabel("목표 금액에 도달하면 자동으로 매매가 중단됩니다. (0 = 비활성화)")
        target_info_label.setStyleSheet("color: #555; font-size: 10pt;")
        target_layout.addWidget(target_info_label)
        
        # 목표 금액 입력 필드
        target_amount_layout = QHBoxLayout()
        self.target_amount_label = QLabel("목표 금액(원):")
        self.target_amount_label.setFont(label_font)
        self.target_amount_input = QLineEdit(str(target_amount))
        self.target_amount_input.setPlaceholderText("예: 1000000")
        
        # 숫자만 입력되도록 설정
        self.target_amount_input.textChanged.connect(self.validate_target_amount)
        
        target_amount_layout.addWidget(self.target_amount_label)
        target_amount_layout.addWidget(self.target_amount_input)
        target_layout.addLayout(target_amount_layout)
        
        target_group.setLayout(target_layout)
        main_layout.addWidget(target_group)
        
        # 마틴 설정 그룹
        martin_group = QGroupBox("마틴 설정")
        martin_group.setFont(label_font)
        martin_layout = QVBoxLayout()
        
        # 마틴 횟수 선택
        count_layout = QHBoxLayout()
        self.martin_count_label = QLabel("마틴 횟수:")
        self.martin_count_label.setFont(label_font)
        self.martin_count_spinner = QSpinBox()
        self.martin_count_spinner.setMinimum(1)
        self.martin_count_spinner.setMaximum(30)  # 최대 마틴 단계 수
        self.martin_count_spinner.setValue(martin_count)
        self.martin_count_spinner.valueChanged.connect(self.update_martin_table)
        count_layout.addWidget(self.martin_count_label)
        count_layout.addWidget(self.martin_count_spinner)
        martin_layout.addLayout(count_layout)
        
        # 마틴 금액 테이블
        self.martin_table = QTableWidget()
        self.martin_table.setColumnCount(1)  # 금액 열만 표시
        self.martin_table.setHorizontalHeaderLabels(["금액 (원)"])
        self.martin_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        # 행 헤더(단계) 표시 설정
        self.martin_table.verticalHeader().setVisible(True)  # 행 헤더 표시
        self.martin_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.martin_table.verticalHeader().setDefaultSectionSize(30)  # 행 높이 설정
        
        # 추가 스타일 적용
        self.martin_table.setStyleSheet("""
            QLineEdit {
                min-height: 28px;
                font-size: 14px;
            }
            QHeaderView::section:vertical {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #2E7D32;
            }
        """)
        martin_layout.addWidget(self.martin_table)
        
        # 테이블 초기화
        self.martin_amounts = martin_amounts
        self.update_martin_table()
        
        # 테이블 편집 설정
        self.martin_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | 
                                         QTableWidget.EditTrigger.SelectedClicked)
        self.martin_table.itemChanged.connect(self.on_table_item_changed)
        
        martin_group.setLayout(martin_layout)
        main_layout.addWidget(martin_group)

        # 저장 버튼
        self.save_button = QPushButton("💾 저장")
        self.save_button.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.save_button.setFixedHeight(40)
        self.save_button.clicked.connect(self.save_settings)
        main_layout.addWidget(self.save_button)

        self.setLayout(main_layout)

    def validate_target_amount(self, text):
        """목표 금액 입력값 검증 - 숫자만 허용"""
        if text and not text.isdigit():
            # 숫자가 아닌 문자 제거
            cursor_pos = self.target_amount_input.cursorPosition()
            clean_text = ''.join(filter(str.isdigit, text))
            self.target_amount_input.setText(clean_text)
            # 가능한 한 원래 커서 위치 유지
            self.target_amount_input.setCursorPosition(min(cursor_pos, len(clean_text)))

    def update_martin_table(self):
        """마틴 테이블 업데이트"""
        count = self.martin_count_spinner.value()
        self.martin_table.setRowCount(count)
        
        # 테이블 아이템 변경 이벤트 처리 일시 중지
        self.martin_table.blockSignals(True)
        
        # 기존 마틴 금액 배열 크기 조정
        if len(self.martin_amounts) < count:
            # 배열이 작으면 확장 (기본값: 이전 값의 2배, 첫 값은 1000원)
            last_amount = self.martin_amounts[-1] if self.martin_amounts else 1000
            for i in range(len(self.martin_amounts), count):
                self.martin_amounts.append(last_amount * 2)
                last_amount = last_amount * 2
        elif len(self.martin_amounts) > count:
            # 배열이 크면 축소
            self.martin_amounts = self.martin_amounts[:count]
            
        # 테이블 채우기
        for i in range(count):
            # 행 헤더 설정 (단계)
            self.martin_table.setVerticalHeaderItem(i, QTableWidgetItem(f"단계 {i+1}"))
            
            # 금액 열 (편집 가능)
            amount_item = QTableWidgetItem(f"{self.martin_amounts[i]:,}원")
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # 가운데 정렬
            self.martin_table.setItem(i, 0, amount_item)
        
        # 테이블 아이템 변경 이벤트 처리 재개
        self.martin_table.blockSignals(False)
    
    def on_table_item_changed(self, item):
        """테이블 항목이 편집되었을 때 호출"""
        row = item.row()
        try:
            # 쉼표와 '원' 제거
            text = item.text().replace(",", "").replace("원", "").strip()
            amount = int(text)
            
            # 금액 범위 제한 (최소 100원)
            if amount < 100:
                amount = 100
            
            # 마틴 금액 배열 업데이트
            if row < len(self.martin_amounts):
                self.martin_amounts[row] = amount
            
            # 포맷된 텍스트로 다시 표시
            item.setText(f"{amount:,}원")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # 가운데 정렬
            
        except ValueError:
            # 숫자가 아닌 경우 이전 값으로 복원
            old_amount = self.martin_amounts[row] if row < len(self.martin_amounts) else 1000
            item.setText(f"{old_amount:,}원")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)  # 가운데 정렬
    
    def collect_martin_amounts(self):
        """테이블에서 마틴 금액 수집"""
        count = self.martin_table.rowCount()
        amounts = []
        
        for i in range(count):
            amount_item = self.martin_table.item(i, 0)  # 첫 번째(유일한) 열
            text = amount_item.text().replace(",", "").replace("원", "").strip()  # 쉼표와 '원' 제거
            try:
                amount = int(text)
                amounts.append(amount)
            except ValueError:
                amounts.append(1000)  # 기본값
                
        return amounts
    
    def get_target_amount(self):
        """목표 금액 입력값 가져오기"""
        try:
            text = self.target_amount_input.text().replace(",", "").strip()
            if text:
                return int(text)
            return 0  # 빈 값은 0으로 처리 (비활성화)
        except ValueError:
            return 0  # 변환 오류 시 0으로 처리 (비활성화)

    def save_settings(self):
        """입력된 사이트 정보와 마틴 설정을 JSON 파일에 저장"""
        site1 = self.site1_input.text()
        site2 = self.site2_input.text()
        site3 = self.site3_input.text()
        
        martin_count = self.martin_count_spinner.value()
        martin_amounts = self.collect_martin_amounts()
        
        # 목표 금액 가져오기
        target_amount = self.get_target_amount()
        
        self.settings_manager.save_settings(
            site1, site2, site3, 
            martin_count=martin_count,
            martin_amounts=martin_amounts,
            target_amount=target_amount
        )
        
        print(f"[INFO] 설정 저장 완료 - 목표 금액: {target_amount:,}원")
        self.close()