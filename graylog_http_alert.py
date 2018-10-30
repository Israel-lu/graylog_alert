# -*- coding:utf-8 -*-
import requests
import json
import os, re
import datetime, time
import configparser
import sys
import platform

reload(sys)
sys.setdefaultencoding('utf-8')
'''
    v1版本实现告警及恢复, 添加不同项目告警分组, 支持告警分组正则
'''

alert_id = []


def utctolocal(utc_time):
    # param utc_time: %Y-%m-%dT%H:%M:%S.%fZ
    # return: 本地时间

    utc = utc_time
    utc_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    utc_st = datetime.datetime.strptime(utc, utc_format)
    now_stamp = time.time()
    local_time = datetime.datetime.fromtimestamp(now_stamp)
    utc_time = datetime.datetime.utcfromtimestamp(now_stamp)
    offset = local_time - utc_time
    local_st = utc_st + offset
    local_st.strftime("%Y-%m-%d %H:%M:%S")
    return local_st.strftime("%Y-%m-%d %H:%M:%S")


class WechatSendApi(object):

    # 微信告警

    def __init__(self):
        self.wechat_url = "https://qyapi.weixin.qq.com"   # 微信接口地址
        self.corp_id = ""                # corp_id
        self.corp_secret = "" # secret

    def get_token(self):
        res = requests.get("{}/cgi-bin/gettoken".format(self.wechat_url),
                           params={"corpid": self.corp_id, "corpsecret": self.corp_secret})
        res = json.loads(res.text)
        access_token = res["access_token"]
        return access_token

    def send_message(self, user, subject, content):
        send_url = "{}/cgi-bin/message/send?access_token={}".format(self.wechat_url, self.get_token())
        data = {
            "touser": user,
            "toparty": "@all",
            "msgtype": "text",
            "agentid": "1000003",
            "text": {
                "content": subject + '\n' + content
            },
            "safe": "0"
        }

        res = requests.post(send_url, data=json.dumps(data))


class GraylogRestApi(object):
    '''
        graylog api
    '''

    def __init__(self):
        cur_path = os.getcwd()
        self.config_file = "{}/graylog_alert.conf".format(cur_path)
        self.conf = configparser.ConfigParser()
        self.conf.read(self.config_file, encoding='utf-8')
        self.url = "http://10.1.1.120:9000"
        # self.url = "http://graylog.juqitech.com"
        self.session_obj = requests.session()
        self.session_obj.auth = ("1au6lqjaotj3dvouu8ro9vqfmaqsbe49qm61cj3n4ionh0nhs0mr", "token")

    def get_stream_info(self):
        '''

        :return: stream列表
        '''
        stream_info = []
        stream = self.conf.get("stream", "stream_name")
        stream_name = stream.strip('"')
        res = self.session_obj.get("{}/api/streams".format(self.url))
        result = json.loads(res.text)
        streams = result["streams"]
        for stream in streams:
            stream_title = stream["title"]
            stream_id = stream["id"]
            stream_des = stream["description"]
            if stream_title == stream_name:
                stream_dict = {"stream_name": stream_title, "stream_id": stream_id, "stream_des": stream_des}
                stream_info.append(stream_dict)
        return stream_info

    def get_alerts_conditions(self):
        '''

        :return: 所有告警条件
        '''
        try:
            res = self.session_obj.get("{}/api/alerts/conditions".format(self.url))
            result = json.loads(res.text)
            return result
        except Exception as error:
            pass

    def get_alert(self, types):
        '''

        :param types:  resolved（恢复告警列表） unresolved(实时告警列表)
        :return:
        '''
        alert_info_list = []
        try:
            alert_conditions_info = self.get_alerts_conditions()
            conditions_info = alert_conditions_info["conditions"]
            conditions_number = alert_conditions_info["total"]
            if types == "resolved":
                res = self.session_obj.get("{}/api/streams/alerts/paginated".format(self.url),
                                           params={"skip": 0,
                                                   "limit": conditions_number,
                                                   "state": "resolved"})
            elif types == "unresolved":
                res = self.session_obj.get("{}/api/streams/alerts/paginated".format(self.url),
                                           params={"skip": 0, "limit": conditions_number, "state": "unresolved"})
            result = json.loads(res.text)

            alert_info = result["alerts"]
            for alert in alert_info:
                for conditions in conditions_info:
                    conditions_id = conditions["id"]
                    if alert["condition_id"] == conditions_id:
                        conditions_title = conditions["title"]
                        alert["conditions_title"] = conditions_title
                        conditions_title = conditions_title.split("_")
                        conditions_title.pop(-1)
                        conditions_title = "_".join(conditions_title)
                        alert["project_name"] = conditions_title
                        alert_info_list.append(alert)
            return alert_info_list

        except Exception as error:
            return alert_info_list


