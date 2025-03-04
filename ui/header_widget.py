from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from ui.settings_window import SettingsWindow

class HeaderWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout()

        # 현재 잔액
        self.balance_label = QLabel("현재 잔액: 0원")
        layout.addWidget(self.balance_label)

        # 수익금
        self.profit_label = QLabel("수익금: 0원")
        layout.addWidget(self.profit_label)

        # 설정 버튼
        self.settings_button = QPushButton("설정")
        self.settings_button.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_button)

        self.setLayout(layout)

    def update_balance(self, balance):
        """잔액 업데이트"""
        self.balance_label.setText(f"현재 잔액: {balance}원")
        
    def open_settings(self):
        """설정창 열기"""
        self.settings_window = SettingsWindow()
        self.settings_window.show()
