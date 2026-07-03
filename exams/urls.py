from django.urls import path
from . import views

app_name = 'exams'

urlpatterns = [
    path('', views.exam_list, name='list'),
    path('create/', views.exam_create, name='create'),
    path('<int:pk>/', views.exam_detail, name='detail'),
    path('<int:pk>/edit/', views.exam_edit, name='edit'),
    path('<int:pk>/add-question/', views.exam_add_question, name='add_question'),
    path('<int:pk>/remove-question/<int:qpk>/', views.exam_remove_question, name='remove_question'),
    path('<int:pk>/results/', views.exam_results, name='results'),
    path('<int:pk>/results/export/', views.export_results_csv, name='export_csv'),
    path('join/', views.exam_join, name='join'),
    path('<int:pk>/start/', views.exam_start, name='start'),
    path('session/<int:pk>/', views.exam_session, name='session'),
    path('session/<int:pk>/save/', views.exam_save_answer, name='save_answer'),
    path('session/<int:pk>/submit/', views.exam_submit, name='submit'),
    path('session/<int:pk>/result/', views.exam_session_result, name='session_result'),
]
