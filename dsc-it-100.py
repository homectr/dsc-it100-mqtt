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
deviceName  = "DSC IT 100"
serialPort  = "/dev/ttyUSB0"

class DSCIT100(threading.Thread):
  def __init__(self, clientId, name):
    threading.Thread.__init__(self)
    self.clientId = clientId
    self.name = name
    self.running = True
    self.receivedMessages = []
  
  def run(self, serialPort, mqttUrl, mqttUser, mqttPwd):
    print("Starting " + self.name)
    
    print("Opening serial port port="+serialPort)
    self.ser = serial.Serial(serialPort,timeout=1)  # open serial port
    print(self.ser.name)         # check which port was really used
    
    print("Connecting to MQTT url="+mqttUrl)
    self.mqtt = mqtt.Client(clientId)
    self.mqtt.username_pw_set(mqttUser, mqttPwd)
    self.mqtt.on_message = self.on_message
    self.mqtt.on_publish = self.on_publish
    self.mqtt.connect(mqttUrl)
    self.mqtt.loop_start()
    self.mqtt.subscribe("cmd/"+self.clientId)
    
    print("Reading serial port")
    ret=self.ser.read_until()
    while self.running:
      if ret != b'':
        self.process(ret[:3].decode('ASCII'),ret[3:-4].decode('ASCII')) # get command and data - remove checksum and CRLF from end
      ret=self.ser.read_until()
  
  def sendCommand(self, arr):
    print("Sending arr=",arr)
    self.ser.write(arr)     # write a string  
  
  def c609(self, cmd, data):
    print("Zone open=",data)
    self.publish("stat/"+self.clientId+"/zones/"+data,"open")
  
  def c610(self, cmd, data):
    print("Zone restored=",data)
    self.publish("stat/"+self.clientId+"/zones/"+data,"closed")
  
  def c700(self, cmd, data):
    print("User closing=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data[0],"closed")
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedBy",data[1:4])
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedOn",datetime.datetime.now().isoformat(timespec="seconds"))
  
  def c750(self, cmd, data):
    print("User opening=",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data[0],"open")
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedBy",data[1:4])
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedOn",datetime.datetime.now().isoformat(timespec="seconds"))
  
  def c901(self, cmd, data):
    print("Alive=",data)
    self.publish("stat/"+self.clientId+"/alive",datetime.datetime.now().isoformat(timespec="seconds"))
  
  def unknown(self,cmd,data):
    print("Unknown cmd=",cmd," data=",data)
  
  def process(self, cmd, data):
    f = {
        '609': self.c609,  # zone open
        '610': self.c610,  # zone restored
        '700': self.c700,  # user closing
        '750': self.c750,  # user opening
        '901': self.c901   # display changed
    }.get(cmd, self.unknown)
    f(cmd, data)
  
  # display all incoming messages
  def on_message(self, userdata, message):
    print("Received operation ", str(message.payload))
  
  def on_publish(self, userdata, mid):
    self.receivedMessages.append(mid)
  
  # publish a message
  def publish(self, topic, message, waitForAck = False):
    mid = self.mqtt.publish(topic, message, 2)[1]
    if (waitForAck):
        while mid not in self.receivedMessages:
            time.sleep(0.25)    

# connect the client to Cumulocity IoT and register a device
print("Creating MQTT client"+serialPort)

dsc = DSCIT100(clientId, deviceName)
dsc.run(serialPort, serverUrl, username, password)
