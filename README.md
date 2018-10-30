# graylog_alert
1.安装相应模块

  pip install -r requirements.txt

2. 添加微信告警用户

   打开graylog_alert.conf


   [项目名称定义]
   # wechat_user eg:  xxx,xxx,xxx
   wechat_user=xxxx,xxxx,xxxx

3. 启动脚本
   sh restart.sh 或者 nohup python graylog_http_alert.py &
