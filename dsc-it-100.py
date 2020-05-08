#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial, threading
import paho.mqtt.client as mqtt
import time, ssl, random
import datetime

# client, user and device details
serverUrl   = "localhost"
username    = "<<username>>"
password    = "<<password>>"

clientId    = "dscNH8"
deviceName  = "DSC IT-100"
serialPort  = "/dev/ttyUSB0"

class DSCIT100(threading.Thread):
  def __init__(self, clientId, name, mqttClient, serialPort):
    threading.Thread.__init__(self)
    self.clientId = clientId
    self.name = name
    self.running = True
    self.receivedMessages = []
    self.mqtt = mqttClient
    self.ser = serialPort
    self.mqtt.on_message = self.on_message
    self.mqtt.on_publish = self.on_publish
    self.mqtt.on_connect = self.on_mqtt_connect
    self.mqtt_reconnect = 0
  
  def run(self):
    print("Starting " + self.name)
    
    print("Starting MQTT client")
    self.mqtt.loop_start()
    self.mqtt.subscribe("cmd/"+self.clientId)
    
    print("Reading serial port")
    ret=self.ser.read_until()
    while self.running:
      if self.mqtt_reconnect > 0:
        print("Trying to reconnect...")
        self.mqtt.reconnect()
      else:
        if ret != b'':
          self.process(ret[:3].decode('ASCII'),ret[3:-4].decode('ASCII')) # get command and data - remove checksum and CRLF from end
      ret=self.ser.read_until()
  
  def sendCommand(self, arr):
    print("Sending arr=",arr)
    self.ser.write(arr)     # write a string  
  
  def c609(self, cmd, data):
    #print("Zone open=",data)
    self.publish("stat/"+self.clientId+"/zones/"+data,"open")
  
  def c610(self, cmd, data):
    #print("Zone restored=",data)
    self.publish("stat/"+self.clientId+"/zones/"+data,"closed")
  
  def c650(self, cmd, data):
    #print("Partition ready=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"open-ready")
  
  def c651(self, cmd, data):
    #print("Partition not ready=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"open-not ready")
  
  def c652(self, cmd, data):
    #print("Partition armed=",data)
    mode = {
      '000' : 'away',
      '001' : 'stay',
      '002' : 'away-no delay',
      '003' : 'stay-no delay',
      '004' : 'night'
    }.get(data[1:3], 'unknown')
    self.publish("stat/"+self.clientId+"/partitions/"+data[0],"armed "+mode)
    self.publish("stat/"+self.clientId+"/partitions/"+data+"/armed","on")
    self.publish("stat/"+self.clientId+"/partitions/"+data+"/armedOn",datetime.datetime.now().isoformat(timespec="seconds"))
  
  def c654(self, cmd, data):
    #print("Partition alarm=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"ALARM")
  
  def c655(self, cmd, data):
    #print("Partition disarmed=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"disarmed")
    self.publish("stat/"+self.clientId+"/partitions/"+data+"/armed","off")
    self.publish("stat/"+self.clientId+"/partitions/"+data+"/armedOn",datetime.datetime.now().isoformat(timespec="seconds"))
  
  def c656(self, cmd, data):
    #print("Partition exit delay=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"exit-delay")
  
  def c657(self, cmd, data):
    #print("Partition entry delay=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"entry-delay")
  
  def c672(self, cmd, data):
    #print("Partition failed to arm=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"failed to arm")
  
  def c700(self, cmd, data):
    #print("User closing=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data[0],"closing")
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedBy",data[1:4])
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedOn",datetime.datetime.now().isoformat(timespec="seconds"))
  
  def c750(self, cmd, data):
    #print("User opening=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data[0],"opening")
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedBy",data[1:4])
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedOn",datetime.datetime.now().isoformat(timespec="seconds"))
  
  def c901(self, cmd, data):
    #print("Alive=",data)
    self.publish("stat/"+self.clientId+"/alive",datetime.datetime.now().isoformat(timespec="seconds"))
  
  def c903(self, cmd, data):
    #print("LED status=",data)
    led = {
      '1' : 'ready',
      '2' : 'armed',
      '3' : 'memory',
      '4' : 'bypass',
      '5' : 'trouble',
      '6' : 'program',
      '7' : 'fire',
      '8' : 'backlight',
      '9' : 'ac'
    }.get(data[0],'unknown')

    s = 'off'
    if data[1] == '1': s='on'

    self.publish("stat/"+self.clientId+"/leds/"+led,s)
  
  # do nothing
  def donothing(self, cmd, data):
    #print("Do nothing cmd=",cmd,"data=",data)
    time.sleep(0.1)
  
  def unknown(self,cmd,data):
    print("Unknown cmd=",cmd," data=",data)
  
  def process(self, cmd, data):
    f = {
        '609': self.c609,  # zone open
        '610': self.c610,  # zone restored
        '650': self.c650,  # partition ready
        '651': self.c651,  # partition not ready
        '652': self.c652,  # partition armed+mode
        '654': self.c654,  # partition ALARM
        '655': self.c655,  # partition disarmed
        '656': self.c656,  # partition exit delay
        '657': self.c657,  # partition entry delay
        '672': self.c672,  # partition failed to arm
        '700': self.c700,  # user closing
        '750': self.c750,  # user opening
        '901': self.c901,  # display changed
        '903': self.c903,  # LED status
        '904': self.donothing,  # beep status
        '905': self.donothing,  # tone status
        '906': self.donothing   # buzzer status
    }.get(cmd, self.unknown)
    f(cmd, data)
  
  # display all incoming messages
  def on_message(self, userdata, message):
    print("Received operation ", str(message.payload))
  
  def on_publish(self, userdata, mid):
    self.receivedMessages.append(mid)
  
  def on_mqtt_connect(self, client, userdata, flags, rc):
    self.mqtt_connected = rc
    self.mqtt_reconnect = 0
    if rc != 0:
      print("Connection returned result: ",rc)
      self.mqtt_reconnect += 1
      if self.mqtt_reconnect > 12: self.mqtt_reconnect = 12
      self.mqtt_reconnect_delay = 2**self.mqtt_reconnect
    else:
      print("Connected to MQTT broker.")
  
  def on_mqtt_disconnect(self, client, userdata, rc):
    self.mqtt_reconnect = 1
    if rc != 0:
      print("Unexpected disconnection.")
      self.mqtt_reconnect = True
      self.mqtt_reconnect_delay = 10
  
  # publish a message
  def publish(self, topic, message, waitForAck = False):
    mid = self.mqtt.publish(topic, message, 2)[1]
    if (waitForAck):
        while mid not in self.receivedMessages:
            time.sleep(0.25)    


#-------------------------------------------------------

print("Opening serial port port=", serialPort)
ser = serial.Serial(serialPort,timeout=1)  # open serial port
print("Opened",ser.name)   # check which port was really used

# connect the client to Cumulocity IoT and register a device
print("Creating MQTT client for",serverUrl)
mqtt = mqtt.Client(clientId)
mqtt.username_pw_set(username, password)
mqtt.connect_async(serverUrl)

print("Creating DSC IT-100 device as",clientId)
dsc = DSCIT100(clientId, deviceName, mqtt, ser)
dsc.start()

time.sleep(30)
while True:
  print("DSC IT-100 Alive")
  time.sleep(3600)

