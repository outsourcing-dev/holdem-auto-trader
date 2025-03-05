from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QGridLayout, QVBoxLayout
from PyQt6.QtCore import Qt
from ui.settings_window import SettingsWindow

class HeaderWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Main layout
        main_layout = QVBoxLayout()
        
        # Top info section
        info_layout = QGridLayout()
        
        # User info
        self.user_label = QLabel("유저정보")
        self.user_value = QLabel("로그인 필요")
        info_layout.addWidget(self.user_label, 0, 0)
        info_layout.addWidget(self.user_value, 1, 0)
        
        # Starting amount - 초기화: 0원
        self.start_amount_label = QLabel("시작금액")
        self.start_amount_value = QLabel("0")
        info_layout.addWidget(self.start_amount_label, 0, 1)
        info_layout.addWidget(self.start_amount_value, 1, 1)
        
        # Current amount - 초기화: 0원
        self.current_amount_label = QLabel("현재금액")
        self.current_amount_value = QLabel("0")
        info_layout.addWidget(self.current_amount_label, 0, 2)
        info_layout.addWidget(self.current_amount_value, 1, 2)
        
        # Profit amount - 초기화: 0원
        self.profit_label = QLabel("수익금액")
        self.profit_value = QLabel("0")
        info_layout.addWidget(self.profit_label, 0, 3)
        info_layout.addWidget(self.profit_value, 1, 3)
        
        # Cumulative betting - 초기화: 0원
        self.total_bet_label = QLabel("누적배팅")
        self.total_bet_value = QLabel("0")
        info_layout.addWidget(self.total_bet_label, 0, 4)
        info_layout.addWidget(self.total_bet_value, 1, 4)
        
        # Settings button
        self.settings_button = QPushButton("환경설정")
        self.settings_button.clicked.connect(self.open_settings)
        info_layout.addWidget(self.settings_button, 0, 5, 2, 1)  # Span 2 rows
        
        # Add info layout to main layout
        main_layout.addLayout(info_layout)
        
        # Set alignment for all labels to center
        for i in range(info_layout.count()):
            widget = info_layout.itemAt(i).widget()
            if isinstance(widget, QLabel):
                widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.setLayout(main_layout)

    def update_user_info(self, username):
        """Update user information"""
        if username:
            self.user_value.setText(username)
        
    def update_start_amount(self, amount):
        """Update starting amount"""
        self.start_amount_value.setText(f"{amount:,}")
        
    def update_current_amount(self, amount):
        """Update current amount"""
        self.current_amount_value.setText(f"{amount:,}")
        
    def update_profit(self, amount):
        """Update profit amount and set color based on value"""
        self.profit_value.setText(f"{amount:,}")
        if amount > 0:
            self.profit_value.setStyleSheet("color: blue;")
        elif amount < 0:
            self.profit_value.setStyleSheet("color: red;")
        else:
            self.profit_value.setStyleSheet("color: black;")
            
    def update_total_bet(self, amount):
        """Update cumulative betting amount"""
        self.total_bet_value.setText(f"{amount:,}")
    
    def reset_values(self):
        """모든 값을 초기화 (0원)"""
        self.user_value.setText("로그인 필요")
        self.start_amount_value.setText("0")
        self.current_amount_value.setText("0")
        self.profit_value.setText("0")
        self.profit_value.setStyleSheet("color: black;")
        self.total_bet_value.setText("0")
        
    def open_settings(self):
        """Open settings window"""
        self.settings_window = SettingsWindow()
        self.settings_window.show()