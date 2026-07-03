from django import forms
from .models import Question, Category, Tag


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'description')
        labels = {
            'name': '分類名稱',
            'description': '描述',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class QuestionForm(forms.ModelForm):
    tags_input = forms.CharField(
        required=False,
        label='標籤（以逗號分隔）',
        help_text='例如：迴圈, 陣列, 字串',
        widget=forms.TextInput(attrs={'placeholder': '迴圈, 陣列, 字串'})
    )

    class Meta:
        model = Question
        fields = (
            'category', 'title', 'content',
            'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'difficulty', 'year',
            'hint', 'solution_idea', 'explanation', 'is_active'
        )
        labels = {
            'category': '分類',
            'title': '題目標題',
            'content': '題目內容',
            'option_a': '選項 A',
            'option_b': '選項 B',
            'option_c': '選項 C',
            'option_d': '選項 D',
            'correct_answer': '正確答案',
            'difficulty': '難度',
            'year': '年份',
            'hint': '提示',
            'solution_idea': '解題思路',
            'explanation': '詳細解說',
            'is_active': '啟用',
        }
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5}),
            'option_a': forms.Textarea(attrs={'rows': 2}),
            'option_b': forms.Textarea(attrs={'rows': 2}),
            'option_c': forms.Textarea(attrs={'rows': 2}),
            'option_d': forms.Textarea(attrs={'rows': 2}),
            'hint': forms.Textarea(attrs={'rows': 3}),
            'solution_idea': forms.Textarea(attrs={'rows': 4}),
            'explanation': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['tags_input'].initial = ', '.join(
                t.name for t in self.instance.tags.all()
            )

    def save(self, commit=True):
        question = super().save(commit=commit)
        if commit:
            tags_raw = self.cleaned_data.get('tags_input', '')
            tag_names = [t.strip() for t in tags_raw.split(',') if t.strip()]
            tags = []
            for name in tag_names:
                tag, _ = Tag.objects.get_or_create(name=name)
                tags.append(tag)
            question.tags.set(tags)
        return question


class QuestionFilterForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        label='分類',
        empty_label='所有分類',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    difficulty = forms.ChoiceField(
        choices=[('', '所有難度'), ('easy', '簡單'), ('medium', '中等'), ('hard', '困難')],
        required=False,
        label='難度',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    year = forms.IntegerField(
        required=False,
        label='年份',
        widget=forms.NumberInput(attrs={'placeholder': '例如：2023', 'class': 'form-control form-control-sm'})
    )
    keyword = forms.CharField(
        required=False,
        label='關鍵字',
        widget=forms.TextInput(attrs={'placeholder': '搜尋題目...', 'class': 'form-control form-control-sm'}),
        max_length=100
    )
