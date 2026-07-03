from django.db import models
from django.contrib.auth.models import User
from questions.models import Question

CONFIDENCE_CHOICES = [
    ('sure', '很確定'),
    ('unsure', '不太確定'),
    ('guess', '猜的'),
]


class PracticeRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='practice_records')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='practice_records')
    selected_answer = models.CharField(max_length=1, verbose_name='選擇的答案')
    confidence = models.CharField(
        max_length=10, choices=CONFIDENCE_CHOICES, blank=True, verbose_name='信心程度'
    )
    is_correct = models.BooleanField(verbose_name='是否答對')
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name='作答時間')

    class Meta:
        verbose_name = '練習紀錄'
        verbose_name_plural = '練習紀錄'
        ordering = ['-answered_at']

    def __str__(self):
        status = '答對' if self.is_correct else '答錯'
        return f'{self.user.username} - {self.question.title[:30]} - {status}'


class WrongQuestion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wrong_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='wrong_by')
    wrong_count = models.IntegerField(default=1, verbose_name='錯誤次數')
    review_count = models.IntegerField(default=0, verbose_name='複習次數（連續答對）')
    next_review_at = models.DateTimeField(null=True, blank=True, verbose_name='下次複習時間')
    is_resolved = models.BooleanField(default=False, verbose_name='是否已解決')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新時間')

    class Meta:
        verbose_name = '錯題'
        verbose_name_plural = '錯題'
        unique_together = ('user', 'question')
        ordering = ['next_review_at']

    def __str__(self):
        return f'{self.user.username} - {self.question.title[:30]} (錯{self.wrong_count}次)'


class FavoriteQuestion(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='收藏時間')

    class Meta:
        verbose_name = '收藏題目'
        verbose_name_plural = '收藏題目'
        unique_together = ('user', 'question')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} 收藏 {self.question.title[:30]}'


class QuestionNote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField(verbose_name='筆記內容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新時間')

    class Meta:
        verbose_name = '筆記'
        verbose_name_plural = '筆記'
        unique_together = ('user', 'question')
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.user.username} 的筆記 - {self.question.title[:30]}'
