#!/usr/bin/env python
# coding: utf-8

import cgi
import os
import time

import MySQLdb

import sys

reload(sys)
sys.setdefaultencoding('utf-8')

print "Content-type:text/html;charset=utf-8\r\n\r\n"

#print os.environ['QUERY_STRING']

form = cgi.FieldStorage()

user = form.getvalue('user')
to_user = form.getvalue('to_user')
start = form.getvalue('start')
end = form.getvalue('end')
contains = form.getvalue('contains')
group_name = form.getvalue('group_name')
#getvalue filter special characters like '+' and replace them with ' '
#we use regexp to match any possible character
if (group_name != None):
	group_name = group_name.replace(' ', '.')

condition = ""

if (user != None and user != ''): 
	condition = "where user = '" + user + "'";

if (to_user != None and to_user != ''): 
        if (condition != ""):
		condition = condition + " and ";
	else:
		condition = "where "
	condition = condition + "to_user = '" + to_user + "'";

if (start != None and start != ''): 
        timeArray = time.strptime(start, "%Y-%m-%d %H:%M")
	timeStamp = int(time.mktime(timeArray))
        if (condition != ""):
		condition = condition + " and ";
	else:
		condition = "where "
	condition = condition + "CreateTime >= " + str(timeStamp);

if (end != None and end != ''): 
        timeArray = time.strptime(start, "%Y-%m-%d %H:%M")
	timeStamp = int(time.mktime(timeArray))
        if (condition != ""):
		condition = condition + " and ";
	else:
		condition = "where "
	condition = condition + "CreateTime < " + str(timeStamp);

if (contains != None and contains !=''): 
        if (condition != ""):
		condition = condition + " and ";
	else:
		condition = "where "
	condition = condition + "content REGEXP '" + contains + "'";

if (group_name != None and group_name != ''): 
        if (condition != ""):
		condition = condition + " and ";
	else:
		condition = "where "
	condition = condition + "group_name REGEXP '" + group_name + "'";

#print condition
#print "<a href='http://localhost/'>home</a><br>"
print '<table align="center" border="0" width="100%" style="table-layout:fixed">'

try:
	conn = MySQLdb.connect(host='localhost',user='wx',passwd='welcome..',port=3306,charset='utf8')
	cur = conn.cursor()
	conn.select_db('python')

except MySQLdb.Error,e:
	print 'Mysql error %d: %s' % (e.args[0], e.args[1])

try:
	query = 'select msgType, group_name, user, to_user, content,CreateTime from wx ' 
        if (condition != ""): 
		query = query + condition + " order by id DESC limit 50"
	else:
		query = query + "order by id DESC limit 50";

	#print query
	cur.execute(query)

	results = cur.fetchall()
	for r in results:
		if (r[4] == None):
			r[4] = '';
		if (r[1] != ""):
			head = r[1] + '|' + r[2] + "->" + r[3] + ":"
		else:
			head = r[2] + "->" + r[3] + ":"
		timeStamp = r[5]
		timeStr = time.strftime("%Y-%m-%d %H:%M", time.localtime(timeStamp))
		print '<tr>'
		print '<td colspan=1 style="word-break:break-all">' + timeStr + '</td>'
		print '<td colspan=2 style="word-break:break-all">' + head + '</td>'
		print '<td colspan=4 style="word-break:break-all">' + r[4] + '</td>'
		print '</tr>'

	print '</table>'

        conn.commit()

 	cur.close()
	conn.close()

except MySQLdb.Error,e:
	print 'Mysql error %d: %s' % (e.args[0], e.args[1])


