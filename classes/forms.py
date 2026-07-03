from django import forms
from .models import ClassRoom, ClassExamAssignment
from exams.models import Exam


class ClassRoomForm(forms.ModelForm):
    class Meta:
        model = ClassRoom
        fields = ('name', 'description', 'is_active', 'allow_join')
        labels = {
            'name': '班級名稱',
            'description': '描述',
            'is_active': '啟用',
            'allow_join': '允許學生加入',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ClassJoinForm(forms.Form):
    class_code = forms.CharField(
        max_length=10,
        label='班級代號',
        widget=forms.TextInput(attrs={
            'placeholder': '輸入班級代號 (例如 CLASS01)',
            'class': 'form-control form-control-lg text-uppercase'
        })
    )

    def clean_class_code(self):
        return self.cleaned_data['class_code'].upper().strip()


class AssignExamForm(forms.Form):
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.none(),
        label='選擇考卷',
        empty_label='-- 請選擇考卷 --'
    )
    start_time = forms.DateTimeField(
        required=False,
        label='開始時間',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    end_time = forms.DateTimeField(
        required=False,
        label='結束時間',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    is_required = forms.BooleanField(required=False, label='必做', initial=True)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['exam'].queryset = Exam.objects.filter(created_by=user, is_active=True)
