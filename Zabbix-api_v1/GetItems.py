#! /usr/bin/env python
# _*_ coding: utf-8 _*_

# @Desc   :调用zabbix api接口，获取监控数据，zabbix-版本为5.0以上


import requests
import json
import time
import re
import urllib3

urllib3.disable_warnings()

class Zabbix(object):
    def __init__(self, ApiUrl, User, Pwd):
        self.ApiUrl = ApiUrl
        self.User = User
        self.Pwd = Pwd
        self.__Headers = {
            'Content-Type': 'application/json-rpc',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Safari/537.36'
        }
        self.Message = {
            1001: {"errcode": "1001", "errmsg": "请求路径错误，请检查API接口路径是否正确."},
            1002: {"errcode": "1002", "errmsg": "Login name or password is incorrect."},
            1003: {"errcode": "1003", "errmsg": "未获取到监控主机，请检查server端是否监控有主机."},
            1004: {"errcode": "1004", "errmsg": "未知错误."},
        }


    def __Login(self):
        '''
        登陆zabbix，获取认证的秘钥
        Returns: 返回认证秘钥

        '''
        # 登陆zabbix,接口的请求数据
        LoginApiData = {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": {
                "user": self.User,
                "password": self.Pwd
            },
            "id": 1
        }
        # 向登陆接口发送post请求，获取result
        LoginRet = requests.post(url=self.ApiUrl, data=json.dumps(LoginApiData), headers=self.__Headers, verify=False)
        # 判断请求是否为200
        if LoginRet.status_code != 200:
            return 1001
        else:
            # 如果是200状态，则进行数据格式化
            try:
                LoginRet = LoginRet.json()
            except:
                return 1001
            # 如果result在返回数据中，那么表示请求成功，则获取认证key
            if 'result' in LoginRet:
                Result = LoginRet['result']
                return Result
            # 否则返回用户或密码错误
            else:
                return 1002


    def __GetMonitorHost(self):
        # 调用登陆函数，获取auth，并判断是否登陆成功
        Auth = self.__Login()
        if Auth == 1001:
            return 1001
        elif Auth == 1002:
            return 1002
        else:
            HostApiData = {
                "jsonrpc": "2.0",
                "method": "host.get",
                "params": {
                    "output": ["hostid", "host", "name"],
                    "groupids": "43",
                    "selectInterfaces": ["interfaces", "ip"],
                },
                "auth": Auth,
                "id": 1
            }
            # 向host.get接口发起请求，获取所有监控主机
            HostRet = requests.post(url=self.ApiUrl, data=json.dumps(HostApiData), headers=self.__Headers, verify=False).json()
            #print (HostRet)

            if 'result' in HostRet:
                if len(HostRet['result']) != 0:
                    # 循环处理每一条记录，进行结构化,最终将所有主机加入到all_host字典中
                    Allhost = {}
                    for host in HostRet['result']:
                        # host = {'hostid': '10331', 'host': '172.24.125.24', 'name': 'TBDS测试版172.24.125.24', 'interfaces': [{'ip': '172.24.125.24'}]}
                        # 进行结构化，提取需要的信息
                        HostInfo = {'host': host['host'], 'hostid': host['hostid'], 'ip': host['interfaces'][0]['ip'],
                                     'name': host['name']}
                        # host_info = {'host': '172.24.125.24', 'hostid': '10331', 'ip': '172.24.125.24', 'name': 'TBDS测试版172.24.125.24'}
                        # 加入到all_host中
                        Allhost[host['hostid']] = HostInfo
                    #print(Allhost)主机结构化列表
                    return {"Auth":Auth, "Allhost":Allhost}
                else:
                    return 1003
            else:
                return 1001


    def GetItemValue(self):
        '''
        # 调用item.get接口，获取监控项（监控项中带有每个监控项的最新监控数据） 接口说明文档：https://www.zabbix.com/documentation/4.0/zh/manual/api/reference/item/get
        Returns: 返回所有监控主机监控信息，
        '''
        # 获取所有的主机
        HostRet = self.__GetMonitorHost()
        

        # 判断HostRet是否有主机和认证key存在，这里如果是类型如果是字段，那边表示一定获取到的有主机信息，如果不是，则表示没有获取到值

        if type(HostRet) is dict:
            # 首先拿到认证文件和所有主机信息
            Auth, AllHost = HostRet['Auth'], HostRet['Allhost']
            # 定义一个新的allhost，存放所有主机新的信息
            NewAllHost = {}
            # 循环向每个主机发起请求，获取监控项的值
            #print (AllHost)
            for k in AllHost:
                ItemData = {
                    "jsonrpc": "2.0",
                    "method": "item.get",
                    "params": {
                        #"output": ["extend", "name", "key_", "lastvalue"],
                        "output": ["extend", "name", "key_", "itemid"],
                        "hostids": str(k),
                        "search": {
                            "key_":
                                [
                                    #"system.hostname",    # 主机名
                                    "system.uptime",      # 系统开机时长
                                    "system.cpu.util[,idle,avg1]",    # cpu使用率
                                    "system.cpu.load",    # cpu平均负载
                                    "vm.memory.size[total]",      # 内存总大小
                                    "vm.memory.size[free]", # 可用内存
                                    "vm.memory.size[cached]",
                                    "vm.memory.size[buffers]"

                                ]
                        },
                        "searchByAny": "true",
                        "sortfield": "name"
                    },
                    "auth": Auth,
                    "id": 1
                }
                # 向每一台主机发起请求，获取监控项
                Ret = requests.post(url=self.ApiUrl, data=json.dumps(ItemData), headers=self.__Headers, verify=False).json()
                #print(Ret)
                if 'result' in Ret:
                    # 判断每台主机是否有获取到监控项，如果不等于0表示获取到有监控项
                    if len(Ret['result']) != 0:
                        # 从所有主机信息中取出目前获取信息的这台主机信息存在host_info中
                        HostInfo = AllHost[k]
                        # 循环处理每一台主机的所有监控项
                        #print(HostInfo)
                        for historyid in Ret['result']:
                            #print(str(historyid.values()))
                            #print(historyid)
                            starttime = "2022-09-19 12:00:00" 
                            stoptime = "2022-09-23 12:00:00"
                            
                            timeArray = time.strptime(starttime, "%Y-%m-%d %H:%M:%S")
                            start = int(time.mktime(timeArray))
                            timeArray = time.strptime(stoptime, "%Y-%m-%d %H:%M:%S")
                            stop = int(time.mktime(timeArray)) 
                            HistoryApiData = {
                                "jsonrpc": "2.0",
                                "method": "trend.get",
                                "params": {
                                    "output": "extend",
                                    "itemids": historyid['itemid'],
                                    "history": 0,
                                    "time_from":start,
                                    "time_till":stop
                                },
                                "auth": Auth,
                                "id": 1
                            }
                            HistoryApiRet = requests.post(url=self.ApiUrl, data=json.dumps(HistoryApiData), headers=self.__Headers, verify=False).json()
                            if HistoryApiRet:
                                avg_valuelist = []
                                for i in HistoryApiRet['result']:
                                    avg_valuelist.append(int(float(i["value_avg"])))
                                avge = sum(avg_valuelist)/len(avg_valuelist)

                                HostInfo[historyid['name']] = avge
                                NewAllHost[HostInfo['hostid']] = HostInfo
                                #print (NewAllHost)
                else:
                    return {"errcode": "1001", "errmess": "Login name or password is incorrect."}
            return NewAllHost
            #print(NewAllHost)

        elif HostRet == 1001:
            return self.Message[1001]
        elif HostRet == 1002:
            return self.Message[1002]
        elif HostRet == 1003:
            return self.Message[1003]
        else:
            return self.Message[1004]
