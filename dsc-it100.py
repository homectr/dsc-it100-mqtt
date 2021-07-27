#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial, threading
import paho.mqtt.client as mqtt
import time
import logging
import sys, getopt, configparser
import signal

runScript = True

class Config:
    # client, user and device details
    def __init__(self, argv):
      self.serverUrl = "localhost"
      self.username = "<<username>>"
      self.password = "<<password>>"
      self.serialPort = ""

      self.devId = "dscit100"  # device id, also used as mqtt client id and mqtt base topic

      self.logfile = "./dsc-it100.log"
      self.logLevel = logging.INFO
      self.configFile = './dsc-it100.cfg'
      self.qos = 1

      self.parse_args(argv)

      if len(self.configFile) > 0:
        self.read_config(self.configFile)

    def help(self):
      print('Usage: '+sys.argv[0] +
        ' -c <configfile> -v <verbose level> -l <logfile>')
      print()
      print('  -c | --config: ini-style configuration file, default is '+self.configFile)
      print('  -v | --verbose: 1-fatal, 2-error, 3-warning, 4-info, 5-debug')
      print('  -l | --logfile: log file name,default is '+self.logfile)
      print()
      print('Example: '+sys.argv[0] +
        ' -c /etc/dsc-it100.cfg -v 2 -l /var/log/dsc-it100.log')

    def parse_args(self, argv):
      try:
        opts, args = getopt.getopt(
            argv, "hc:v:l:", ["config=", "verbose=", "logfile="])
      except getopt.GetoptError:
        print("Command line argument error")
        self.help()
        sys.exit(2)

      for opt, arg in opts:
        if opt == '-h':
          self.help()
          sys.exit()
        elif opt in ("-c", "--config"):
          self.configFile = arg
        elif opt in ("-v", "--verbose"):
          if arg == "1": self.logLevel = logging.FATAL
          if arg == "2": self.logLevel = logging.ERROR
          if arg == "3": self.logLevel = logging.WARNING
          if arg == "4": self.logLevel = logging.INFO
          if arg == "5": self.logLevel = logging.DEBUG
        elif opt in ("-l", "--logfile"):
          self.logfile = arg

    def read_config(self, cf):
      print('Using configuration file ', cf)
      config = configparser.ConfigParser()
      config.read(cf)

      try:
        seccfg = config['dsc-it100']
      except KeyError:
        print('Error: configuration file is not correct or missing')
        exit(1)

      self.serverUrl = seccfg.get('host', 'localhost')
      self.username = seccfg.get('username')
      self.password = seccfg.get('password')
      self.devId = seccfg.get('id', 'dscit100')
      self.qos = int(seccfg.get('qos', "1"))
      self.serialPort = seccfg.get('serialport')

