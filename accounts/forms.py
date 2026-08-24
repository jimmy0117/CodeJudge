from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile


class RegisterForm(UserCreationForm):
    """一般使用者自助註冊表單。

    刻意不提供角色選擇欄位：自助註冊一律建立為「學生」帳號
    （由 accounts.models.create_user_profile signal 決定預設值）。
    教師 / 管理員身分不可由使用者自行選取，只能由既有管理員
    透過 Django Admin 的 UserProfile 後台指派，避免任何訪客
    在註冊時勾選「管理員」就直接取得題庫/考卷/班級管理權限。
    """
    email = forms.EmailField(required=True, label='電子郵件')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        labels = {
            'username': '使用者名稱',
        }

    def clean_email(self):
        email = self.cleaned_data['email']
        # email 沒有唯一性檢查的話，兩個帳號可以共用同一個 email；
        # 忘記密碼是用 email 查帳號，共用的話會把好幾組不同帳號的
        # 重設連結一起寄到同一封信裡，混淆使用者也可能被誤用。
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('這個電子郵件已經被其他帳號使用了。')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=False, label='名字')
    last_name = forms.CharField(max_length=150, required=False, label='姓氏')
    email = forms.EmailField(required=True, label='電子郵件')

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['first_name'].initial = self.instance.first_name
            self.fields['last_name'].initial = self.instance.last_name
            self.fields['email'].initial = self.instance.email

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('這個電子郵件已經被其他帳號使用了。')
        return email
