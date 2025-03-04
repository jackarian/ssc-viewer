import sys
import random

from PySide6.QtGui import QAction, QKeySequence, QGuiApplication
from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import QApplication

from interfaces.observer import ConnectionObserver


class MyWidget(QtWidgets.QWidget,ConnectionObserver):
    def __init__(self):
        super().__init__()

        self.hello = ["Hallo Welt", "Hei maailma", "Hola Mundo", "Привет мир"]

        self.button = QtWidgets.QPushButton("Click me!")
        self.text = QtWidgets.QLabel("Hello World",
                                     alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.button)
        self.layout.addWidget(self.text)


        self.button.clicked.connect(self.magic)

        geometry = QGuiApplication.primaryScreen().geometry()
        self.resize(geometry.width(), geometry.height())
        self.show()

    @QtCore.Slot()
    def magic(self):
        self.text.setText(random.choice(self.hello))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Reservation Info")
    widget = MyWidget()
    ##widget.show()
    sys.exit(app.exec())
