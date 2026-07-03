import random
import string
from django.db import models
from django.contrib.auth.models import User
from exams.models import Exam


def generate_class_code():
    while True:
        code = 'CLASS' + ''.join(random.choices(string.digits, k=2))
        if not ClassRoom.objects.filter(class_code=code).exists():
            return code


class ClassRoom(models.Model):
    name = models.CharField(max_length=100, verbose_name='班級名稱')
    description = models.TextField(blank=True, verbose_name='描述')
    class_code = models.CharField(max_length=10, unique=True, verbose_name='班級代號')
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_classes', verbose_name='建立者'
    )
    is_active = models.BooleanField(default=True, verbose_name='啟用')
    allow_join = models.BooleanField(default=True, verbose_name='允許加入')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新時間')

    class Meta:
        verbose_name = '班級'
        verbose_name_plural = '班級'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.class_code})'

    def save(self, *args, **kwargs):
        if not self.class_code:
            self.class_code = generate_class_code()
        super().save(*args, **kwargs)

    def student_count(self):
        return self.enrollments.filter(is_active=True).count()


class ClassEnrollment(models.Model):
    class_room = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name='enrollments'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='加入時間')
    is_active = models.BooleanField(default=True, verbose_name='啟用')

    class Meta:
        verbose_name = '班級成員'
        verbose_name_plural = '班級成員'
        unique_together = ('class_room', 'user')
        ordering = ['joined_at']

    def __str__(self):
        return f'{self.user.username} @ {self.class_room.name}'


class ClassExamAssignment(models.Model):
    class_room = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name='exam_assignments'
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='class_assignments')
    assigned_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='assigned_exams'
    )
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='開始時間')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='結束時間')
    is_required = models.BooleanField(default=True, verbose_name='必做')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='指派時間')

    class Meta:
        verbose_name = '班級考卷指派'
        verbose_name_plural = '班級考卷指派'
        unique_together = ('class_room', 'exam')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.class_room.name} - {self.exam.title}'
