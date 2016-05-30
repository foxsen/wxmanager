from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.views.generic.base import TemplateView
from .models import Wx

import time

# Create your views here.
class LoggedInMixin(object):

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(LoggedInMixin, self).dispatch(*args, **kwargs)


class IndexView(LoggedInMixin,ListView):
    queryset = Wx.objects.all().order_by('-id')[:50]
    template_name = 'index.html'
    


class StatusView(LoggedInMixin, TemplateView):
    template_name = 'status.txt'

class ContentView(LoggedInMixin, ListView):
    queryset = Wx.objects.all()
    template_name = 'content_list.html'
    #queryset = Wx.objects.all()

    def get(self, request):
        user = request.GET.get('user', '')
        to_user = request.GET.get('to_user', '')
        start = request.GET.get('start', '')
        end = request.GET.get('end', '')
        contains = request.GET.get('contains', '')
        if (request.user.is_staff):
            group_name = request.GET.get('group_name', '')
        else:
            group_name = request.user.last_name

        if (user != ''): 
            self.queryset = self.queryset.filter(user = user)

        if (to_user != ''): 
            self.queryset = self.queryset.filter(to_user = user)

        if (start != ''): 
            timeArray = time.strptime(start, "%Y-%m-%d %H:%M")
            timeStamp = int(time.mktime(timeArray))
            print timeStamp
            self.queryset = self.queryset.filter(CreateTime__gt = timeStamp)

        if (end != ''): 
            timeArray = time.strptime(end, "%Y-%m-%d %H:%M")
            timeStamp = int(time.mktime(timeArray))
            self.queryset = self.queryset.filter(CreateTime__lt = timeStamp)

        if (contains != ''): 
            self.queryset = self.queryset.filter(content__contains = contains)

        if (group_name != ''): 
            self.queryset = self.queryset.filter(group_name__contains = group_name)

        self.queryset = self.queryset.order_by('-id')[:50]

        return super(ContentView, self).get(request)




