from django.db import models

DIFFICULTY_CHOICES = [
    ('easy', '簡單'),
    ('medium', '中等'),
    ('hard', '困難'),
]


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='分類名稱')
    description = models.TextField(blank=True, verbose_name='描述')

    class Meta:
        verbose_name = '分類'
        verbose_name_plural = '分類'
        ordering = ['name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name='標籤名稱')

    class Meta:
        verbose_name = '標籤'
        verbose_name_plural = '標籤'
        ordering = ['name']

    def __str__(self):
        return self.name


class Question(models.Model):
    ANSWER_CHOICES = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('E', 'E')]

    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='分類', related_name='questions'
    )
    tags = models.ManyToManyField(Tag, blank=True, verbose_name='標籤')
    title = models.CharField(max_length=200, verbose_name='題目標題')
    content = models.TextField(verbose_name='題目內容')
    option_a = models.TextField(verbose_name='選項 A')
    option_b = models.TextField(verbose_name='選項 B')
    option_c = models.TextField(verbose_name='選項 C')
    option_d = models.TextField(verbose_name='選項 D')
    option_e = models.TextField(blank=True, verbose_name='選項 E（可留空）')
    correct_answer = models.CharField(
        max_length=1, choices=ANSWER_CHOICES, verbose_name='正確答案'
    )
    hint = models.TextField(blank=True, verbose_name='提示')
    solution_idea = models.TextField(blank=True, verbose_name='解題思路')
    explanation = models.TextField(blank=True, verbose_name='詳細解說')
    difficulty = models.CharField(
        max_length=10, choices=DIFFICULTY_CHOICES, default='medium', verbose_name='難度'
    )
    year = models.IntegerField(null=True, blank=True, verbose_name='年份')
    is_active = models.BooleanField(default=True, verbose_name='啟用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='建立時間')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新時間')

    class Meta:
        verbose_name = '題目'
        verbose_name_plural = '題目'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_difficulty_display()}] {self.title}'

    def get_options(self):
        opts = [
            ('A', self.option_a),
            ('B', self.option_b),
            ('C', self.option_c),
            ('D', self.option_d),
        ]
        if self.option_e:
            opts.append(('E', self.option_e))
        return opts
