# ui/settings_window.py - Updated without Double & Half section

import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QGroupBox, QHBoxLayout, 
                             QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtGui import QFont,QIntValidator
from PyQt6.QtCore import Qt
from utils.settings_manager import SettingsManager

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("설정")
        self.setGeometry(200, 200, 600, 800)
        self.setObjectName("SettingsWindow")  # QSS 스타일 적용을 위한 ID 지정
        
        # 스타일 적용 - 경로 로직 수정
        style_path = self.get_style_path()
        if style_path and os.path.exists(style_path):
            try:
                with open(style_path, "r", encoding="utf-8") as f:
                    self.setStyleSheet(f.read())
                    print(f"[INFO] 설정 창에 스타일시트 적용 완료: {style_path}")
            except Exception as e:
                print(f"[ERROR] 스타일시트 파일 읽기 오류: {e}")
        else:
            print(f"[WARNING] 스타일시트 파일을 찾을 수 없습니다: {style_path}")

        self.settings_manager = SettingsManager()
        site1, site2, site3 = self.settings_manager.get_sites()
        martin_count, martin_amounts = self.settings_manager.get_martin_settings()
        target_amount = self.settings_manager.get_target_amount()
        
        # Load Double & Half settings for backward compatibility (but we won't display them)
        double_half_start, double_half_stop = self.settings_manager.get_double_half_settings()

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
        
        # 개선: 목표 금액을 천 단위 구분자로 포맷팅하여 표시
        formatted_target = f"{target_amount:,}" if target_amount > 0 else ""
        self.target_amount_input = QLineEdit(formatted_target)
        self.target_amount_input.setPlaceholderText("예: 200,000")
        
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
        self.martin_count_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; }")
        
        # 현재 스피너 값
        self.martin_count_value = martin_count
        
        # 커스텀 스피너 구현 (값 입력 필드 왼쪽, +/- 버튼 둘 다 오른쪽에 배치)
        spinner_layout = QHBoxLayout()
        spinner_layout.setContentsMargins(0, 0, 0, 0)
        spinner_layout.setSpacing(5)  # 적당한 간격

        # 왼쪽 여백 추가 (스트레치로 여백 넣기)
        spinner_layout.addStretch(1)

        # 값 표시 필드 (중앙)
        self.martin_value_display = QLineEdit(str(martin_count))
        self.martin_value_display.setFixedHeight(30)
        self.martin_value_display.setFixedWidth(60)
        self.martin_value_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.martin_value_display.setReadOnly(True)
        self.martin_value_display.setStyleSheet("""
            QLineEdit {
                background-color: #FFFFFF;
                color: #333333;
                border: 2px solid #4CAF50;
                border-radius: 3px;
                font-size: 14px;
                font-weight: bold;
            }
        """)

        # 오른쪽 여백과 버튼 사이 공간 (조정 가능)
        spinner_layout.addWidget(self.martin_value_display)
        spinner_layout.addStretch(1)  # 중앙과 오른쪽 버튼 사이 여백

        # 오른쪽 버튼들 (기존과 동일)
        # 증가 버튼 (+)
        self.increase_btn = QPushButton("+")
        self.increase_btn.setFixedSize(30, 30)
        self.increase_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: black;
                font-weight: bold;
                font-size: 16px;
                border: 1px solid #333333;
                border-radius: 3px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)

        # 감소 버튼 (-)
        self.decrease_btn = QPushButton("-")
        self.decrease_btn.setFixedSize(30, 30)
        self.decrease_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: black;
                font-weight: bold;
                font-size: 16px;
                border: 1px solid #333333;
                border-radius: 3px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)

        # 버튼 클릭 이벤트 연결
        self.decrease_btn.clicked.connect(self.decrease_value)
        self.increase_btn.clicked.connect(self.increase_value)

        # 위젯 배치 - 입력 필드가 중앙, 버튼들이 오른쪽으로 배치
        spinner_layout.addWidget(self.increase_btn)
        spinner_layout.addWidget(self.decrease_btn)

        # 스피너 컨테이너 생성
        spinner_container = QWidget()
        spinner_container.setLayout(spinner_layout)
        
        # 레이아웃에 추가
        count_layout.addWidget(self.martin_count_label)
        count_layout.addWidget(spinner_container)
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
        
    def decrease_value(self):
        """마틴 횟수 감소"""
        if self.martin_count_value > 1:
            self.martin_count_value -= 1
            self.martin_value_display.setText(str(self.martin_count_value))
            self.update_martin_table()
    
    def increase_value(self):
        """마틴 횟수 증가"""
        if self.martin_count_value < 30:
            self.martin_count_value += 1
            self.martin_value_display.setText(str(self.martin_count_value))
            self.update_martin_table()

    def get_style_path(self):
        """스타일시트 파일 경로를 결정합니다."""
        # PyInstaller로 패키징된 경우
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            # 여러 경로 후보를 확인 (우선순위 순서대로)
            paths = [
                os.path.join(base_dir, "ui", "style.qss"),       # 기존 경로
                os.path.join(base_dir, "style.qss"),            # 루트 경로
                os.path.join(base_dir, "_internal", "ui", "style.qss")  # _internal 내부 경로
            ]
            
            # 존재하는 첫 번째 경로 반환
            for path in paths:
                if os.path.exists(path):
                    print(f"[INFO] 스타일시트 파일 발견: {path}")
                    return path
                    
            print(f"[WARNING] 패키지 환경에서 스타일시트 파일을 찾을 수 없습니다.")
            return os.path.join(base_dir, "ui", "style.qss")  # 기본 경로 반환
        else:
            # 개발 환경인 경우
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.dirname(current_dir)  # 상위 디렉토리 (프로젝트 루트)
            style_path = os.path.join(current_dir, "style.qss")
            
            # 현재 디렉토리에 없으면 ui 폴더 확인
            if not os.path.exists(style_path):
                style_path = os.path.join(base_dir, "ui", "style.qss")
                
            print(f"[INFO] 개발 환경, 스타일 경로: {style_path}")
            return style_path
    
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
        # 현재 스피너 값 사용
        count = self.martin_count_value
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
        """입력된 사이트 정보와 마틴 설정, 목표 금액을 JSON 파일에 저장하고 다시 로드"""
        site1 = self.site1_input.text()
        site2 = self.site2_input.text()
        site3 = self.site3_input.text()
        
        martin_count = self.martin_count_value  # 직접 구현한 스피너에서 값 가져오기
        martin_amounts = self.collect_martin_amounts()
        
        # 목표 금액 가져오기
        target_amount = self.get_target_amount()
        
        # 기존 Double & Half 설정 유지 (for backward compatibility)
        double_half_start, double_half_stop = self.settings_manager.get_double_half_settings()
        
        # 설정 저장
        self.settings_manager.save_settings(
            site1, site2, site3, 
            martin_count=martin_count,
            martin_amounts=martin_amounts,
            target_amount=target_amount,
            double_half_start=double_half_start,
            double_half_stop=double_half_stop
        )
        
        # 설정 파일을 명시적으로 다시 로드
        self.settings_manager.load_settings()
        
        print(f"[INFO] 설정 저장 및 재로드 완료 - 목표 금액: {target_amount:,}원")
        
        # 부모 창에 있는 설정 관련 클래스들도 새로운 설정 로드
        try:
            # 메인 창의 설정 관련 객체들 업데이트
            for obj_name in ['trading_manager', 'martin_service', 'balance_service']:
                if hasattr(self.parent(), obj_name):
                    obj = getattr(self.parent(), obj_name)
                    if hasattr(obj, 'settings_manager'):
                        # 설정 매니저 갱신
                        obj.settings_manager = self.settings_manager
                    # 추가로 settings_manager 내부의 설정 업데이트
                    if hasattr(obj, 'update_settings') and callable(getattr(obj, 'update_settings')):
                        obj.update_settings()
        except Exception as e:
            print(f"[WARNING] 부모 창 설정 업데이트 오류: {e}")
        
        self.close()