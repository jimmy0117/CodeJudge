from django import forms
from questions.models import Category


class PracticeStartForm(forms.Form):
    MODE_CHOICES = [
        ('free', '自由練習'),
        ('random', '隨機練習'),
        ('wrong', '錯題複習'),
        ('favorite', '收藏練習'),
        ('weakness', '弱點練習'),
    ]
    mode = forms.ChoiceField(choices=MODE_CHOICES, label='練習模式')
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        label='分類',
        empty_label='所有分類'
    )
    difficulty = forms.ChoiceField(
        choices=[('', '所有難度'), ('easy', '簡單'), ('medium', '中等'), ('hard', '困難')],
        required=False,
        label='難度'
    )
    count = forms.IntegerField(
        min_value=1, max_value=50, initial=10,
        label='題數',
        widget=forms.NumberInput(attrs={'min': 1, 'max': 50})
    )


class NoteForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': '在這裡記錄你的筆記...'}),
        label='筆記內容'
    )
