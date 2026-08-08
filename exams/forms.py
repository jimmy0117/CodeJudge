from django import forms
from .models import Exam


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = (
            'title', 'description', 'time_limit',
            'is_active', 'show_score', 'show_explanation',
            'anti_cheat', 'official_ui',
            'start_time', 'end_time'
        )
        labels = {
            'title': '考卷名稱',
            'description': '描述',
            'time_limit': '時間限制（分鐘）',
            'is_active': '啟用',
            'show_score': '交卷後顯示分數',
            'show_explanation': '交卷後顯示詳解',
            'anti_cheat': '啟用防作弊（偵測切換視窗／分頁）',
            'official_ui': '模擬 APCS 正式考試介面',
            'start_time': '開始時間',
            'end_time': '結束時間',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class ExamJoinForm(forms.Form):
    code = forms.CharField(
        max_length=10,
        label='考卷代號',
        widget=forms.TextInput(attrs={
            'placeholder': '輸入6碼考卷代號',
            'class': 'form-control form-control-lg text-uppercase'
        })
    )

    def clean_code(self):
        return self.cleaned_data['code'].upper().strip()
