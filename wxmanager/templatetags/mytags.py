#!/usr/bin/env python
# coding=utf-8

import datetime

from django import template  
  
register = template.Library()  
  
@register.filter(name='to_datetime')  
def to_datetime(ts):  
    return datetime.datetime.fromtimestamp(ts)
  
