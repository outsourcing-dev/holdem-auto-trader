from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class HistoryWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.label = QLabel("거래 내역")
        layout.addWidget(self.label)

        self.setLayout(layout)