class DSCIT100(threading.Thread):
  def __init__(self, clientId, mqttClient, serialPort):
    threading.Thread.__init__(self)
    self.clientId = clientId
    self.running = True
    self.receivedMessages = []
    self.mqtt = mqttClient
    self.ser = serialPort
    self.log = logging.getLogger("dsc")
    self.f = 0
    self.mqtt.on_message = self.on_message
    self.mqtt.on_publish = self.on_publish
    self.mqtt.on_connect = self.on_mqtt_connect
    self.mqtt_reconnect = 0

  def stop(self):
    self.log.info("Stopping DSC-IT100 id=%s",self.clientId)
    self.running = False
  
  def run(self):
    print("Starting " + self.name)
    self.log.info("*** DSC-IT100 Starting")
    self.log.info("Starting MQTT client")
    self.mqtt.loop_start()
    self.mqtt.subscribe("cmd/"+self.clientId)
    
    print("Starting processing loop")
    ret=self.ser.read_until()
    while self.running:
      if self.mqtt_reconnect > 0:
        self.log.warning("MQTT Reconnecting...")
        self.mqtt.reconnect()
      else:
        if ret != b'':
          self.log.debug(">="+ret[:-2].decode('ASCII'))
          self.process(ret[:3].decode('ASCII'),ret[3:-4].decode('ASCII')) # get command and data - remove checksum and CRLF from end
      ret=self.ser.read_until()
  
  def sendCommand(self, arr):
    self.log.info("DSC Sending arr=%s",arr)
    self.ser.write(arr)     # write a string  
  
  def c609(self, cmd, data):
    self.log.info("DSC Zone open=%s",data)
    self.publish("stat/"+self.clientId+"/zones/"+data,"open")
  
  def c610(self, cmd, data):
    self.log.info("DSC Zone restored=%s",data)
    self.publish("stat/"+self.clientId+"/zones/"+data,"closed")
  
  def c650(self, cmd, data):
    self.log.info("DSC Partition ready=%s",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"open-ready")
  
  def c651(self, cmd, data):
    self.log.info("DSC Partition not ready=%s",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"open-not ready")
  
  def c652(self, cmd, data):
    self.log.info("DSC Partition armed=%s",data)
    mode = {
      '000' : 'away',
      '001' : 'stay',
      '002' : 'away-no delay',
      '003' : 'stay-no delay',
      '004' : 'night'
    }.get(data[1:3], 'unknown')
    self.publish("stat/"+self.clientId+"/partitions/"+data[0],"armed "+mode)
    self.publish("stat/"+self.clientId+"/partitions/"+data+"/armed","on")
    self.publish("stat/"+self.clientId+"/partitions/"+data+"/armedOn",time.strftime("%Y-%m-%dT%H:%M:%S"))
  
  def c654(self, cmd, data):
    self.log.info("DSC Partition alarm=%s",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"ALARM")
  
  def c655(self, cmd, data):
    self.log.info("DSC Partition disarmed=%s",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"disarmed")
    self.publish("stat/"+self.clientId+"/partitions/"+data+"/armed","off")
    self.publish("stat/"+self.clientId+"/partitions/"+data+"/armedOn",time.strftime("%Y-%m-%dT%H:%M:%S"))
  
  def c656(self, cmd, data):
    self.log.info("DSC Partition exit delay=%s",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"exit-delay")
  
  def c657(self, cmd, data):
    self.log.info("DSC Partition entry delay=%s",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"entry-delay")
  
  def c672(self, cmd, data):
    self.log.info("DSC Partition failed to arm=%s",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data,"failed to arm")
  
  def c700(self, cmd, data):
    self.log.info("User closing=%s",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data[0],"closing")
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedBy",data[1:4])
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedOn",time.strftime("%Y-%m-%dT%H:%M:%S"))
  
  def c750(self, cmd, data):
    self.log.info("DSC User opening=%s",data)
    self.publish("stat/"+self.clientId+"/partitions/"+data[0],"opening")
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedBy",data[1:4])
    self.publish("stat/"+self.clientId+"/partitions/"+data[0]+"/changedOn",time.strftime("%Y-%m-%dT%H:%M:%S"))
  
  def c901(self, cmd, data):
    self.log.info("Alive=%s",data)
    self.publish("stat/"+self.clientId+"/alive",time.strftime("%Y-%m-%dT%H:%M:%S"))
  
  def c903(self, cmd, data):
    self.log.info("DSC LED status=%s",data)
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
    self.log.warning("DSC unknown cmd=%s data=%s", cmd,data)
  
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
    self.log.info("MQTT received msg=%s",message.payload)
  
  def on_publish(self, userdata, mid):
    self.receivedMessages.append(mid)
  
  def on_mqtt_connect(self, client, userdata, flags, rc):
    self.mqtt_connected = rc
    self.mqtt_reconnect = 0
    if rc != 0:
      self.log.error("MQTT connection returned result=%s",rc)
      self.mqtt_reconnect += 1
      if self.mqtt_reconnect > 12: self.mqtt_reconnect = 12
      self.mqtt_reconnect_delay = 2**self.mqtt_reconnect
    else:
      self.log.info("Connected to MQTT broker.")
  
  def on_mqtt_disconnect(self, client, userdata, rc):
    self.mqtt_reconnect = 1
    if rc != 0:
      self.log.error("MQTT unexpected disconnection.")
      self.mqtt_reconnect = True
      self.mqtt_reconnect_delay = 10
  
  # publish a message
  def publish(self, topic, message, waitForAck = False):
    mid = self.mqtt.publish(topic, message, 2)[1]
    if (waitForAck):
        while mid not in self.receivedMessages:
            time.sleep(0.25)

def stop_script_handler(msg, logger):
  logger.info(msg)
  global runScript
  runScript = False

#-------------------------------------------------------

# parse commandline aruments and read config file if specified
cfg = Config(sys.argv[1:])

# configure logging
logging.basicConfig(filename=cfg.logfile, level=cfg.logLevel, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# create logger
log = logging.getLogger('main')

# add console to logger output
log.addHandler(logging.StreamHandler())

if cfg.serialPort == "":
  log.fatal("Serial port not specified.")
  exit(1)

# handle gracefull end in case of service stop
signal.signal(signal.SIGTERM, lambda signo,
              frame: stop_script_handler("Signal SIGTERM received", log))

# handles gracefull end in case of closing a terminal window
signal.signal(signal.SIGHUP, lambda signo,
              frame: stop_script_handler("Signal SIGHUP received", log))

log.info("Opening serial port port=%s", cfg.serialPort)
ser = serial.Serial(cfg.serialPort,timeout=1)  # open serial port

# connect the client to Cumulocity IoT and register a device
log.info("Creating MQTT client for %s",cfg.serverUrl)
mqtt = mqtt.Client(cfg.devId)
mqtt.username_pw_set(cfg.username, cfg.password)
mqtt.connect_async(cfg.serverUrl)

log.info("Creating DSC IT-100 device as %s",cfg.devId)
dsc = DSCIT100(cfg.devId, mqtt, ser)
dsc.start()

try:
  while runScript:
    time.sleep(1)

except KeyboardInterrupt:
  log.info("Signal SIGINT received.")

# perform some cleanup
log.info("Stopping device id=%s", cfg.devId)
dsc.stop()
log.info('DSC-IT100 stopped.')
