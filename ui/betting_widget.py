from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

class BettingWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.label = QLabel("배팅 상태")
        layout.addWidget(self.label)

        self.setLayout(layout)
