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
from ssc_viewer.stylesheet.interface_styles import ROM_NAME_STYLE, CONNECTION_BUTTON_STYLE, CLOCK_STYLE, \
    SECONDARY_STYLE, RED, GREEN, ORANGE, status_style, progress_style

from interfaces.observer import ConnectionObserver

basedir=os.path.dirname(__file__)
decimal.getcontext().rounding = decimal.ROUND_HALF_EVEN
SALA_LIBERA = "Sala libera"
SESSIONE_IN_CORSO = "Sessione in corso"
# last minutes of the session shown in orange
WARNING_SECONDS = 5 * 60
GIORNI = ("lun", "mar", "mer", "gio", "ven", "sab", "dom")
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre")
CONNECT="Connect"
DISCONNECT="Disconnect"
APPLICATION_NAME="Reservation Info"
# SSC of the location, on the totem: gui.yaml server.websocket overrides it
DEFAULT_WS_URI="ws://totem.padova:8080/ssc/prenostazione-risorse/websocket"
# MQTT ports with TLS: gui.yaml mqtt.tls overrides it
MQTT_TLS_PORTS=(8883, 8884)
SECRET_KEYS=('password', 'api_key')


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
        self.lMainVertical:QtWidgets = None
        geometry = QGuiApplication.primaryScreen().geometry()
        self.labelWidth= int(geometry.width() / 2)
        self._configureFromFile()
        self.tag=self.config['station']['tag']
        # the room configs installed so far have no websocket, proto, resource, fullscreen keys
        server = self.config['server']
        if ws_uri is None:
            ws_uri = server.get('websocket', DEFAULT_WS_URI)
        if fullscreen is None:
            fullscreen = self.config['station'].get('fullscreen', True)
        self.thread:Thread= None


        self.titleLabel = QtWidgets.QLabel('')
        self.titleLabel.setPixmap(QPixmap(os.path.join(basedir,'./img/padovamusic.png')))
        self.titleLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.titleLabel.setFixedHeight(103)
        """
        Clock: current time and date, top right
        """
        self.clockLabel = QtWidgets.QLabel('')
        self.clockLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.clockLabel.setStyleSheet(CLOCK_STYLE)
        self.dateLabel = QtWidgets.QLabel('')
        self.dateLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.dateLabel.setStyleSheet(SECONDARY_STYLE)
        self.roomName = QtWidgets.QLabel(self.config['station']['name'])
        self.roomName.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.roomName.setStyleSheet(ROM_NAME_STYLE)
        """
        Session status, remaining time and slot
        """
        self.statusLabel = QtWidgets.QLabel('')
        self.statusLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.timeLabel = QtWidgets.QLabel('')
        self.timeLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.intervalLabel = QtWidgets.QLabel('')
        self.intervalLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.intervalLabel.setStyleSheet(SECONDARY_STYLE)
        self.progressBar = QtWidgets.QProgressBar()
        self.progressBar.setRange(0, 1000)
        self.progressBar.setTextVisible(False)
        self.progressBar.setFixedWidth(self.labelWidth)
        self.progressBar.setVisible(False)
        # colour of the current state, to restyle only when it changes
        self.stateColor = None
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

        self.setLayout(self.lMainVertical)

        self.resize(geometry.width(), geometry.height())
        self.uri = ws_uri
        self.start = None
        self.end = None
        if fullscreen:
            self.showFullScreen()
        self.sscCli = SscClient(server.get('proto', 'http')+'://'
                                +server['address']
                                +':'+str(server['port'])
                                +server.get('resource', '/ssc'),
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
        # MQTT is optional: without the mqtt section only the websocket is used
        mqtt = self.config.get('mqtt')
        self.mqttClient = None
        if mqtt:
            self.mqttClient  = ClientMqttController(broker=mqtt['broker'],
                                   topic=mqtt['topic'],
                                   port=mqtt['port'],
                                   username=mqtt['username'],
                                   password=mqtt['password'],
                                   observer=self,
                                   client_id=mqtt['client_id'],
                                   tls=mqtt.get('tls', mqtt['port'] in MQTT_TLS_PORTS))
        #############################
        # Timer setup

        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.update_counter)
        self.timer.start()
        self.update_counter()
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
        if self.mqttClient is not None:
            self.mqttClient.startConnection()

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
        self.lMainVertical.setContentsMargins(24, 16, 24, 16)
        # logo centred and clock on the right: three columns of the same width
        lTop = QtWidgets.QGridLayout()
        lClock = QtWidgets.QVBoxLayout()
        lClock.setSpacing(0)
        lClock.addWidget(self.clockLabel)
        lClock.addWidget(self.dateLabel)
        lTop.addWidget(self.titleLabel, 0, 1)
        lTop.addLayout(lClock, 0, 2)
        for column in range(3):
            lTop.setColumnStretch(column, 1)
        self.lMainVertical.addLayout(lTop)
        self.lMainVertical.addWidget(self.roomName)
        self.lCentraColumn = QtWidgets.QVBoxLayout()
        self.lCentraColumn.addStretch(1)
        self.lCentraColumn.addWidget(self.statusLabel)
        self.lCentraColumn.addWidget(self.timeLabel)
        self.lCentraColumn.addWidget(self.intervalLabel)
        self.lCentraColumn.addWidget(self.progressBar, 0, Qt.AlignmentFlag.AlignHCenter)
        self.lCentraColumn.addStretch(2)
        self.lMainVertical.addLayout(self.lCentraColumn, 1)
        self.lBottomRow = QtWidgets.QHBoxLayout()
        self.lBottomRow.setSpacing(0)
        self.lBottomRow.setContentsMargins(0, 0, 0, 0)
        self.lMainVertical.addLayout(self.lBottomRow)
        self.lBottomRow.addWidget(self.connectionButton)
        self.lBottomRow.addWidget(self.massageLabel)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # font sizes follow the window height: readable from the back of the room
        height = max(self.height(), 400)
        for label, ratio, bold in ((self.clockLabel, 0.08, True), (self.dateLabel, 0.03, False),
                                   (self.roomName, 0.065, True), (self.statusLabel, 0.06, True),
                                   (self.timeLabel, 0.18, True), (self.intervalLabel, 0.045, False)):
            font = label.font()
            font.setPixelSize(int(height * ratio))
            font.setBold(bold)
            label.setFont(font)
        self.progressBar.setFixedHeight(int(height * 0.025))

    @QtCore.Slot()
    def update_counter(self):
       try:
            now = datetime.now()
            self.clockLabel.setText(now.strftime("%H:%M"))
            self.dateLabel.setText(f"{GIORNI[now.weekday()]} {now.day} {MESI[now.month - 1]}")

            if self.end is not None and now >= self.end:
                self.start = None
                self.end = None

            if self.start is not None and self.start <= now:
                # computed from the end of the slot at every tick: no drift if the timer is late
                remaining = int((self.end - now).total_seconds())
                total = (self.end - self.start).total_seconds()
                ore, resto = divmod(remaining, 3600)
                minuti, secondi = divmod(resto, 60)
                self._showState(SESSIONE_IN_CORSO, f"{ore:02d}:{minuti:02d}:{secondi:02d}",
                                f"dalle {self.start:%H:%M} alle {self.end:%H:%M}",
                                ORANGE if remaining <= WARNING_SECONDS else RED,
                                int(1000 * remaining / total) if total > 0 else 0)
            elif self.start is not None:
                self._showState(SALA_LIBERA, "",
                                f"prossima sessione dalle {self.start:%H:%M} alle {self.end:%H:%M}", GREEN, None)
            else:
                self._showState(SALA_LIBERA, "", "", GREEN, None)

       except Exception as ex:
           self.logger.exception(ex)

    def _showState(self, status, remaining, interval, color, progress):
        self.statusLabel.setText(status)
        self.timeLabel.setText(remaining)
        self.timeLabel.setVisible(bool(remaining))
        self.intervalLabel.setText(interval)
        self.progressBar.setVisible(progress is not None)
        if progress is not None:
            self.progressBar.setValue(progress)
        if color != self.stateColor:
            self.stateColor = color
            self.statusLabel.setStyleSheet(status_style(color))
            self.timeLabel.setStyleSheet(status_style(color))
            self.progressBar.setStyleSheet(progress_style(color))


    def _configureFromFile(self):
        home = str(Path.home())
        with open(r'' + home + '/config/gui.yaml') as file:
            self.config = yaml.load(file, Loader=yaml.FullLoader)
        # never write credentials to the log
        self.logger.info({section: {k: '***' if k in SECRET_KEYS else v for k, v in values.items()}
                          if isinstance(values, dict) else values
                          for section, values in self.config.items()})

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
            self.start = datetime.fromisoformat(str(payload['startTime']))
            self.end   = datetime.fromisoformat(str(payload['endTime']))
            self.update_counter()

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
        if self.mqttClient is not None:
            self.mqttClient.closeConnection()


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(255,255,255))
        app.setApplicationName(APPLICATION_NAME)
        app.setPalette(palette)
        # websocket and fullscreen from ~/config/gui.yaml
        widget = MyWidget(app, None, "/scheduler", None)
        sys.exit(app.exec())
    except Exception as ex:
        print(ex)
