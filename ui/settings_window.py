from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
from utils.settings_manager import SettingsManager

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("설정")
        self.setGeometry(200, 200, 400, 300)

        self.settings_manager = SettingsManager()
        site1, site2, site3 = self.settings_manager.get_sites()

        layout = QVBoxLayout()

        self.label1 = QLabel("사이트 1:")
        self.site1_input = QLineEdit(site1)
        layout.addWidget(self.label1)
        layout.addWidget(self.site1_input)

        self.label2 = QLabel("사이트 2:")
        self.site2_input = QLineEdit(site2)
        layout.addWidget(self.label2)
        layout.addWidget(self.site2_input)

        self.label3 = QLabel("사이트 3:")
        self.site3_input = QLineEdit(site3)
        layout.addWidget(self.label3)
        layout.addWidget(self.site3_input)

        self.save_button = QPushButton("저장")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def save_settings(self):
        """입력된 사이트 정보를 저장"""
        site1 = self.site1_input.text()
        site2 = self.site2_input.text()
        site3 = self.site3_input.text()

        self.settings_manager.save_settings(site1, site2, site3)
        self.close()
