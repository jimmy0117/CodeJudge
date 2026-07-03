from django.contrib import admin
from .models import ClassRoom, ClassEnrollment, ClassExamAssignment


class ClassEnrollmentInline(admin.TabularInline):
    model = ClassEnrollment
    extra = 0


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'class_code', 'created_by', 'is_active', 'allow_join', 'created_at')
    list_filter = ('is_active', 'allow_join')
    search_fields = ('name', 'class_code', 'created_by__username')
    inlines = [ClassEnrollmentInline]
    readonly_fields = ('class_code', 'created_at', 'updated_at')


@admin.register(ClassEnrollment)
class ClassEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'class_room', 'joined_at', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'class_room__name')


@admin.register(ClassExamAssignment)
class ClassExamAssignmentAdmin(admin.ModelAdmin):
    list_display = ('class_room', 'exam', 'assigned_by', 'is_required', 'created_at')
    list_filter = ('is_required',)
