from paho.mqtt import client as mqtt_client
import random
import logging

from ssc_viewer.interfaces.observer import ConnectionObserver

logging.basicConfig(level=logging.DEBUG)

class ClientMqttController():
    def __init__(self,broker,port=1883, topic=None,username=None,password=None, observer: ConnectionObserver=None,
                 client_id =None):
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
         self.observers = list()
         if observer is not None:
            self.addObserver(observer)

    def addObserver(self,observer:ConnectionObserver):
        self.observers.append(observer)

    def startConnection(self):
        if self.username is not None and self.password is not None:
           self.client.username_pw_set(self.username,self.password)
        self.client.on_connect = self.onConnect
        self.client.on_message=self.onMessage
        self.client.on_disconnect=self.onDisconnect
        self.client.connect(self.broker,self.port)              
        self.client.loop_forever()

    def closeConnection(self):
        self.client.disconnect()

    def onDisconnect(self,client, userdata, disconnect_flags, reason_code, properties):
        pass

    def onConnect(self,client, userdata, flags, reason_code, properties):
         if reason_code == 0:
            print("Connected to MQTT Broker!")
            self.client.subscribe(self.topic)
            for observer in self.observers:
             observer.notifyOnOpen(observable=self,message='Connected to mqtt server')
         else:
            print("Failed to connect, return code %d\n", reason_code)
            for observer in self.observers:
             observer.notifyOnError(self,message='Failed to connect to mqtt server')

    def onMessage(self,client, userdata, msg):
        print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
        for observer in self.observers:
            observer.onReceiveMessage(msg.payload.decode())
        
if __name__ == '__main__':
     broker = 'mqtt.back-iot.it'
     port = 1883
     topic = "padova/entry"
     # Generate a Client ID with the subscribe prefix.
     client_id = f'subscribe-{random.randint(0, 100)}'
     username = 'jackarian'
     password = 'knl3M00coj'             
     client = ClientMqttController(broker=broker,
                                   topic=topic,
                                   port=port,
                                   username=username,
                                   password=password,
                                   client_id= f'subscribe-{random.randint(0, 100)}',
                                   observer=None)
     client.startConnection()
