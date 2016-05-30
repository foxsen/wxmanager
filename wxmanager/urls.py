#!/usr/bin/env python
# coding=utf-8
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.IndexView.as_view(), name='home'),
    url(r'query/status/$', views.StatusView.as_view(), name='query_status'),
    url(r'query/content/$', views.ContentView.as_view(), name='query_content'),
]

