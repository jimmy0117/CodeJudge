from django.urls import path
from . import views

app_name = 'practice'

urlpatterns = [
    path('', views.practice_start, name='start'),
    path('question/', views.practice_question, name='question'),
    path('next/', views.practice_next, name='next'),
    path('wrong/', views.wrong_list, name='wrong_list'),
    path('favorites/', views.favorites, name='favorites'),
    path('favorite/<int:pk>/toggle/', views.toggle_favorite, name='toggle_favorite'),
    path('notes/', views.notes_list, name='notes'),
    path('note/<int:pk>/edit/', views.note_edit, name='note_edit'),
]
