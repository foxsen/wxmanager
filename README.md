# wxmanager

这是一套用于记录和管理微信的工具，它包括三个部分：

1. 一个Django写的网页前端。它可以查询记录在数据库中的微信记录,可以设置按时间、发言人、群名等不同的查询条件，也可以设置自动刷新已达到直播的效果。

Screenshort:
    ![image](https://github.com/foxsen/wxmanager/raw/master/screenshots/screen1.jpg)

2. 一个python写的微信记录抓取后端。它由[WeixinBot](https://github.com/Urinxs/WeixinBot)项目改造而来，利用微信网页版的接口获取指定账户的所有微信信息，解析后存入数据库。有关接口的文档，可以参见WeixinBot项目。

主要的修改包括：

* 统一用requests库，去除对urllib/urllib2的依赖
* 增加数据库存储操作
* 鲁棒性加强： 处理输入无效时的异常，避免不必要的退出; 增加SafeSession，对一个连接的异常进行自动重试；synchost轮转避免同步失败直接放弃。 （实测连续运行两周以上没有中断)；
* 其他一些小的改进，格式调整等

3. 一些辅助部署的工具和资料，在tools/目录下。包括一个定期执行的脚本检查服务运行状态，以便网页前端可以看到微信抓取服务的状态和后端抓取程序对应的systemd配置。

## 部署使用

1. 网页前端的部署参考常规的django项目部署，可以直接用python自带的网页服务器，也可以部署到apache等服务器。

前者的参考步骤：
* git clone https://githubcom/foxsen/wxmanager
* cd wxmanager
* pip install -r requirements.txt
* 修改mysite/settings.py，设置数据库源等相关信息(SECRET_KEY/ALLOWED_HOSTS/DATABASES/STATIC_URL/STATIC_ROOT/)
* python manage.py migrate
* python manage.py runserver
* 访问127.0.0.1:8000

部署到apache服务器可以参考如下配置：

	alias /wxlogger/saved /var/www/html/wxlogger/saved/
	alias /static /var/www/html/wxlogger/saved/
	<Directory /var/www/html/wxlogger/saved>
		Require all granted
	</Directory>

	WSGIScriptAlias / /home/fxzhang/wxmanager/mysite/wsgi.py
	WSGIPythonPath /home/fxzhang/wxmanager/

	<Directory /home/fxzhang/wxmanager/mysite>
		<Files wsgi.py>
			Require all granted
		</Files>
	</Directory>

其中，假设wxlogger把静态文件（微信中的图片语音视频等）放到/var/www/html/wxlogger/saved/目录下，采用的链接前缀是/static。同时，还需要使能mod_wsgi。

2. 抓取后端

pip install -r requirements.txt也将安装wxlogger的依赖包

2.1 前台运行

测试时可以用:

    ./wxlogger.py -f -l <link_prefix> -s <save_folder>

来直接在命令行下运行，它将在终端上输出一个二维码，通过扫描二维码登录一个微信账号即可开始记录。wxlogger将图片语音视频等内容以文件形式存放到save_folder指定的目录里，并生成带有link_prefix前缀的url以便在web服务器显示时链接到对应内容文件。link_prefix缺省为/static，save_folder 缺省为/var/www/html/wxlogger/saved。

2.2 采用systemd来做后台运行

参考tools/wxlogger.service文件，修改其中的程序所在目录以及命令行参数。 其中--link_prefix 以及 --save_folder需要和本机上的web前端配合，link_prefix指向web服务器上静态文件根目录，save_folder则为其实际物理目录名。

将该文件放到合适的目录中，例如/etc/systemd/system/，然后运行sudo systemctl start wxlogger启动服务。

3. 其他

可以用crontab运行定期执行的脚本，参考如下(每分钟运行一次检查)：

    0-59 * * * * /home/user/wxmanager/tools/check_server.py > /home/user/wxmanager/wxmanager/templates/status.txt

为了简单起见，目前web前端通过templates目录下的status.txt文件获取当前服务器状态信息。

