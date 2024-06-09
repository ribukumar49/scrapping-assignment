INSTALLED_APPS = [
    'rest_framework',
    'scraper',
    'django_celery_results',
]

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# setup model
from django.db import models
import uuid

class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    job = models.ForeignKey(Job, related_name='tasks', on_delete=models.CASCADE)
    coin = models.CharField(max_length=50)
    output = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coin_scraper.settings')

app = Celery('coin_scraper')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

from __future__ import absolute_import, unicode_literals

from .celery import app as celery_app

__all__ = ('celery_app',)

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By

class CoinMarketCap:
    BASE_URL = "https://coinmarketcap.com/currencies/{}/"

    def __init__(self):
        self.driver = webdriver.Chrome(executable_path='/path/to/chromedriver')

    def fetch_coin_data(self, coin):
        url = self.BASE_URL.format(coin.lower())
        self.driver.get(url)
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')

        data = {
            'price': self.get_price(soup),
            'price_change': self.get_price_change(soup),
            'market_cap': self.get_market_cap(soup),
            'market_cap_rank': self.get_market_cap_rank(soup),
            'volume': self.get_volume(soup),
            'volume_rank': self.get_volume_rank(soup),
            'volume_change': self.get_volume_change(soup),
            'circulating_supply': self.get_circulating_supply(soup),
            'total_supply': self.get_total_supply(soup),
            'diluted_market_cap': self.get_diluted_market_cap(soup),
            'contracts': self.get_contracts(soup),
            'official_links': self.get_official_links(soup),
            'socials': self.get_socials(soup)
        }

        return data
from celery import shared_task
from .models import Job, Task
from .coinmarketcap import CoinMarketCap

@shared_task
def scrape_coin_data(job_id, coin):
    job = Job.objects.get(id=job_id)
    cmc = CoinMarketCap()
    data = cmc.fetch_coin_data(coin)
    Task.objects.create(job=job, coin=coin, output=data)

from rest_framework import serializers
from .models import Job, Task

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['coin', 'output']

class JobSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True)

    class Meta:
        model = Job
        fields = ['id', 'tasks']

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Job, Task
from .serializers import JobSerializer
from .tasks import scrape_coin_data

class StartScrapingView(APIView):
    def post(self, request):
        coins = request.data
        if not all(isinstance(coin, str) for coin in coins):
            return Response({'error': 'Invalid input'}, status=status.HTTP_400_BAD_REQUEST)

        job = Job.objects.create()
        for coin in coins:
            scrape_coin_data.delay(job.id, coin)

        return Response({'job_id': job.id}, status=status.HTTP_201_CREATED)

class ScrapingStatusView(APIView):
    def get(self, request, job_id):
        job = Job.objects.get(id=job_id)
        serializer = JobSerializer(job)
        return Response(serializer.data)

from django.urls import path
from .views import StartScrapingView, ScrapingStatusView

urlpatterns = [
    path('taskmanager/start_scraping', StartScrapingView.as_view(), name='start-scraping'),
    path('taskmanager/scraping_status/<uuid:job_id>', ScrapingStatusView.as_view(), name='scraping-status'),
]

from django.urls import path, include

urlpatterns = [
    path('api/', include('scraper.urls')),
]



