from django.urls import path
from . import views

app_name = 'classes'

urlpatterns = [
    path('', views.class_list, name='list'),
    path('create/', views.class_create, name='create'),
    path('<int:pk>/', views.class_detail, name='detail'),
    path('join/', views.class_join, name='join'),
    path('<int:pk>/leave/', views.class_leave, name='leave'),
    path('<int:pk>/delete/', views.class_delete, name='delete'),
    path('<int:pk>/students/', views.class_students, name='students'),
    path('<int:pk>/students/batch-create/', views.class_batch_create_students, name='batch_create_students'),
    path('<int:pk>/students/batch-create/result/', views.class_batch_create_students_result, name='batch_create_students_result'),
    path('<int:pk>/students/batch-create/export/', views.class_batch_create_students_csv, name='batch_create_students_csv'),
    path('<int:pk>/assign-exam/', views.class_assign_exam, name='assign_exam'),
    path('<int:pk>/results/', views.class_results, name='results'),
]
