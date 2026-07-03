from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_index, name='index'),
    path('weakness/', views.weakness_analysis, name='weakness'),
    path('history/', views.practice_history, name='history'),
    path('class-stats/', views.class_stats, name='class_stats'),
]
