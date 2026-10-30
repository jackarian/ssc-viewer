import decimal
import json
import logging
import os.path
import sys
from requests import Response
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Thread
import yaml
from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtGui import QGuiApplication, QPixmap, Qt
from PySide6.QtWidgets import QApplication

from ssc_viewer.mqqt.mqtt_client import ClientMqttController
from ssc_viewer.rest.restclient import SscClient
from ssc_viewer.stomp_ws.client import Client
from ssc_viewer.stomp_ws.frame import Frame
from ssc_viewer.stylesheet.interface_styles import ROM_NAME_STYLE, INFO_LABEL_STYLE, PROGRESS_LABEL_STYLE, \
    CONNECTION_BUTTON_STYLE

from interfaces.observer import ConnectionObserver

basedir=os.path.dirname(__file__)
decimal.getcontext().rounding = decimal.ROUND_HALF_EVEN
NESSUNA_SESSIONE_IN_CORSO = "Nessuna sessione in corso"
CONNECT="Connect"
DISCONNECT="Disconnect"
APPLICATION_NAME="Reservation Info"


def set_logger(logger: logging.Logger):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    h = RotatingFileHandler(filename=os.path.join(basedir, './log/app.log'), mode='a', maxBytes=1048576,
                            backupCount=10)
    h.setLevel(logging.INFO)
    h.setFormatter(formatter)
    logger.addHandler(h)
WEBSOCKET="websocket"
MQTT="mqtt"
# delay between two attempts to reconnect to the SSC websocket
RECONNECT_DELAY_MS=5000

class ObserverMessageDispatcher(QObject):
    """
    I client STOMP e MQTT notificano dai loro thread: i segnali portano
    gli eventi nel thread della GUI, l'unico che puo' aggiornare i widget.
    """
    opened = Signal(str)
    closed = Signal(str)
    error = Signal(str,str)
    reservation = Signal(object)

