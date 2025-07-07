import json
import os.path
import sys
from datetime import datetime
from pathlib import Path
from threading import Thread

import yaml
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QKeySequence, QGuiApplication, QPixmap, QImage
from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import QApplication, QWidget
from websocket import _logging

from interfaces.observer import ConnectionObserver
from rest import restclient
from ssc_viewer.rest.restclient import SscClient
from ssc_viewer.stomp_ws.client import Client
from ssc_viewer.stomp_ws.frame import Frame
import decimal
from decimal import Decimal
from datetime import datetime, time, timedelta

basedir=os.path.dirname(__file__)
decimal.getcontext().rounding = decimal.ROUND_HALF_EVEN
class MyWidget(QtWidgets.QWidget,ConnectionObserver):
    def __init__(self,app=None,ws_uri=None, topic=None):
        super().__init__()
        self.secondi = 0
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_counter)
        self.timer.start()
        self.titleLabel = QtWidgets.QLabel('')
        self.titleLabel.setPixmap(QPixmap(os.path.join(basedir,'./img/padovamusic.png')))

        self.titleLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.infoLabel = QtWidgets.QLabel('Info')
        self.infoLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.timeLabel = QtWidgets.QLabel('Time')
        self.timeLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.messageLabel = QtWidgets.QLabel('Message')
        self.messageLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.connected = False
        self._configureFromFile()

        self.lMainVertical = QtWidgets.QVBoxLayout()
        self.lMainVertical.addWidget(self.titleLabel)

        self.lHExternalRows = QtWidgets.QHBoxLayout()
        self.lBottomRow = QtWidgets.QHBoxLayout()
        self.lMainVertical.addLayout(self.lHExternalRows)
        self.lMainVertical.addLayout(self.lBottomRow)

        self.lLeftColumn = QtWidgets.QHBoxLayout()
        self.lCentraColumn = QtWidgets.QHBoxLayout()
        self.lRightColumn = QtWidgets.QHBoxLayout()

        self.lHExternalRows.addLayout(self.lCentraColumn)
        self.lBottomRow.addLayout(self.lLeftColumn)
        self.lBottomRow.addLayout(self.lRightColumn)

        self.lLeftColumn.addWidget(self.infoLabel)
        self.lCentraColumn.addWidget(self.timeLabel)
        self.lRightColumn.addWidget(self.messageLabel)

        self.setLayout(self.lMainVertical)
        geometry = QGuiApplication.primaryScreen().geometry()
        self.resize(geometry.width(), geometry.height())

        self.start = None
        self.end = None
        ##self.showFullScreen()
        sscCli = SscClient(self.config['server']['address'], self.config['plc']['id'])
        self.client = Client(ws_uri, self)
        self.topic = topic
        self.connectToBroker()
        self.show()

    @QtCore.Slot()
    def update_counter(self):
        if self.secondi == 0:
            self.timeLabel.setText('Secondi:' + str(self.secondi))
        else:
            ore, mi = divmod(float(self.secondi), 3600)
            m, s = divmod(float(mi), 60)
            self.timeLabel.setText('Time left:' + str(int(ore))+":"+str(int(m))+":"+str(int(s)))
            self.secondi -= 1


    def _configureFromFile(self):
        home = str(Path.home())
        with open(r'' + home + '/config/gui.yaml') as file:
            self.config = yaml.load(file, Loader=yaml.FullLoader)
        print(self.config)

    def stopTimer(self):
        self.timer.stop()

    def onReceiveMessage(self, message:Frame):
        print(message)
        try:
            payload = json.loads(message.body)
            self.start = datetime.fromisoformat(str(payload['startTime']))
            self.end   = datetime.fromisoformat(str(payload['endTime']))
            self.messageLabel.setText("Current Reservation:"+self.start.isoformat())
            ds = timedelta(hours=self.start.hour,minutes=self.start.minute,seconds=self.start.second)
            de = timedelta(hours=self.end.hour, minutes=self.end.minute, seconds=self.end.second)
            delta = de - ds
            self.secondi = delta.total_seconds()




        except json.decoder.JSONDecodeError:
            _logging.error(f"received message {message}: {message}")



    def connectToBroker(self):
        if not self.client.connected:
            thread = Thread(target=self.client.connect,
                            kwargs=
                            {'connectCallback': self.onConnected, 'timeout': 10000})
            thread.daemon = True
            thread.start()

    def onConnected(self, frame):
        self.connected = True
        self.client.subscribe(self.topic, callback=self.onReceiveMessage)

    def notifyOnClose(self, observable=None, message=None, exception=None):
        pass

    def notifyOnOpen(self, observable=None, message=None, exception=None):
        pass

    def notifyOnMessage(self, observable=None, message=None, exception=None):
        pass

    def notifyOnError(self, observable=None, message=None, exception=None):
        print(message)
        print(exception)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Reservation Info")
    widget = MyWidget(app,"ws://localhost:8080/ssc/prenostazione-risorse/websocket",
                       "/scheduler")


    sys.exit(app.exec())
