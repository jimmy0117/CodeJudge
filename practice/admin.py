from django.contrib import admin
from .models import PracticeRecord, WrongQuestion, FavoriteQuestion, QuestionNote


@admin.register(PracticeRecord)
class PracticeRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'selected_answer', 'is_correct', 'confidence', 'answered_at')
    list_filter = ('is_correct', 'confidence')
    search_fields = ('user__username', 'question__title')
    date_hierarchy = 'answered_at'


@admin.register(WrongQuestion)
class WrongQuestionAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'wrong_count', 'review_count', 'is_resolved', 'next_review_at')
    list_filter = ('is_resolved',)
    search_fields = ('user__username', 'question__title')


@admin.register(FavoriteQuestion)
class FavoriteQuestionAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'created_at')
    search_fields = ('user__username', 'question__title')


@admin.register(QuestionNote)
class QuestionNoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'updated_at')
    search_fields = ('user__username', 'question__title', 'content')