class MyWidget(QtWidgets.QWidget,ConnectionObserver):
    # noinspection PyTypeChecker
    def __init__(self,app=None,ws_uri=None, topic=None,fullscreen=True,logger=None):
        super().__init__()
        if logger is None:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            set_logger(self.logger)
        else:
            self.logger = logger

        self.lCentraColumn:QtWidgets = None
        self.lBottomRow:QtWidgets = None
        self.lHExternalRows:QtWidgets = None
        self.lMainVertical:QtWidgets = None
        geometry = QGuiApplication.primaryScreen().geometry()
        self.labelWidth= int(geometry.width() / 2)
        self._configureFromFile()
        self.tag=self.config['station']['tag']
        self.thread:Thread= None
        self.secondi = 0


        self.titleLabel = QtWidgets.QLabel('')
        self.titleLabel.setPixmap(QPixmap(os.path.join(basedir,'./img/padovamusic.png')))
        self.titleLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setFixedHeight(103)
        self.roomName = QtWidgets.QLabel(self.config['station']['name'])
        self.roomName.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.roomName.setFixedHeight(103)
        self.roomName.setStyleSheet(ROM_NAME_STYLE)
        """
        Labels to show reservation time info 
        """
        self.infoLabel = QtWidgets.QLabel('Info prenotazione:')
        self.infoLabel.setStyleSheet(INFO_LABEL_STYLE)
        self.infoLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.infoLabel.setFixedWidth(self.labelWidth)

        #self.infoStartPrenotazione = QtWidgets.QLabel('')
        #self.infoStartPrenotazione.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        #self.infoStartPrenotazione.setFixedWidth(self.labelWidth)
        #self.infoStartPrenotazione.setStyleSheet("QLabel {background-color: #fff; border-top: 1px solid black; border-radius: 10px; font-size: 20px; font-weight: bold;color:#e31100;}")

        self.infoEndReservation = QtWidgets.QLabel('')
        self.infoEndReservation.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.infoEndReservation.setFixedWidth(self.labelWidth)
        self.infoEndReservation.setStyleSheet("QLabel {background-color: #fff; border-bottom: 1px solid black; border-radius: 10px; font-size: 20px; font-weight: bold;color:#e31100;}")
        """
        Labels to show time info
        """
        self.timeLabel = QtWidgets.QLabel('')
        self.timeLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.timeLabel.setStyleSheet("QLabel {background-color: #fff; border: 1px solid black; border-radius: 10px; font-size: 20px; font-weight: bold; color:#e31100;}")
        self.timeLabel.setFixedWidth(self.labelWidth)
        self.progressBar = QtWidgets.QProgressBar()
        self.progressBar.setStyleSheet(PROGRESS_LABEL_STYLE)
        self.progressBar.setFixedWidth(self.labelWidth)
        self.progressBar.setVisible(False)
        """
        """
        self.massageLabel = QtWidgets.QLabel('')
        self.connectionButton = QtWidgets.QPushButton(CONNECT)
        self.connectionButton.setStyleSheet(CONNECTION_BUTTON_STYLE)
        self.connectionButton.setFixedWidth(int(self.labelWidth / 2))
        self.connectionButton.clicked.connect(self.reconnect)
        self.connectionButton.setVisible(False)
        """
        """
        self.connected = False

        self.setLabels()

        """
        Layout for time info
        """
        self.lCentraColumn.addWidget(self.progressBar)
        self.lCentraColumn.addWidget(self.timeLabel)
        #self.lCentraColumn.addWidget(self.infoLabel)
        #self.lCentraColumn.addWidget(self.infoStartPrenotazione)
        self.lCentraColumn.addWidget(self.infoEndReservation)
        """
        """

        self.setLayout(self.lMainVertical)

        self.resize(geometry.width(), geometry.height())
        self.uri = ws_uri
        self.start = None
        self.end = None
        if fullscreen:
            self.showFullScreen()
        self.sscCli = SscClient(self.config['server']['proto']+'://'
            +self.config['server']['address']
                                +':'+str(self.config['server']['port'])
                                +self.config['server']['resource'],
                                 self.config['plc']['id'])
        """
        Instantiate observer dispatcher
        """
        self.dispatcher = ObserverMessageDispatcher()
        self.dispatcher.opened.connect(self._onOpened)
        self.dispatcher.closed.connect(self._onClosed)
        self.dispatcher.error.connect(self._onError)
        self.dispatcher.reservation.connect(self._onReservation)
        self.client = Client(ws_uri, self)
        self.topic = topic
        self.mqttClient  = ClientMqttController(broker=self.config['mqtt']['broker'],
                                   topic=self.config['mqtt']['topic'],
                                   port=self.config['mqtt']['port'],
                                   username=self.config['mqtt']['username'],
                                   password=self.config['mqtt']['password'],
                                   observer=self,
                                   client_id=self.config['mqtt']['client_id'],
                                   tls=True)
        #############################
        # Timer setup

        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.update_counter)
        ##########################
        # Websocket reconnect timer
        self.closing = False
        self.reconnectTimer = QTimer(self)
        self.reconnectTimer.setSingleShot(True)
        self.reconnectTimer.setInterval(RECONNECT_DELAY_MS)
        self.reconnectTimer.timeout.connect(self._autoReconnect)
        ##########################

        self.connectToBroker()
        self.show()
        self.mqttClient.startConnection();

    """
    Slots running in the GUI thread. The connection button reconnects only the
    websocket: the mqtt client reconnects by itself.
    """
    @QtCore.Slot(str)
    def _onOpened(self, source):
        if source == WEBSOCKET:
            self.connectionButton.setVisible(False)
        self.massageLabel.setText("")

    @QtCore.Slot(str)
    def _onClosed(self, source):
        if source == WEBSOCKET:
            self.connectionButton.setVisible(True)
            self._scheduleReconnect()
        self.massageLabel.setText("")

    @QtCore.Slot(str,str)
    def _onError(self, source, error):
        self.logger.error(f"{source}: {error}")
        if source == WEBSOCKET:
            self.connected = False
            self.connectionButton.setVisible(True)
            self.connectionButton.setEnabled(True)
            self._scheduleReconnect()
        self.massageLabel.setText("Error connecting to broker.")

    def _scheduleReconnect(self):
        if not self.closing and not self.reconnectTimer.isActive():
            self.logger.info(f"websocket: reconnecting in {RECONNECT_DELAY_MS // 1000} s")
            self.reconnectTimer.start()

    @QtCore.Slot()
    def _autoReconnect(self):
        if self.thread is not None and self.thread.is_alive():
            # previous attempt still waiting for its timeout
            self._scheduleReconnect()
            return
        self.reconnect()

    @QtCore.Slot(object)
    def _onReservation(self, payload):
        try:
            self._setReservation(payload)
        except Exception as ex:
            self.logger.error(f"received message {payload}")
            self.logger.exception(ex)

    """
    Setting layout 
    """
    def setLabels(self):
        self.lMainVertical = QtWidgets.QVBoxLayout()
        self.lMainVertical.addWidget(self.titleLabel)
        self.lMainVertical.addWidget(self.roomName)
        self.lHExternalRows = QtWidgets.QHBoxLayout()
        self.lBottomRow = QtWidgets.QHBoxLayout()
        self.lBottomRow.setSpacing(0)
        self.lBottomRow.setContentsMargins(0, 0, 0, 0)
        self.lMainVertical.addLayout(self.lHExternalRows)
        self.lMainVertical.addLayout(self.lBottomRow)
        self.lCentraColumn = QtWidgets.QVBoxLayout()
        self.lHExternalRows.addLayout(self.lCentraColumn)
        self.lBottomRow.addWidget(self.connectionButton)
        self.lBottomRow.addWidget(self.massageLabel)

    @QtCore.Slot()
    def update_counter(self):
       try:
            if self.secondi <= 0 :
                self.progressBar.setVisible(False)
                self.timeLabel.setText(NESSUNA_SESSIONE_IN_CORSO)
                self.infoEndReservation.setText('')
            else:
                if not self.progressBar.isVisible():
                    self.progressBar.setVisible(True)
                    self.progressBar.setMinimum(0)
                    self.progressBar.setMaximum(self.secondi)

                ore, mi = divmod(float(self.secondi), 3600)
                m, s = divmod(float(mi), 60)
                self.timeLabel.setText("La sessione finira'  tra : " + str(int(ore))+":"+str(int(m))+":"+str(int(s)))
                self.secondi -= 1
                self.progressBar.setValue(self.secondi)

            ##self.reconnect()

       except Exception as ex:
           self.logger.exception(ex)


    def _configureFromFile(self):
        home = str(Path.home())
        with open(r'' + home + '/config/gui.yaml') as file:
            self.config = yaml.load(file, Loader=yaml.FullLoader)
        self.logger.info(self.config)

    def stopTimer(self):
        self.timer.stop()

    def clearError(self):
        self.connectionButton.setVisible(False)
        self.massageLabel.setText("")

    def onReceiveMessage(self, message:Frame):
        self.logger.debug(message.body)
        try:
            self.dispatcher.reservation.emit(json.loads(message.body))
        except json.decoder.JSONDecodeError as ex:
            self.logger.error(f"received message {message.body}")
            self.logger.error(ex)

    def _setReservation(self,payload):
        self.logger.debug(payload)
        if payload.get('resourceTag') ==self.tag:
            self.progressBar.setVisible(False)
            self.start = datetime.fromisoformat(str(payload['startTime']))
            self.end   = datetime.fromisoformat(str(payload['endTime']))

            delta =  (self.end - datetime.now())
            self.secondi = delta.total_seconds()
            self.infoEndReservation.setText("Fine sessione: "+self.end.strftime("%H:%M"))

    def connectToBroker(self):
        if not self.client.connected:
            self.thread = Thread(target=self.client.connect,kwargs= {'connectCallback': self.onConnected,'timeout': 10000})
            self.thread.daemon = True
            self.thread.start()
            self.timer.start()

    def reconnect(self):

        try:
            if self.client is None or   not self.client.connected:

                self.connectionButton.setEnabled(False)
                self.massageLabel.setText("Trying connecting to broker.")
                if self.client is not None:
                      self.client.stop()
                self.client=None
                self.thread.join()
                self.thread = None
                self.client=Client(self.uri, self)
                self.connectToBroker()
        except Exception  as ex:
                self.logger.log(level=logging.ERROR, msg=ex.__str__())
                self.connectionButton.setEnabled(True)


    def onConnected(self, frame):
        self.connected = True
        self.client.subscribe(self.topic, callback=self.onReceiveMessage)
        self.dispatcher.opened.emit(WEBSOCKET)
        self.sscCli.currentReservation(self.tag,callback=self.manageResponse)

    def manageResponse(self,response:Response):
        self.logger.log(level=logging.INFO, msg=response)
        if response.status_code == 200:
            body = response.json()
            if body['result'] is not None:
                self.dispatcher.reservation.emit(body['result'])

    """
    ConnectionObserver callbacks: called from the client threads, they only
    forward the event to the GUI thread.
    """
    @staticmethod
    def _source(observable):
        return MQTT if isinstance(observable, ClientMqttController) else WEBSOCKET

    def _isStale(self, observable):
        # late events from a websocket client already replaced by reconnect()
        client = self.client
        return (self._source(observable) == WEBSOCKET and client is not None
                and observable is not client and observable is not client.ws)

    def notifyOnClose(self, observable=None, message=None, exception=None):
        if not self._isStale(observable):
            self.dispatcher.closed.emit(self._source(observable))

    def notifyOnOpen(self, observable=None, message=None, exception=None):
        if not self._isStale(observable):
            self.dispatcher.opened.emit(self._source(observable))

    def notifyOnMessage(self, observable=None, message=None, exception=None):
        self.dispatcher.reservation.emit(message)

    def notifyOnError(self, observable=None, message=None, exception=None):
        if self._isStale(observable):
            return
        self.dispatcher.error.emit(self._source(observable), str(exception or message))

    def closeEvent(self, event) -> None:
        self.logger.log(level=logging.INFO, msg=event)
        self.closing = True
        self.reconnectTimer.stop()
        self.mqttClient.closeConnection()


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(255,255,255))
        app.setApplicationName(APPLICATION_NAME)
        app.setPalette(palette)
        widget = MyWidget(app,"ws://service.local:8080/ssc/prenostazione-risorse/websocket",
                           "/scheduler",False)
        sys.exit(app.exec())
    except Exception as ex:
        print(ex)
