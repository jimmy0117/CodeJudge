from django.contrib import admin
from .models import Question, Category, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'difficulty', 'year', 'is_active', 'created_at')
    list_filter = ('difficulty', 'category', 'is_active', 'year')
    search_fields = ('title', 'content')
    filter_horizontal = ('tags',)
    list_editable = ('is_active',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('基本資訊', {
            'fields': ('title', 'content', 'category', 'tags', 'difficulty', 'year', 'is_active')
        }),
        ('選項', {
            'fields': ('option_a', 'option_b', 'option_c', 'option_d', 'correct_answer')
        }),
        ('詳解', {
            'fields': ('hint', 'solution_idea', 'explanation'),
            'classes': ('collapse',)
        }),
        ('時間戳記', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
