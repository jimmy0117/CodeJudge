from django.urls import path
from . import views

app_name = 'questions'

urlpatterns = [
    path('', views.question_list, name='list'),
    path('<int:pk>/', views.question_detail, name='detail'),
    path('create/', views.question_create, name='create'),
    path('<int:pk>/edit/', views.question_edit, name='edit'),
    path('<int:pk>/delete/', views.question_delete, name='delete'),
    path('categories/', views.category_list, name='category_list'),
    path('import/', views.question_import, name='import'),
    path('import/sample/', views.download_sample_csv, name='import_sample'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
]
