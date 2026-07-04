import random
import string
from django.db import models
from django.contrib.auth.models import User
from questions.models import Question


def generate_exam_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Exam.objects.filter(code=code).exists():
            return code


class Exam(models.Model):
    title = models.CharField(max_length=200, verbose_name='考卷名稱')
    description = models.TextField(blank=True, verbose_name='描述')
    code = models.CharField(max_length=10, unique=True, verbose_name='考卷代號')
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_exams', verbose_name='建立者'
    )
    time_limit = models.IntegerField(default=30, help_text='分鐘', verbose_name='時間限制（分鐘）')
    is_active = models.BooleanField(default=True, verbose_name='啟用')
    show_score = models.BooleanField(default=True, verbose_name='顯示分數')
    show_explanation = models.BooleanField(default=False, verbose_name='顯示詳解')
    anti_cheat = models.BooleanField(default=False, verbose_name='啟用防作弊（切換視窗偵測）')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='開始時間')
    end_time = models.DateTimeField(null=True, blank=True, verbose_name='結束時間')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新時間')

    class Meta:
        verbose_name = '考卷'
        verbose_name_plural = '考卷'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.code})'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_exam_code()
        super().save(*args, **kwargs)

    def total_score(self):
        return sum(eq.score for eq in self.exam_questions.all())

    def question_count(self):
        return self.exam_questions.count()


class ExamQuestion(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='exam_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='in_exams')
    order = models.IntegerField(default=0, verbose_name='順序')
    score = models.IntegerField(default=5, verbose_name='分數')

    class Meta:
        verbose_name = '考卷題目'
        verbose_name_plural = '考卷題目'
        unique_together = ('exam', 'question')
        ordering = ['order']

    def __str__(self):
        return f'{self.exam.title} - 第{self.order}題'


class ExamSession(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='sessions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_sessions')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='開始時間')
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name='交卷時間')
    score = models.IntegerField(default=0, verbose_name='分數')
    is_submitted = models.BooleanField(default=False, verbose_name='已交卷')
    cheat_count = models.IntegerField(default=0, verbose_name='切換視窗次數')

    class Meta:
        verbose_name = '考試紀錄'
        verbose_name_plural = '考試紀錄'
        unique_together = ('exam', 'user')
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.user.username} - {self.exam.title}'


class ExamAnswer(models.Model):
    exam_session = models.ForeignKey(
        ExamSession, on_delete=models.CASCADE, related_name='answers'
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=1, blank=True, verbose_name='選擇的答案')
    confidence = models.CharField(max_length=10, blank=True, verbose_name='信心程度')
    is_correct = models.BooleanField(default=False, verbose_name='是否答對')
    answered_at = models.DateTimeField(auto_now=True, verbose_name='作答時間')

    class Meta:
        verbose_name = '考試答案'
        verbose_name_plural = '考試答案'
        unique_together = ('exam_session', 'question')

    def __str__(self):
        return f'{self.exam_session} - Q{self.question_id}'
