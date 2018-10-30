#!/bin/sh

ps aux | grep "graylog_http_alert.py" | grep -v grep | awk '{print $2}' | xargs kill -9

cd /opt/scripts/graylog_alerts && nohup python graylog_http_alert.py > /dev/null 2>&1 &