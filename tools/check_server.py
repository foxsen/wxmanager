#!/usr/bin/env python
# coding=utf-8

"""
script run by cron daemon to check the status of wxlogger, output to stdout
"""

import os
import subprocess
import time

p = subprocess.Popen(['systemctl', 'status', 'wxlogger'],stdout=subprocess.PIPE)
p.wait()
output = ''
for line in p.stdout.readlines():
    output += line

#print output

if (output.find('active (running)') >= 0):
    if (os.path.exists('/var/www/html/wxlogger/saved/logging')):
       print ('等待登录中，请用微信扫描下列二维码：<br/>'
               '<image src="/wxlogger/saved/qrcodes/qrcode.jpg?%s"'
               ' alt="登录二维码"/>' % time.time())
    elif(os.path.exists('/var/www/html/wxlogger/saved/initing')): 
       print  '  正在初始化。。。'
    else:
    	print '  运行中。。。'
else:
    if (os.path.exists('/var/www/html/wxlogger/autorestart')):
        retcode = subprocess.call(['systemctl', 'start', 'wxlogger'])
        if (retcode == 0):
            print '  重启中。。。'
        else:
            print '尝试重启服务失败，已停止。'
    else:
        print '  已停止'

