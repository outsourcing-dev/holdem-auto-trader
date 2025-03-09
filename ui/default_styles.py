# utils/default_styles.py

"""
기본 스타일 정의 모듈
CSS 파일을 로드하지 못할 경우 사용할 기본 스타일을 정의합니다.
"""

# 기본 스타일 정의
DEFAULT_STYLE = """
/* 전체 배경을 라이트 모드로 적용 */
QWidget, QMainWindow, QDialog {
    background-color: #F5F5F5;
    color: #333333;
    font-family: "Arial";
    font-size: 14px;
}

/* 입력 필드 스타일 */
QLineEdit {
    background-color: #FFFFFF;
    color: #333333;
    border: 2px solid #4CAF50;
    border-radius: 6px;
    padding: 6px;
    font-size: 14px;
}

QLineEdit:focus {
    border-color: #2E7D32;
}

/* 버튼 스타일 */
QPushButton {
    background-color: #4CAF50;
    color: white;
    font-size: 16px;
    border-radius: 6px;
    padding: 8px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #2E7D32;
}

QPushButton:pressed {
    background-color: #1B5E20;
}

/* 그룹 박스 */
QGroupBox {
    border: 2px solid #4CAF50;
    border-radius: 6px;
    margin-top: 10px;
    padding: 6px;
    background-color: #FFFFFF;
}

QGroupBox::title {
    color: #2E7D32;
    font-weight: bold;
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 5px;
}

/* 테이블 위젯 */
QTableWidget {
    background-color: #FFFFFF;
    color: #333333;
    gridline-color: #CCCCCC;
    border: 1px solid #4CAF50;
    border-radius: 4px;
    selection-background-color: #C8E6C9;
    selection-color: #333333;
}

QHeaderView::section {
    background-color: #4CAF50;
    color: white;
    font-weight: bold;
    padding: 4px;
    border: 1px solid #2E7D32;
}

QTableWidget::item {
    padding: 4px;
}
"""

# 간단한 스타일 (최소한의 스타일만 정의)
MINIMAL_STYLE = """
QWidget, QMainWindow, QDialog {
    background-color: #F5F5F5;
}

QPushButton {
    background-color: #4CAF50;
    color: white;
    border-radius: 5px;
    padding: 5px;
}

QLineEdit {
    border: 1px solid #4CAF50;
    border-radius: 3px;
    padding: 3px;
}

QTableWidget {
    background-color: white;
    border: 1px solid #CCCCCC;
}

QHeaderView::section {
    background-color: #4CAF50;
    color: white;
}
"""

def get_default_style(is_minimal=False):
    """기본 스타일을 반환합니다."""
    return MINIMAL_STYLE if is_minimal else DEFAULT_STYLE