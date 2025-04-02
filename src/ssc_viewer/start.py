import sys
import random
from pathlib import Path

import yaml
from PySide6.QtGui import QAction, QKeySequence, QGuiApplication
from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import QApplication

from interfaces.observer import ConnectionObserver
from rest import restclient
from ssc_viewer.rest.restclient import SscClient


class MyWidget(QtWidgets.QWidget,ConnectionObserver):
    def __init__(self,app=None):
        super().__init__()
        self._configureFromFile()

        self.button = QtWidgets.QPushButton("Click me!")

        self.layout = QtWidgets.QVBoxLayout(self)
        self.button.setCheckable(True)
        self.layout.addWidget(self.button)
        self.button.clicked.connect(self.magic)
        self.button.clicked.connect(self.printCheckStatus)


        geometry = QGuiApplication.primaryScreen().geometry()
        self.resize(geometry.width(), geometry.height())
        self.show()
        ##self.showFullScreen()
        sscCli = SscClient(self.config['server']['address'], self.config['plc']['id'])

    @QtCore.Slot()
    def magic(self):
        print("Button pressed")

    @QtCore.Slot()
    def printCheckStatus(self,checkStatus):
        print("Is checked?",checkStatus)

    def _configureFromFile(self):
        home = str(Path.home())
        with open(r'' + home + '/config/gui.yaml') as file:
            self.config = yaml.load(file, Loader=yaml.FullLoader)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Reservation Info")
    widget = MyWidget(app)

    ##widget.show()
    sys.exit(app.exec())
