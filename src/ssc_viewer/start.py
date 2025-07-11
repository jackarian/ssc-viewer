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
import stomp

basedir=os.path.dirname(__file__)
decimal.getcontext().rounding = decimal.ROUND_HALF_EVEN
class MyWidget(QtWidgets.QWidget,ConnectionObserver,stomp.ConnectionListener):
    def __init__(self,app=None,ws_uri=None, topic=None):
        super().__init__()
        geometry = QGuiApplication.primaryScreen().geometry()
        self.labelWidth= int(geometry.width() / 2)
        self._configureFromFile()
        self.tag=self.config['station']['tag']
        self.thread:Thread= None
        self.secondi = 0
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_counter)
        self.timer.start()

        self.titleLabel = QtWidgets.QLabel('Title')
        self.titleLabel.setPixmap(QPixmap(os.path.join(basedir,'./img/padovamusic.png')))
        self.titleLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setFixedHeight(103)
        self.roomName = QtWidgets.QLabel(self.config['station']['name'])
        self.roomName.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.roomName.setFixedHeight(103)
        self.roomName.setStyleSheet("QLabel {background-color: #fff; font-size: 50px; font-weight: bold; color: #e31100}")
        """
        Labels to show reservation time info 
        """
        self.infoLabel = QtWidgets.QLabel('Info prenotazione:')
        self.infoLabel.setStyleSheet("QLabel {background-color: #fff; border: 1px solid black; border-radius: 10px; font-size: 35px; font-weight: bold; color:#e31100;}")
        self.infoLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.infoLabel.setFixedWidth(self.labelWidth)

        self.infoStartPrenotazione = QtWidgets.QLabel('')
        self.infoStartPrenotazione.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.infoStartPrenotazione.setFixedWidth(self.labelWidth)
        self.infoStartPrenotazione.setStyleSheet("QLabel {background-color: #fff; border-top: 1px solid black; border-radius: 10px; font-size: 20px; font-weight: bold;color:#e31100;}")

        self.infoEndReservation = QtWidgets.QLabel('')
        self.infoEndReservation.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.infoEndReservation.setFixedWidth(self.labelWidth)
        self.infoEndReservation.setStyleSheet("QLabel {background-color: #fff; border-bottom: 1px solid black; border-radius: 10px; font-size: 20px; font-weight: bold;color:#e31100;}")
        """
        Labels to show time info
        """
        self.timeLabel = QtWidgets.QLabel('')
        self.timeLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.timeLabel.setStyleSheet("QLabel {background-color: #fff; border: 1px solid black; border-radius: 10px; font-size: 30px; font-weight: bold; color:#e31100;}")
        self.timeLabel.setFixedWidth(self.labelWidth)
        self.progressBar = QtWidgets.QProgressBar()
        self.progressBar.setStyleSheet(""" 
        QProgressBar { 
        border: 2px solid grey; 
        border-radius: 5px;  
        text-align: center;
        } 
        QProgressBar::chunk {
        background-color: #e31100;
        width: 20px;
        }
        """)
        self.progressBar.setFixedWidth(self.labelWidth)
        self.progressBar.setVisible(False)
        """
        """
        self.massageLabel = QtWidgets.QLabel('')
        self.connectionButton = QtWidgets.QPushButton('Connect')
        self.connectionButton.setStyleSheet("""
        QPushButton {
            border: 2px solid #e31100;
            border-radius: 10px;
            min-width: 80px;
            color: #e31100;
        }

        QPushButton:flat {
            border: none; /* no border for a flat push button */
        }

        QPushButton:default {
            border-color: navy; /* make the default button prominent */
        }        
        """)
        self.connectionButton.setFixedWidth(int(self.labelWidth / 2))
        self.connectionButton.clicked.connect(self.reconnect)
        self.connectionButton.setVisible(False)
        """
        """
        self.connected = False


        self.lMainVertical = QtWidgets.QVBoxLayout()
        self.lMainVertical.addWidget(self.titleLabel)
        self.lMainVertical.addWidget(self.roomName)

        self.lHExternalRows = QtWidgets.QHBoxLayout()
        self.lBottomRow = QtWidgets.QHBoxLayout()
        self.lBottomRow.setSpacing(0)
        self.lBottomRow.setContentsMargins(0,0,0,0)

        self.lMainVertical.addLayout(self.lHExternalRows)
        self.lMainVertical.addLayout(self.lBottomRow)

        self.lCentraColumn = QtWidgets.QVBoxLayout()
        self.lHExternalRows.addLayout(self.lCentraColumn)


        self.lBottomRow.addWidget(self.connectionButton)
        self.lBottomRow.addWidget(self.massageLabel)

        """
        Layout for time info
        """
        self.lCentraColumn.addWidget(self.progressBar)
        self.lCentraColumn.addWidget(self.timeLabel)
        self.lCentraColumn.addWidget(self.infoLabel)
        self.lCentraColumn.addWidget(self.infoStartPrenotazione)
        self.lCentraColumn.addWidget(self.infoEndReservation)
        """
        """

        self.setLayout(self.lMainVertical)

        self.resize(geometry.width(), geometry.height())
        self.uri = ws_uri
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
            self.progressBar.setVisible(False)
            self.timeLabel.setText('Nessuna Prenotazione')
            self.infoStartPrenotazione.setText('')
            self.infoEndReservation.setText('')
        else:
            if not self.progressBar.isVisible():
                self.progressBar.setVisible(True)
                self.progressBar.setMinimum(0)
                self.progressBar.setMaximum(self.secondi)

            ore, mi = divmod(float(self.secondi), 3600)
            m, s = divmod(float(mi), 60)
            self.timeLabel.setText('Chiusura prenotazion tra : ' + str(int(ore))+":"+str(int(m))+":"+str(int(s)))
            self.secondi -= 1
            self.progressBar.setValue(self.secondi)



    def _configureFromFile(self):
        home = str(Path.home())
        with open(r'' + home + '/config/gui.yaml') as file:
            self.config = yaml.load(file, Loader=yaml.FullLoader)
        print(self.config)

    def stopTimer(self):
        self.timer.stop()

    def clearError(self):
        self.connectionButton.setVisible(False)
        self.massageLabel.setText("")

    def onReceiveMessage(self, message:Frame):
        print(message)
        try:
            payload = json.loads(message.body)
            if payload['resourceTag'] ==self.tag:
                self.progressBar.setVisible(False)
                self.start = datetime.fromisoformat(str(payload['startTime']))
                self.end   = datetime.fromisoformat(str(payload['endTime']))
                delta =  (self.end - self.start)
                self.secondi = delta.total_seconds()
                self.infoStartPrenotazione.setText("Inizio: "+self.start.isoformat())
                self.infoEndReservation.setText("Fine: "+self.end.isoformat())


        except json.decoder.JSONDecodeError:
            _logging.error(f"received message {message}: {message}")
            self.massageLabel.setText(f"received message {message}: {message}")



    def connectToBroker(self):
        if not self.client.connected:
            self.thread = Thread(target=self.client.connect,kwargs= {'connectCallback': self.onConnected,'timeout': 10000})
            self.thread.daemon = True
            self.thread.start()

    def reconnect(self):
        if not self.client.connected:
            self.client.stop()
            self.client=None
            self.thread.join()
            self.thread = None
            self.client=Client(self.uri, self)
            self.connectToBroker()


    def onConnected(self, frame):
        self.connected = True
        self.client.subscribe(self.topic, callback=self.onReceiveMessage)
        self.connectionButton.setVisible(False)
        self.massageLabel.setText("")

    def notifyOnClose(self, observable=None, message=None, exception=None):
        self.connectionButton.setVisible(True)
        self.massageLabel.setText("")
    def notifyOnOpen(self, observable=None, message=None, exception=None):
        self.connectionButton.setVisible(False)

    def notifyOnMessage(self, observable=None, message=None, exception=None):
        pass

    def notifyOnError(self, observable=None, message=None, exception=None):
        self.connected = False
        self.massageLabel.setText("Errore conessione al server")
        self.connectionButton.setVisible(True)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName("Reservation Info")
    widget = MyWidget(app,"ws://totem:8080/ssc/prenostazione-risorse/websocket",
                       "/scheduler")


    sys.exit(app.exec())
