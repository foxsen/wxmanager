#!/usr/bin/env python
# coding: utf-8
import qrcode
import requests
import xml.dom.minidom
import json
import time
import re
import sys
import os
import random
import multiprocessing
import platform
import logging
from collections import defaultdict
from urlparse import urlparse
from lxml import html
import getopt

import MySQLdb

# for media upload
import mimetypes
from requests_toolbelt.multipart.encoder import MultipartEncoder


def catchKeyboardInterrupt(fn):
    def wrapper(*args):
        try:
            return fn(*args)
        except KeyboardInterrupt:
            logging.info('[*] 强制退出程序')
    return wrapper


def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv


def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv


class SafeSession(requests.Session):

    def request(self, method, url, params=None, data=None, headers=None,
                cookies=None, files=None, auth=None, timeout=60,
                allow_redirects=True, proxies=None, hooks=None, stream=None,
                verify=None, cert=None, json=None):
        logging.debug(url)
        for i in range(3):
            try:
                return super(SafeSession, self).request(method, url, params,
                                                        data, headers, cookies,
                                                        files, auth, timeout,
                                                        allow_redirects, 
                                                        proxies, hooks, stream,
                                                        verify, cert, json)
            except Exception as e:
                logging.info(e, exc_info = 1)
                continue
        return None


