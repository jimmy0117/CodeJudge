from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import RegisterForm, ProfileUpdateForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # 專案同時設定了 GoogleOAuth2 + ModelBackend 兩個 AUTHENTICATION_BACKENDS，
            # login() 在有多個 backend 時必須明確指定要用哪一個，否則會丟出
            # ValueError 導致註冊送出後 500（帳號其實已建立，只是沒登入成功）。
            # 這裡走的是帳密註冊，固定用 ModelBackend。
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'歡迎加入，{user.username}！帳號已成功建立。')
            return redirect('home')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'歡迎回來，{username}！')
                # ?next= 是使用者端可以任意帶入的參數，直接 redirect 會是開放
                # 重新導向：攻擊者可以發「這是平台真實的登入連結」，帳密登入
                # 也真的成功，但登入後被導去外部的釣魚頁。這裡驗證 next 是不是
                # 同一個網站，不是的話一律退回首頁。
                next_url = request.GET.get('next', '')
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                ):
                    return redirect(next_url)
                return redirect('home')
        else:
            messages.error(request, '使用者名稱或密碼錯誤，請重試。')
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, '您已成功登出。')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '個人資料已更新。')
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, '密碼已成功更新。')
            return redirect('accounts:profile')
        else:
            messages.error(request, '請修正下方的錯誤。')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})