class FileOperation(object):
    def __init__(self):
        os_type = platform.platform()
        if "Windows" in os_type:
            script_path = os.path.abspath(__file__).split("\\")
        elif "Linux" in os_type:
            script_path = os.path.abspath(__file__).split("/")
        script_path.pop(-1)
        script_path = "/".join(script_path)
        self.alert_id_file = "{}/graylog_alert_id.txt".format(script_path)
        self.config_file = "{}/graylog_alert.conf".format(script_path)
        self.conf = configparser.ConfigParser()
        self.conf.read(self.config_file, encoding='utf-8')

    def re_match(self, patter_value, value):
        patter = re.compile(r'{}'.format(patter_value))
        result = patter.findall(value)
        return result

    def file_operation(self, context=None, **kwargs):
        alert_id_file = self.alert_id_file

        if kwargs:
            # 追加alert_id
            with open(alert_id_file, "a+") as f:
                f.write("%s\n" % kwargs)

        if context:
            # 删除已告警的id
            with open(alert_id_file, "r") as f:
                context_list = f.readlines()
                with open(alert_id_file, 'w') as w:
                    for line in context_list:
                        if context == line.strip():
                            continue
                        w.write(line)

        # 读取alert_id
        with open(alert_id_file, "r") as f:
            return f.readlines()

    def send_wechat_alert(self):
        graylog_rest_api = GraylogRestApi()
        wechat = WechatSendApi()
        stream_alert_info = graylog_rest_api.get_alert("unresolved")
        stream_recovery_alert = graylog_rest_api.get_alert("resolved")
        if stream_alert_info:
            for alert in stream_alert_info:
                project_name = alert["project_name"]
                sects = [sect for sect in self.conf.sections() if self.re_match(sect, project_name)]
                if len(sects) == 1:
                    try:
                        user = self.conf.get(sects[0], "wechat_user")
                        user = "|".join(user.split(","))
                    except:
                        break
                    try:
                        condition_query = alert["condition_parameters"]["query"]
                    except:
                        condition_query = alert["condition_parameters"]["value"]
                    context = alert["description"]
                    alert_id = alert["id"]
                    triggered_utc_time = alert["triggered_at"]
                    resolved_utc_time = alert["resolved_at"]
                    alert["triggered_at"] = utctolocal(triggered_utc_time)
                    triggere_date = alert["triggered_at"]
                    try:
                        status = [alert for alert in self.file_operation() if
                                  eval(alert.strip())["alert_id"] == alert_id]
                    except:
                        status = []
                    if not status:
                        alerts = "项目名称:{}\n状态: PROBLEM\n告警ID: {}\n告警关键字: {}\n告警概览: {}\n告警时间: {}\n恢复时间: {}\n".format(
                            project_name,
                            alert_id,
                            condition_query,
                            context,
                            triggere_date,
                            resolved_utc_time
                        )
                        self.file_operation(status="NO", alert_id=alert_id)
                        wechat.send_message(user, "graylog", alerts)
                        print alerts

        if stream_recovery_alert:
            for alert in stream_recovery_alert:
                project_name = alert["project_name"]
                sects = [sect for sect in self.conf.sections() if self.re_match(sect, project_name)]
                if len(sects) == 1:
                    try:
                        user = self.conf.get(sects[0], "wechat_user")
                        user = "|".join(user.split(","))
                    except:
                        break
                    try:
                        condition_query = alert["condition_parameters"]["query"]
                    except:
                        condition_query = alert["condition_parameters"]["value"]
                    context = alert["description"]
                    alert_id = alert["id"]
                    triggered_utc_time = alert["triggered_at"]
                    resolved_utc_time = alert["resolved_at"]
                    alert["triggered_at"] = utctolocal(triggered_utc_time)
                    triggere_date = alert["triggered_at"]
                    try:
                        status = [alert_info for alert_info in self.file_operation() if
                                  eval(alert_info.strip())["alert_id"] == alert_id]

                    except:
                        status = []
                    if status:
                        status_str = status[0].strip()
                        status_dict = eval(status[0].strip())
                        if status_dict["status"] == "NO":
                            alert["resolved_at"] = utctolocal(resolved_utc_time)
                            recovery_date = alert["resolved_at"]
                            recovery = "项目名称: {}\n状态: OK\n告警ID: {}\n告警关键字: {}\n告警概览: {}\n告警时间: {}\n恢复时间: {}\n".format(
                                project_name, alert_id, condition_query, context,
                                triggere_date, recovery_date)
                            self.file_operation(status="OK", alert_id=alert_id)
                            self.file_operation(context=status_str)
                            wechat.send_message(user, "graylog", recovery)
                            print recovery

    def main(self):
        while True:
            self.send_wechat_alert()
            time.sleep(1)


if __name__ == '__main__':
    FileOperation().main()