class WebWeixin(object):

    def __str__(self):
        description = \
            "=========================\n" + \
            "[#] Web Weixin\n" + \
            "[#] Debug Mode: " + str(self.DEBUG) + "\n" + \
            "[#] Uuid: " + self.uuid + "\n" + \
            "[#] Uin: " + str(self.uin) + "\n" + \
            "[#] Sid: " + self.sid + "\n" + \
            "[#] Skey: " + self.skey + "\n" + \
            "[#] DeviceId: " + self.deviceId + "\n" + \
            "[#] PassTicket: " + self.pass_ticket + "\n" + \
            "========================="
        return description

    def __init__(self):
        self.DEBUG = False
        self.uuid = ''
        self.base_uri = ''
        self.redirect_uri = ''
        self.uin = ''
        self.sid = ''
        self.skey = ''
        self.pass_ticket = ''
        self.deviceId = 'e' + repr(random.random())[2:17]
        self.BaseRequest = {}
        self.synckey = ''
        self.SyncKey = []
        self.User = []
        self.MemberList = []
        self.ContactList = []  # 好友
        self.GroupList = []  # 群
        self.GroupMemeberList = []  # 群友
        self.PublicUsersList = []  # 公众号／服务号
        self.SpecialUsersList = []  # 特殊账号
        self.autoReplyMode = False
        self.syncHost = ''
        self.user_agent = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3)' 
                           'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/'
                           '48.0.2564.109 Safari/537.36')
        self.interactive = False
        self.autoOpen = False
        ''' link_prefix point to the static file url of your web site.
        While saveFolder is the physical directory where we will store images/videos/audios from wechat. You must map /static of the web server to savedFolder for the generated web links to work.
        You can use command line options to set these
        '''
        self.link_prefix = '/static'
        self.saveFolder = os.path.join('/var/www/html/wxlogger', 'saved')
        self.saveSubFolders = {'webwxgeticon': 'icons', 'webwxgetheadimg':
                               'headimgs', 'webwxgetmsgimg': 'msgimgs',
                               'webwxgetvideo': 'videos', 'webwxgetvoice':
                               'voices', '_showQRCodeImg': 'qrcodes',
                               'status':'status'}
        self.appid = 'wx782c26e4c19acffb'
        self.lang = 'zh_CN'
        self.lastCheckTs = time.time()
        self.memberCount = 0
        self.SpecialUsers = ['newsapp', 'fmessage', 'filehelper', 'weibo',
                             'qqmail', 'fmessage', 'tmessage', 'qmessage',
                             'qqsync', 'floatbottle', 'lbsapp', 'shakeapp',
                             'medianote', 'qqfriend', 'readerapp', 'blogapp',
                             'facebookapp', 'masssendapp', 'meishiapp',
                             'feedsapp', 'voip', 'blogappweixin', 'weixin',
                             'brandsessionholder', 'weixinreminder',
                             'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c',
                             'officialaccounts', 'notification_messages',
                             'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'wxitil',
                             'userexperience_alarm', 'notification_messages']
        self.TimeOut = 20  # 同步最短时间间隔（单位：秒）
        self.media_count = -1
        self.next_host = 0 # next sync host index
        self.daemon = True # daemon mode

        self.session = SafeSession()
        self.session.headers.update({'User-agent': self.user_agent})

        try:
            self.conn = MySQLdb.connect(
                host='localhost',
                user='wx',
                passwd='wxmanager',
                port=3306,
                charset='utf8')
            self.cur = self.conn.cursor()
            self.cur.execute(
                'create database if not exists python default character set utf8')
            self.conn.select_db('python')
            self.cur.execute('create table if not exists wxmanager_wx ('
                             'id int not null primary key auto_increment,'
                             'msgType int default 1,'
                             'msgId varchar(256) default "",'
                             'CreateTime int default 0,'
                             'msg varchar(4096) default "",'
                             'content varchar(2048) default "",'
                             'group_name varchar(256) default "",'
                             'user varchar(256) default "", '
                             'to_user varchar(256) default "")')
            self.conn.commit()
            logging.info('Database python initialized')

        except MySQLdb.Error as e:
            logging.error('Mysql error %d: %s' % (e.args[0], e.args[1]))

    def loadConfig(self, config):
        if config['DEBUG']:
            self.DEBUG = config['DEBUG']
        if config['autoReplyMode']:
            self.autoReplyMode = config['autoReplyMode']
        if config['user_agent']:
            self.user_agent = config['user_agent']
        if config['interactive']:
            self.interactive = config['interactive']
        if config['autoOpen']:
            self.autoOpen = config['autoOpen']

    def getUUID(self):
        url = 'https://login.weixin.qq.com/jslogin'
        params = {
            'appid': self.appid,
            'fun': 'new',
            'lang': self.lang,
            '_': int(time.time()),
        }
        data = self._post(url, params, False)
        regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
        pm = re.search(regx, data)
        if pm:
            code = pm.group(1)
            self.uuid = pm.group(2)
            return code == '200'
        return False

    def genQRCode(self):
        if sys.platform.startswith('win'):
            self._showQRCodeImg()
        else:
            if (self.daemon):
                self._saveQRCodeImg()
            else:
                self._str2qr('https://login.weixin.qq.com/l/' + self.uuid)

    def _showQRCodeImg(self):
        url = 'https://login.weixin.qq.com/qrcode/' + self.uuid
        params = {
            't': 'webwx',
            '_': int(time.time())
        }

        data = self._post(url, params, False)
        QRCODE_PATH = self._saveFile('qrcode.jpg', data, '_showQRCodeImg')
        os.startfile(QRCODE_PATH['fn'])

    def _saveQRCodeImg(self):
        url = 'https://login.weixin.qq.com/qrcode/' + self.uuid
        params = {
            't': 'webwx',
            '_': int(time.time())
        }

        data = self._post(url, params, False)
        QRCODE_PATH = self._saveFile('qrcode.jpg', data, '_showQRCodeImg')

    def waitForLogin(self, tip=1):
        time.sleep(tip)
        url = ('https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/'
               'login?tip=%s&uuid=%s&_=%s') % (tip, self.uuid, int(time.time()))
        data = self._get(url)
        pm = re.search(r'window.code=(\d+);', data)
        code = pm.group(1)

        if code == '201':
            return True
        elif code == '200':
            pm = re.search(r'window.redirect_uri="(\S+?)";', data)
            r_uri = pm.group(1) + '&fun=new'
            self.redirect_uri = r_uri
            self.base_uri = r_uri[:r_uri.rfind('/')]
            return True
        elif code == '408':
            logging.error('[登陆超时] \n')
        else:
            logging.error('[登陆异常] \n')
        return False

    def login(self):
        data = self._get(self.redirect_uri)
        doc = xml.dom.minidom.parseString(data)
        root = doc.documentElement

        for node in root.childNodes:
            if node.nodeName == 'skey':
                self.skey = node.childNodes[0].data
            elif node.nodeName == 'wxsid':
                self.sid = node.childNodes[0].data
            elif node.nodeName == 'wxuin':
                self.uin = node.childNodes[0].data
            elif node.nodeName == 'pass_ticket':
                self.pass_ticket = node.childNodes[0].data

        if '' in (self.skey, self.sid, self.uin, self.pass_ticket):
            return False

        self.BaseRequest = {
            'Uin': int(self.uin),
            'Sid': self.sid,
            'Skey': self.skey,
            'DeviceID': self.deviceId,
        }
        return True

    def webwxinit(self):
        url = self.base_uri + '/webwxinit?pass_ticket=%s&skey=%s&r=%s' % \
                   (self.pass_ticket, self.skey, int(time.time()))
        params = {
            'BaseRequest': self.BaseRequest
        }
        ret = True
        dic = self._post(url, params)
        try:
            self.SyncKey = dic['SyncKey']
            self.User = dic['User']
            # synckey for synccheck
            self.synckey = '|'.join(
                [str(keyVal['Key']) + '_' + str(keyVal['Val']) 
                 for keyVal in self.SyncKey['List']])
            ret = (dic['BaseResponse']['Ret'] == 0)
        except Exception as e:
            logging.info(e, exc_info = 1)
            ret = False
        return ret

    def webwxstatusnotify(self):
        url = self.base_uri + \
            '/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % (self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Code": 3,
            "FromUserName": self.User['UserName'],
            "ToUserName": self.User['UserName'],
            "ClientMsgId": int(time.time())
        }
        dic = self._post(url, params)
        try:
            ret = (dic['BaseResponse']['Ret'] == 0)
        except Exception as e:
            logging.info(e, exc_info = 1)
            ret = False
        return ret

    def webwxgetcontact(self):
        SpecialUsers = self.SpecialUsers
        url = self.base_uri + '/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' \
                % (self.pass_ticket, self.skey, int(time.time()))
        dic = self._post(url, {})

        ret = True 
        try:
            self.MemberCount = dic['MemberCount']
            self.MemberList = dic['MemberList']
            ContactList = self.MemberList[:]

            for i in xrange(len(ContactList) - 1, -1, -1):
                Contact = ContactList[i]
                if Contact['VerifyFlag'] & 8 != 0:  # 公众号/服务号
                    ContactList.remove(Contact)
                    self.PublicUsersList.append(Contact)
                elif Contact['UserName'] in SpecialUsers:  # 特殊账号
                    ContactList.remove(Contact)
                    self.SpecialUsersList.append(Contact)
                elif Contact['UserName'].find('@@') != -1:  # 群聊
                    ContactList.remove(Contact)
                    self.GroupList.append(Contact)
                elif Contact['UserName'] == self.User['UserName']:  # 自己
                    ContactList.remove(Contact)

            self.ContactList = ContactList
        except Exception as e:
            logging.info(e, exc_info = 1)
            ret = False

        return ret

    def webwxbatchgetcontact(self):
        url = self.base_uri + \
            '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' \
            % (int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Count": len(self.GroupList),
            "List": [{"UserName": g['UserName'], "EncryChatRoomId":""} \
                     for g in self.GroupList]
        }
        dic = self._post(url, params)

        ret = True
        try:
            # blabla ...
            ContactList = dic['ContactList']
            self.GroupList = ContactList

            for i in xrange(len(ContactList) - 1, -1, -1):
                Contact = ContactList[i]
                MemberList = Contact['MemberList']
                for member in MemberList:
                    self.GroupMemeberList.append(member)
        except Exception as e:
            logging.info(e, exc_info = 1)
            ret = False
        return ret

    def getNameById(self, id):
        url = self.base_uri + \
            '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' \
            % (int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Count": 1,
            "List": [{"UserName": id, "EncryChatRoomId": ""}]
        }
        dic = self._post(url, params)

        if 'ContactList' in dic:
            return dic['ContactList']
        else:
            return {}

    def getNextHost(self):
        SyncHost = [
            'webpush.weixin.qq.com',
            'webpush1.weixin.qq.com',
        ]
        host = SyncHost[self.next_host]
        self.next_host = self.next_host + 1
        if (self.next_host == len(SyncHost)):
            self.next_host = 0
        return host

    def testsynccheck(self):
        while (True):
            self.syncHost = self.getNextHost()
            [retcode, selector] = self.synccheck()
            if retcode == '0':
                return True
            else:
                if self.next_host == 2:
                    logging.info('No usable sync server!')
                    exit()
                else:
                    continue;

    def synccheck(self):
        params = {
            'r': int(time.time()),
            'sid': self.sid,
            'uin': self.uin,
            'skey': self.skey,
            'deviceid': self.deviceId,
            'synckey': self.synckey,
            '_': int(time.time()),
        }
        url = 'https://' + self.syncHost + \
            '/cgi-bin/mmwebwx-bin/synccheck'
        data = self._get(url, params=params)
        # try more sync hosts before giving up
        if (data == ''):
            self.syncHost = self.getNextHost()
            url = 'https://' + self.syncHost + \
            '/cgi-bin/mmwebwx-bin/synccheck'
            data = self._get(url, params=params)
        pm = re.search(
            r'window.synccheck={retcode:"(\d+)",selector:"(\d+)"}', data)
        if (pm):
            retcode = pm.group(1)
            selector = pm.group(2)
            return [retcode, selector]
        else:
            logging.info('get invalid data in synccheck!')
            return ['0', '0']

    def webwxsync(self):
        url = self.base_uri + \
            '/webwxsync?sid=%s&skey=%s&pass_ticket=%s' \
            % (self.sid, self.skey, self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            'SyncKey': self.SyncKey,
            'rr': ~int(time.time())
        }
        dic = self._post(url, params)

        try:
            if dic['BaseResponse']['Ret'] == 0:
                self.SyncKey = dic['SyncKey']
                self.synckey = '|'.join(
                    [str(keyVal['Key']) + '_' + str(keyVal['Val']) 
                     for keyVal in self.SyncKey['List']])
            return dic
        except Exception as e:
            logging.info(e, exc_info = 1)
            return None

    def webwxsendmsg(self, word, to='filehelper'):
        url = self.base_uri + \
            '/webwxsendmsg?pass_ticket=%s' % (self.pass_ticket)
        clientMsgId = str(int(time.time() * 1000)) + \
            str(random.random())[:5].replace('.', '')
        params = {
            'BaseRequest': self.BaseRequest,
            'Msg': {
                "Type": 1,
                "Content": self._transcoding(word),
                "FromUserName": self.User['UserName'],
                "ToUserName": to,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(params, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, headers=headers)
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def webwxuploadmedia(self, image_name):
        url = ('https://file2.wx.qq.com/cgi-bin/mmwebwx-bin/'
               'webwxuploadmedia?f=json')
        # 计数器
        self.media_count = self.media_count + 1
        # 文件名
        file_name = image_name
        # MIME格式
        # mime_type = application/pdf, image/jpeg, image/png, etc.
        mime_type = mimetypes.guess_type(image_name, strict=False)[0]
        # 微信识别的文档格式，微信服务器应该只支持两种类型的格式。pic和doc
        # pic格式，直接显示。doc格式则显示为文件。
        media_type = 'pic' if mime_type.split('/')[0] == 'image' else 'doc'
        # 上一次修改日期
        lastModifieDate = 'Thu Mar 17 2016 00:55:10 GMT+0800 (CST)'
        # 文件大小
        file_size = os.path.getsize(file_name)
        # PassTicket
        pass_ticket = self.pass_ticket
        # clientMediaId
        client_media_id = str(int(time.time() * 1000)) + \
            str(random.random())[:5].replace('.', '')
        # webwx_data_ticket
        webwx_data_ticket = ''
        for item in self.session.cookies:
            if item.name == 'webwx_data_ticket':
                webwx_data_ticket = item.value
                break
        if (webwx_data_ticket == ''):
            return "None Fuck Cookie"

        uploadmediarequest = json.dumps({
            "BaseRequest": self.BaseRequest,
            "ClientMediaId": client_media_id,
            "TotalLen": file_size,
            "StartPos": 0,
            "DataLen": file_size,
            "MediaType": 4
        }, ensure_ascii=False).encode('utf8')

        multipart_encoder = MultipartEncoder(
            fields={
                'id': 'WU_FILE_' + str(self.media_count),
                'name': file_name,
                'type': mime_type,
                'lastModifieDate': lastModifieDate,
                'size': str(file_size),
                'mediatype': media_type,
                'uploadmediarequest': uploadmediarequest,
                'webwx_data_ticket': webwx_data_ticket,
                'pass_ticket': pass_ticket,
                'filename': (file_name, open(file_name, 'rb'), mime_type.split('/')[1])
            },
            boundary='-----------------------------1575017231431605357584454111'
        )

        headers = {
            'Host': 'file2.wx.qq.com',
            'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10;'
                           'rv:42.0) Gecko/20100101 Firefox/42.0'),
            'Accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
                       '*/*;q=0.8'),
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://wx2.qq.com/',
            'Content-Type': multipart_encoder.content_type,
            'Origin': 'https://wx2.qq.com',
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }

        r = self._post(url, data=multipart_encoder, jsonfmt=True, 
                       headers=headers)
        response_json = r.json()
        if response_json['BaseResponse']['Ret'] == 0:
            return response_json
        return None

    def webwxsendmsgimg(self, user_id, media_id):
        url = ('https://wx2.qq.com/cgi-bin/mmwebwx-bin/'
               'webwxsendmsgimg?fun=async&f=json&pass_ticket=%s') \
                % self.pass_ticket
        clientMsgId = str(int(time.time() * 1000)) + \
            str(random.random())[:5].replace('.', '')
        data_json = {
            "BaseRequest": self.BaseRequest,
            "Msg": {
                "Type": 3,
                "MediaId": media_id,
                "FromUserName": self.User['UserName'],
                "ToUserName": user_id,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(data_json, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, jsonfmt=True, headers=headers)
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def webwxsendmsgemotion(self, user_id, media_id):
        url = ('https://wx2.qq.com/cgi-bin/mmwebwx-bin/'
               'webwxsendemoticon?fun=sys&f=json&pass_ticket=%s') \
                % self.pass_ticket
        clientMsgId = str(int(time.time() * 1000)) + \
            str(random.random())[:5].replace('.', '')
        data_json = {
            "BaseRequest": self.BaseRequest,
            "Msg": {
                "Type": 47,
                "EmojiFlag": 2,
                "MediaId": media_id,
                "FromUserName": self.User['UserName'],
                "ToUserName": user_id,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(data_json, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, jsonfmt=True, headers=headers)
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def _saveFile(self, filename, data, api=None):
        fn = filename
        link = filename
        if self.saveSubFolders[api]:
            dirName = os.path.join(self.saveFolder, self.saveSubFolders[api])
            if not os.path.exists(dirName):
                os.makedirs(dirName)
            fn = os.path.join(dirName, filename)
            link = os.path.join(
                self.link_prefix,
                self.saveSubFolders[api],
                filename)
            link = "<a href='" + link + "'>链接</a>"
            logging.debug('Saved file: %s' % fn)
            with open(fn, 'wb') as f:
                f.write(data)
                f.close()
        return {'link': link, 'fn': fn}

    def webwxgeticon(self, id):
        url = self.base_uri + \
            '/webwxgeticon?username=%s&skey=%s' % (id, self.skey)
        data = self._get(url)
        fn = 'img_' + id + '.jpg'
        return self._saveFile(fn, data, 'webwxgeticon')

    def webwxgetheadimg(self, id):
        url = self.base_uri + \
            '/webwxgetheadimg?username=%s&skey=%s' % (id, self.skey)
        data = self._get(url)
        fn = 'img_' + id + '.jpg'
        return self._saveFile(fn, data, 'webwxgetheadimg')

    def webwxgetmsgimg(self, msgid):
        url = self.base_uri + \
            '/webwxgetmsgimg?MsgID=%s&skey=%s' % (msgid, self.skey)
        data = self._get(url)
        fn = 'img_' + msgid + '.jpg'
        return self._saveFile(fn, data, 'webwxgetmsgimg')

    # Not work now for weixin haven't support this API
    def webwxgetvideo(self, msgid):
        url = self.base_uri + \
            '/webwxgetvideo?msgid=%s&skey=%s' % (msgid, self.skey)
        data = self._get(url, api='webwxgetvideo')
        fn = 'video_' + msgid + '.mp4'
        return self._saveFile(fn, data, 'webwxgetvideo')

    def webwxgetvoice(self, msgid):
        url = self.base_uri + \
            '/webwxgetvoice?msgid=%s&skey=%s' % (msgid, self.skey)
        data = self._get(url)
        fn = 'voice_' + msgid + '.mp3'
        return self._saveFile(fn, data, 'webwxgetvoice')

    def getGroupName(self, id):
        name = '未知群'
        for member in self.GroupList:
            if member['UserName'] == id:
                name = member['NickName']
        if name == '未知群':
            # 现有群里面查不到
            GroupList = self.getNameById(id)
            for group in GroupList:
                self.GroupList.append(group)
                if group['UserName'] == id:
                    name = group['NickName']
                    MemberList = group['MemberList']
                    for member in MemberList:
                        self.GroupMemeberList.append(member)
        return name

    def getUserRemarkName(self, id):
        name = '未知群' if id[:2] == '@@' else '陌生人'
        if id == self.User['UserName']:
            return self.User['NickName']  # 自己

        if id[:2] == '@@':
            # 群
            name = self.getGroupName(id)
        else:
            # 特殊账号
            for member in self.SpecialUsersList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']

            # 公众号或服务号
            for member in self.PublicUsersList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']

            # 直接联系人
            for member in self.ContactList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']
            # 群友
            for member in self.GroupMemeberList:
                if member['UserName'] == id:
                    name = member['DisplayName'] if member[
                        'DisplayName'] else member['NickName']

        if name == '未知群' or name == '陌生人':
            logging.debug(id)
        return name

    def getUSerID(self, name):
        for member in self.MemberList:
            if name == member['RemarkName'] or name == member['NickName']:
                return member['UserName']
        return None

    def _showMsg(self, message):

        srcName = None
        dstName = None
        groupName = None
        content = None

        msg = message
        logging.debug(msg)

        if msg['raw_msg']:
            srcName = self.getUserRemarkName(msg['raw_msg']['FromUserName'])
            dstName = self.getUserRemarkName(msg['raw_msg']['ToUserName'])
            content = msg['raw_msg']['Content'].replace(
                '&lt;', '<').replace('&gt;', '>')
            msgId = msg['raw_msg']['MsgId']
            msgType = msg['raw_msg']['MsgType']
            CreateTime = int(msg['raw_msg']['CreateTime'])

            if content.find(
                    'http://weixin.qq.com/cgi-bin/redirectforward?args=') != -1:
                # 地理位置消息
                data = self._get(content).decode('gbk').encode('utf-8')
                pos = self._searchContent('title', data, 'xml')
                tree = html.fromstring(self._get(content))
                url = tree.xpath('//html/body/div/img')[0].attrib['src']

                for item in urlparse(url).query.split('&'):
                    if item.split('=')[0] == 'center':
                        loc = item.split('=')[-1:]

                content = '%s 发送了一个 位置消息 - 我在 [%s](%s) @ %s]' \
                           % (srcName, pos, url, loc)

            if msg['raw_msg']['ToUserName'] == 'filehelper':
                # 文件传输助手
                dstName = '文件传输助手'

            if msg['raw_msg']['FromUserName'][:2] == '@@':
                # 接收到来自群的消息
                """
		        if content happens to contain more than one :<br/>
                the split will throw an exception
                if re.search(":<br/>", content, re.IGNORECASE):
                    [people, content] = content.split(':<br/>')
                """
                idx = content.find(':<br/>')
                if idx >= 0:
                    people = content[0:idx]
                    content = content[idx+6:]
                    groupName = srcName
                    srcName = self.getUserRemarkName(people)
                    dstName = '群'
                else:
                    groupName = srcName
                    srcName = 'SYSTEM'
            elif msg['raw_msg']['ToUserName'][:2] == '@@':
                # 自己发给群的消息
                groupName = dstName
                dstName = '群'

            # 收到了红包
            if content == '收到红包，请在手机上查看':
                msg['message'] = content

            # 指定了消息内容
            if 'message' in msg.keys():
                content = msg['message']

        if (srcName is None):
            user = ''
        else:
            user = srcName.strip()
        if (dstName is None):
            to_user = ''
        else:
            to_user = dstName.strip()
        if (groupName is None):
            groupName = ''
        else:
            groupName = groupName.strip()

        content = content.replace('<br/>', '\n')
        if groupName != '':
            logging.info(
                '%s |%s| %s -> %s: %s' %
                (msgId, groupName, srcName, dstName, content))
        else:
            logging.info('%s %s -> %s: %s' % (msgId, srcName, dstName, content))

        try:
            s = ('insert into wxmanager_wx set msgType=%s, msgId=%s,CreateTime=%s,'
                 'msg=%s, content=%s, group_name=%s, user=%s, to_user=%s')
            self.cur.execute(
                s,
                (msgType, msgId, CreateTime, json.dumps(msg), content, groupName,
                 user, to_user))
            self.conn.commit()
        except MySQLdb.Error as e:
            logging.error('Mysql error %d: %s' % (e.args[0], e.args[1]))

    def handleMsg(self, r):
        for msg in r['AddMsgList']:
            logging.debug('[*] 你有新的消息，请注意查收')

            if self.DEBUG:
                fn = 'msg' + str(int(random.random() * 1000)) + '.json'
                with open(fn, 'w') as f:
                    f.write(json.dumps(msg))
                logging.debug('[*] 该消息已储存到文件: %s' % (fn))

            msgType = int(msg['MsgType'])
            msgId = msg['MsgId']
            user = self.getUserRemarkName(msg['FromUserName'])
            content = msg['Content'].replace('&lt;', '<').replace('&gt;', '>')
            if msgType == 1:
                raw_msg = {'raw_msg': msg}
                self._showMsg(raw_msg)
                if self.autoReplyMode:
                    ans = self._xiaodoubi(content) + '\n[微信机器人自动回复]'
                    if self.webwxsendmsg(ans, msg['FromUserName']):
                        logging.info('自动回复: ' + ans)
                    else:
                        logging.info('自动回复失败')
            elif msgType == 3:
                image = self.webwxgetmsgimg(msgId)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发送了一张图片: %s' \
                                       % (user, image['link'])}
                self._showMsg(raw_msg)
                self._safe_open(image['fn'])
            elif msgType == 34:
                voice = self.webwxgetvoice(msgId)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发了一段语音: %s' \
                           % (user, voice['link'])}
                self._showMsg(raw_msg)
                self._safe_open(voice['fn'])
            elif msgType == 42:
                info = msg['RecommendInfo']
                logging.info('%s 发送了一张名片:' % user)
                logging.info('=========================')
                logging.info('= 昵称: %s' % info['NickName'])
                logging.info('= 微信号: %s' % info['Alias'])
                logging.info('= 地区: %s %s' % (info['Province'], info['City']))
                logging.info('= 性别: %s' % ['未知', '男', '女'][info['Sex']])
                logging.info('=========================')
                raw_msg = {'raw_msg': msg, 'message': '%s 发送了一张名片: %s' \
                           % (user, json.dumps(info))}
                self._showMsg(raw_msg)
            elif msgType == 47:
                url = self._searchContent('cdnurl', content)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发了一个动画表情，点击下面链接查看: \
                            <a href=%s>链接</a>' % (user, url)}
                self._showMsg(raw_msg)
                self._safe_open(url)
            elif msgType == 49:
                appMsgType = defaultdict(lambda: "")
                appMsgType.update({5: '链接', 3: '音乐', 7: '微博'})
                logging.info('%s 分享了一个%s:' %
                             (user, appMsgType[msg['AppMsgType']]))
                logging.info('=========================')
                logging.info('= 标题: %s' % msg['FileName'])
                logging.info(
                    '= 描述: %s' % self._searchContent( 'des', content, 'xml'))
                logging.info('= 链接: %s' % msg['Url'])
                logging.info( '= 来自: %s' 
                             % self._searchContent( 'appname', content, 'xml'))
                logging.info('=========================')
                card = {
                    'title': msg['FileName'],
                    'description': self._searchContent('des', content, 'xml'),
                    'url': msg['Url'],
                    'appname': self._searchContent('appname', content, 'xml')
                }
                raw_msg = {'raw_msg': msg, 
                           'message': ('%s 分享了一个%s:<br> 标题：%s<br>'
                                       '描述：%s<br> <a href="%s">链接</a><br>')
                                      % (user, appMsgType[msg['AppMsgType']],
                                         card['title'], card['description'],
                                         card['url'])}
                self._showMsg(raw_msg)
            elif msgType == 51:
                raw_msg = {'raw_msg': msg, 'message': '[*] 成功获取联系人信息'}
                # self._showMsg(raw_msg)
            elif msgType == 62:
                video = self.webwxgetvideo(msgId)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发了一段小视频: %s' \
                                      % (user, video['link'])}
                self._showMsg(raw_msg)
                self._safe_open(video['fn'])
            elif msgType == 10002:
                raw_msg = {'raw_msg': msg, 'message': '%s 撤回了一条消息' % user}
                self._showMsg(raw_msg)
            else:
                logging.debug( ('[*] 该消息类型为: %d，可能是表情，图片,'
                                '链接或红 包: %s')
                              % (msg['MsgType'], json.dumps(msg)))
                raw_msg = {
                    'raw_msg': msg, 
                    'message': ('[*] 该消息类型为: %d，可能是表情，图片,'
                                ' 链接或红包') % msg['MsgType']}
                # self._showMsg(raw_msg)

    def listenMsgMode(self):
        logging.info('[*] 进入消息监听模式 ... 成功')
        logging.debug('[*] 进入消息监听模式 ... 成功')
        self._run('[*] 进行同步线路测试 ... ', self.testsynccheck)
        playWeChat = 0
        redEnvelope = 0
        while True:
            self.lastCheckTs = time.time()
            [retcode, selector] = self.synccheck()
            logging.info('retcode: %s, selector: %s' % (retcode, selector))
            if retcode == '1100':
                logging.info('[*] 你在手机上登出了微信，再见')
                break
            if retcode == '1101':
                logging.info('[*] 你在其他地方登录了 WEB 版微信，再见')
                break
            elif retcode == '0':
                if selector == '2':
                    r = self.webwxsync()
                    if r is not None:
                        try:
                            self.handleMsg(r)
                        except Exception as e:
                            logging.info(e, exc_info = 1)
                elif selector == '6':
                    # TODO
                    redEnvelope += 1
                    logging.info('[*] 收到疑似红包消息 %d 次' % redEnvelope)
                    r = self.webwxsync()
                    if r is not None:
                        try:
                            self.handleMsg(r)
                        except Exception as e:
                            logging.info(e, exc_info = 1)
                elif selector == '7':
                    playWeChat += 1
                    logging.info('[*] 你在手机上玩微信被我发现了 %d 次' 
                                 % playWeChat)
                    r = self.webwxsync()
                elif selector == '0':
                    time.sleep(1)
                else:
                    r = self.webwxsync()

            if (time.time() - self.lastCheckTs) <= 20:
                time.sleep(time.time() - self.lastCheckTs)

    def sendMsg(self, name, word, isfile=False):
        id = self.getUSerID(name)
        if id:
            if isfile:
                with open(word, 'r') as f:
                    for line in f.readlines():
                        line = line.replace('\n', '')
                        logging.info('-> ' + name + ': ' + line)
                        if self.webwxsendmsg(line, id):
                            logging.info(' [成功]')
                        else:
                            logging.info(' [失败]')
                        time.sleep(1)
            else:
                if self.webwxsendmsg(word, id):
                    logging.info('[*] 消息发送成功')
                else:
                    logging.info('[*] 消息发送失败')
        else:
            logging.info('[*] 此用户不存在')

    def sendMsgToAll(self, word):
        for contact in self.ContactList:
            name = contact['RemarkName'] if contact[
                'RemarkName'] else contact['NickName']
            id = contact['UserName']
            logging.info('-> ' + name + ': ' + word)
            if self.webwxsendmsg(word, id):
                logging.info(' [成功]')
            else:
                logging.info(' [失败]')
            time.sleep(1)

    def sendImg(self, name, file_name):
        response = self.webwxuploadmedia(file_name)
        media_id = ""
        if response is not None:
            media_id = response['MediaId']
        user_id = self.getUSerID(name)
        response = self.webwxsendmsgimg(user_id, media_id)

    def sendEmotion(self, name, file_name):
        response = self.webwxuploadmedia(file_name)
        media_id = ""
        if response is not None:
            media_id = response['MediaId']
        user_id = self.getUSerID(name)
        response = self.webwxsendmsgemotion(user_id, media_id)

    def checkFlag(self, flag):
        status_flag = os.path.join(self.saveFolder, 
                                   self.saveSubFolders['status'],
                                   flag)
        return os.path.exists(status_flag)

    def setFlag(self, flag):
        status_flag = os.path.join(self.saveFolder, 
                                   self.saveSubFolders['status'],
                                   flag)
        if not os.path.exists(status_flag):
            os.mknod(status_flag)

    def clearFlag(self, flag):
        status_flag = os.path.join(self.saveFolder, 
                                   self.saveSubFolders['status'],
                                   flag)
        if os.path.exists(status_flag):
            os.remove(status_flag)

    @catchKeyboardInterrupt
    def start(self):
        self.setFlag('logging')
        logging.debug('[*] 微信网页版 ... 开动')
        while True:
            self._run('[*] 正在获取 uuid ... ', self.getUUID)
            logging.debug('[*] 微信网页版 ... 开动')
            self.genQRCode()
            logging.info('[*] 请使用微信扫描二维码以登录 ... ')
            if not self.waitForLogin():
                continue
                logging.info('[*] 请在手机上点击确认以登录 ... ')
            if not self.waitForLogin(0):
                continue
            break
        self.clearFlag('logging')
        self.setFlag('initing')

        self._run('[*] 正在登录 ... ', self.login)
        self._run('[*] 微信初始化 ... ', self.webwxinit)
        self._run('[*] 开启状态通知 ... ', self.webwxstatusnotify)
        self._run('[*] 获取联系人 ... ', self.webwxgetcontact)
        logging.info('[*] 应有 %s 个联系人，读取到联系人 %d 个' %
                     (self.MemberCount, len(self.MemberList)))
        logging.info( ('[*] 共有 %d 个群 | %d 个直接联系人 | %d 个特殊账号 '
                       '｜ %d 公众号或服务号') 
                     % (len(self.GroupList), len(self.ContactList), 
                        len(self.SpecialUsersList), 
                        len(self.PublicUsersList)))
        self._run('[*] 获取群 ... ', self.webwxbatchgetcontact)
        logging.debug('[*] 微信网页版 ... 开动')

        self.clearFlag('initing')

        if self.interactive and raw_input(
            '[*] 是否开启自动回复模式(y/n): ') == 'y':
            self.autoReplyMode = True
            logging.info('[*] 自动回复模式 ... 开启')
        else:
            logging.info('[*] 自动回复模式 ... 关闭')

        listenProcess = multiprocessing.Process(target=self.listenMsgMode)
        listenProcess.start()

        while True:
            text = raw_input('')
            if text == 'quit':
                listenProcess.terminate()
                logging.info('[*] 退出微信')
                exit()
            elif text[:2] == '->':
                [name, word] = text[2:].split(':')
                if name == 'all':
                    self.sendMsgToAll(word)
                else:
                    self.sendMsg(name, word)
            elif text[:3] == 'm->':
                [name, file] = text[3:].split(':')
                self.sendMsg(name, file, True)
            elif text[:3] == 'f->':
                print '发送文件'
                logging.info('发送文件')
            elif text[:3] == 'i->':
                print '发送图片'
                [name, file_name] = text[3:].split(':')
                self.sendImg(name, file_name)
                logging.debug('发送图片')
            elif text[:3] == 'e->':
                print '发送表情'
                [name, file_name] = text[3:].split(':')
                self.sendEmotion(name, file_name)
                logging.debug('发送表情')

    def _safe_open(self, path):
        if self.autoOpen:
            if platform.system() == "Linux":
                os.system("xdg-open %s &" % path)
            else:
                os.system('open %s &' % path)

    def _run(self, str, func, *args):
        if func(*args):
            logging.info('%s... 成功' % (str))
        else:
            logging.info('%s... 失败' % (str))
            logging.info('[*] 退出程序')
            exit()

    def _echo(self, str):
        sys.stdout.write(str)
        sys.stdout.flush()

    def _printQR(self, mat):
        for i in mat:
            BLACK = '\033[40m  \033[0m'
            WHITE = '\033[47m  \033[0m'
            print ''.join([BLACK if j else WHITE for j in i])

    def _str2qr(self, str):
        qr = qrcode.QRCode()
        qr.border = 1
        qr.add_data(str)
        mat = qr.get_matrix()
        self._printQR(mat)  # qr.print_tty() or qr.print_ascii()

    def _transcoding(self, data):
        if not data:
            return data
        result = None
        if isinstance(data, unicode):
            result = data
        elif isinstance(data, str):
            result = data.decode('utf-8')
        return result

    def _get(self, url, api=None, params=None):
        headers = {'Referer': 'https://wx.qq.com'}
        if api == 'webwxgetvoice':
            headers['Range'] = 'bytes=0-'
        if api == 'webwxgetvideo':
            headers['Range'] = 'bytes=0-'
        r = self.session.get(url=url, params=params, headers=headers)
        if (r is not None):
            r.encoding = 'utf-8'
            data = r.content
        else:
            data = '' 
        return data

    def _post(self, url, params, jsonfmt=True, headers=None):
        if jsonfmt:
            data = json.dumps(params)
            if (headers == None):
                headers = {'ContentType':'application/json; charset=UTF-8'}
        else:
            data = params
        r = self.session.post(url=url, data=data, headers=headers)
        if (r is not None):
            r.encoding = 'utf-8'
            if jsonfmt:
                return json.loads(r.text, object_hook=_decode_dict)
            return r.content
        else:
            if jsonfmt:
                return {}
            else:
                return ''

    def _xiaodoubi(self, word):
        url = 'http://www.xiaodoubi.com/bot/chat.php'
        try:
            r = self._post(url, data={'chat': word}, jsonfmt=False)
            return r.content
        except:
            return "让我一个人静静 T_T..."

    def _simsimi(self, word):
        key = ''
        url = ('http://sandbox.api.simsimi.com/request.p?'
               'key=%s&lc=ch&ft=0.0&text=%s') \
                % ( key, word)
        r = self._get(url)
        ans = r.json()
        if ans['result'] == '100':
            return ans['response']
        else:
            return '你在说什么，风太大听不清列'

    def _searchContent(self, key, content, fmat='attr'):
        if fmat == 'attr':
            pm = re.search(key + '\s?=\s?"([^"<]+)"', content)
            if pm:
                return pm.group(1)
        elif fmat == 'xml':
            pm = re.search('<{0}>([^<]+)</{0}>'.format(key), content)
            if not pm:
                pm = re.search(
                  '<{0}><\!\[CDATA\[(.*?)\]\]></{0}>'.format(key), content)
            if pm:
                return pm.group(1)
        return '未知'


class UnicodeStreamFilter:

    def __init__(self, target):
        self.target = target
        self.encoding = 'utf-8'
        self.errors = 'replace'
        self.encode_to = self.target.encoding

    def write(self, s):
        if isinstance(s, str):
            s = s.decode('utf-8')
        s = s.encode(self.encode_to, self.errors).decode(self.encode_to)
        self.target.write(s)

    def flush(self):
        self.target.flush()

if sys.stdout.encoding == 'cp936':
    sys.stdout = UnicodeStreamFilter(sys.stdout)

def Usage():
    print 'wxlogger.py usage:'
    print '-h, --help: print help message'
    print '-f, --foreground: run in foreground, ie. none daemon mode'
    print '-l url, --link_prefix=<url>: set link_prefix for generated links'
    print '-s dir, --save_folder=<dir>: set directory to saved wechat files'
    print '-v, --version: print version'

def Version():
    print 'wxlogger.py 1.0.0'

if __name__ == '__main__':

    daemon = True
    link_prefix = '/static'
    save_folder = '/var/www/html/wxlogger/saved'
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hfl:s:v', ['help','version', 'link_prefix=', 'save_folder='])
    except getopt.GetoptError, err:
        print str(err)
        Usage()
        sys.exit(2)

    for o, a in opts:
        if o in ('-h', '--help'):
            Usage()
            sys.exit(1)
        elif o in ('-v','--version'):
            Version()
            sys.exit(1)
        elif o in ('-f', '--foreground'):
            daemon = False
        elif o in ('-l', '--link_prefix'):
            link_prefix = a
        elif o in ('-s', '--save_folder'):
            directory = a
        else:
            Usage()
            sys.exit(3)

    if not daemon:
        print 'running in none-daemon mode'
        logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',  
                    datefmt='%a, %d %b %Y %H:%M:%S')
        daemon = False
    else:
        print 'running in daemon mode'
        logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',  
                    datefmt='%a, %d %b %Y %H:%M:%S',  
                    filename='/var/www/html/wxlogger/saved/test.log',  
                    filemode='a')  
        daemon = True

    logger = logging.getLogger(__name__)

    # disable requests' log
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.ERROR)

    webwx = WebWeixin()
    webwx.daemon = daemon
    webwx.link_prefix = link_prefix
    webwx.saveFolder = save_folder
    webwx.start()
