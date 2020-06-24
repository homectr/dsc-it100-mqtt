# dsc-it100-mqtt
DSC IT-100 MQTT client 

# Installation
1. copy script to any directory, e.g. user home
1. prepare empty log file\
   `sudo touch /var/log/dsc-it100.log`\
   `sudo chown openhabian /var/log/dsc-it100.log`
1. copy `dsc-it100.service` to `/lib/systemd/system`
1. modify service file as needed
1. make systemctl daemon aware of new service, run\
   `sudo systemctl daemon-reload`
1. enable and start service\
    `sudo systemctl enable dsc-it100.service`\
    `sudo systemctl start dsc-it100.service`
1. create empty logrotate configuration in /etc/logrotate.d/dsc-it100
1. copy-paste following configuration\
    ```/var/log/dsc-it100.log {
      size 5M
      rotate 3
      missingok
      dateext
      copytruncate
      compress
      delaycompress
    }```
 1. restart logrotate service

# Usage
1. check service status
   `sudo systemctl status dsc-it100`
1. restart service
   `sudo systemctl restart dsc-it100`
