from __future__ import unicode_literals

from django.db import models

# Create your models here.
class Wx(models.Model):
    msgType = models.IntegerField(default=0)
    msgId = models.CharField(max_length=256,default='')
    CreateTime = models.IntegerField(default=0)
    msg = models.CharField(max_length=4096,default='')
    content = models.CharField(max_length=2048,default='')
    group_name = models.CharField(max_length=256,default='')
    user = models.CharField(max_length=256,default='')
    to_user = models.CharField(max_length=256,default='')

    def __unicode__(self):
        return self.content
