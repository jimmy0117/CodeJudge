from django.contrib import admin
from .models import Exam, ExamQuestion, ExamSession, ExamAnswer


class ExamQuestionInline(admin.TabularInline):
    model = ExamQuestion
    extra = 0


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'code', 'created_by', 'time_limit', 'is_active', 'created_at')
    list_filter = ('is_active', 'show_score', 'show_explanation')
    search_fields = ('title', 'code', 'created_by__username')
    inlines = [ExamQuestionInline]
    readonly_fields = ('code', 'created_at', 'updated_at')


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'exam', 'score', 'is_submitted', 'started_at', 'submitted_at')
    list_filter = ('is_submitted',)
    search_fields = ('user__username', 'exam__title')


@admin.register(ExamAnswer)
class ExamAnswerAdmin(admin.ModelAdmin):
    list_display = ('exam_session', 'question', 'selected_answer', 'is_correct')
    list_filter = ('is_correct',)
