import json
import logging
import random
import ssl
from getopt import error

import certifi
from paho.mqtt import client as mqtt_client
from ssc_viewer.interfaces.observer import ConnectionObserver

logging.basicConfig(level=logging.DEBUG)

class ClientMqttController:
    def __init__(self,broker,port=1883, topic=None,username=None,password=None, observer: ConnectionObserver=None,
                 client_id =None,tls=True):
         self.logger = logging.getLogger(__name__)
         self.client: mqtt_client.Client = mqtt_client.Client(callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
                       client_id=client_id)
         self.client.enable_logger(self.logger)
         self.client._userdata = True
         self.broker = broker
         self.username = username
         self.password = password
         self.port = port
         self.topic = topic
         self.tls = tls
         self.observers = list()
         if observer is not None:
            self.addObserver(observer)

    def addObserver(self,observer:ConnectionObserver):
        self.observers.append(observer)

    def startConnection(self):
        if self.username is not None and self.password is not None:
           self.client.username_pw_set(self.username,self.password)
        if self.tls is True:
            self.client.tls_set(ca_certs=certifi.where(),
                                tls_version=ssl.PROTOCOL_TLSv1_2,
                                cert_reqs=ssl.CERT_REQUIRED)
        self.client.on_connect = self.onConnect
        self.client.on_message=self.onMessage
        self.client.on_disconnect=self.onDisconnect
        self.client.connect_async(self.broker,self.port)
        self.client.loop_start()

    def closeConnection(self):
        self.client.loop_stop()
        self.client.disconnect()

    def onDisconnect(self,client, userdata, disconnect_flags, reason_code, properties):
        for observer in self.observers:
            observer.notifyOnClose(observable=self,message=f'Disconnected from mqtt server: {reason_code}')

    def onConnect(self,client, userdata, flags, reason_code, properties):
         if reason_code == 0:
            self.client.subscribe(self.topic)
            for observer in self.observers:
             observer.notifyOnOpen(observable=self,message='Connected to mqtt server')
         else:
            self.logger.error(f"Failed to connect, reason code {reason_code}")
            for observer in self.observers:
             observer.notifyOnError(self,message=f'Failed to connect to mqtt server: {reason_code}')

    def onMessage(self,client, userdata, msg):
        payload = msg.payload.decode(errors='ignore')
        self.logger.debug(f"Received `{payload}` from `{msg.topic}` topic")
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as ex:
            # an exception here would stop the paho network loop
            self.logger.error(f"Invalid message on `{msg.topic}`: {ex}")
            return
        for observer in self.observers:
            observer.notifyOnMessage(observable=self,message=payload)
        
if __name__ == '__main__':
     import yaml
     from pathlib import Path
     # broker and credentials come from the viewer config, never from the code
     with open(Path.home() / 'config' / 'gui.yaml') as file:
         mqtt = yaml.safe_load(file)['mqtt']
     client = ClientMqttController(broker=mqtt['broker'],
                                   topic=mqtt['topic'],
                                   port=mqtt['port'],
                                   username=mqtt['username'],
                                   password=mqtt['password'],
                                   client_id= f'subscribe-{random.randint(0, 100)}',
                                   observer=None)
     client.startConnection()
     input("Press Enter to stop\n")
     client.closeConnection()
