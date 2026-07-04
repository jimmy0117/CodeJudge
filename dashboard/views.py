from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from practice.models import PracticeRecord, WrongQuestion
from exams.models import ExamSession
from classes.models import ClassRoom, ClassEnrollment


def get_weakness(user):
    records = PracticeRecord.objects.filter(user=user) \
        .values('question__category__name') \
        .annotate(
            total=Count('id'),
            correct=Count('id', filter=Q(is_correct=True))
        ) \
        .filter(total__gte=3) \
        .order_by('correct')
    return records


@login_required
def dashboard_index(request):
    user = request.user
    records = PracticeRecord.objects.filter(user=user)
    total = records.count()
    correct = records.filter(is_correct=True).count()
    wrong = total - correct
    accuracy = round(correct / total * 100, 1) if total else 0

    # Category stats
    cat_stats = records.values('question__category__name') \
        .annotate(
            total=Count('id'),
            correct=Count('id', filter=Q(is_correct=True))
        ).order_by('-total')

    cat_stats_with_pct = []
    for s in cat_stats:
        pct = round(s['correct'] / s['total'] * 100, 1) if s['total'] else 0
        cat_stats_with_pct.append({
            'name': s['question__category__name'] or '未分類',
            'total': s['total'],
            'correct': s['correct'],
            'pct': pct,
        })

    # Wrong questions
    wrong_count = WrongQuestion.objects.filter(user=user, is_resolved=False).count()

    # Recent records
    recent_records = records.select_related('question', 'question__category') \
                            .order_by('-answered_at')[:10]

    # Exam stats
    exam_sessions = ExamSession.objects.filter(
        user=user, is_submitted=True
    ).select_related('exam').order_by('-submitted_at')[:5]

    return render(request, 'dashboard/index.html', {
        'total': total,
        'correct': correct,
        'wrong': wrong,
        'accuracy': accuracy,
        'cat_stats': cat_stats_with_pct,
        'wrong_count': wrong_count,
        'recent_records': recent_records,
        'exam_sessions': exam_sessions,
    })


@login_required
def weakness_analysis(request):
    weakness = get_weakness(request.user)
    weakness_with_pct = []
    for w in weakness:
        pct = round(w['correct'] / w['total'] * 100, 1) if w['total'] else 0
        weakness_with_pct.append({
            'name': w['question__category__name'] or '未分類',
            'total': w['total'],
            'correct': w['correct'],
            'pct': pct,
        })
    return render(request, 'dashboard/weakness.html', {'weakness': weakness_with_pct})


@login_required
def practice_history(request):
    records = PracticeRecord.objects.filter(
        user=request.user
    ).select_related('question', 'question__category').order_by('-answered_at')

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(records, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/history.html', {'page_obj': page_obj})


@login_required
def site_settings_view(request):
    """管理員平台設定頁面（僅限管理員）。"""
    if not hasattr(request.user, 'profile') or not request.user.profile.is_teacher_or_admin():
        messages.error(request, '此頁面僅限管理員使用。')
        return redirect('dashboard:index')

    from accounts.models import SiteSettings
    settings_obj = SiteSettings.get_solo()

    if request.method == 'POST':
        # ── 基本資訊 ────────────────────────────────────────────────────────
        settings_obj.site_name   = request.POST.get('site_name', 'APCS 練習平台').strip() or 'APCS 練習平台'
        settings_obj.footer_text = request.POST.get('footer_text', '').strip()

        # Icon 上傳
        if 'site_icon' in request.FILES:
            # 刪除舊檔案
            if settings_obj.site_icon:
                settings_obj.site_icon.delete(save=False)
            settings_obj.site_icon = request.FILES['site_icon']
        # 明確移除 icon
        if request.POST.get('remove_icon') == '1' and settings_obj.site_icon:
            settings_obj.site_icon.delete(save=False)
            settings_obj.site_icon = None

        # ── 顏色主題 ────────────────────────────────────────────────────────
        import re
        hex_re = re.compile(r'^#[0-9A-Fa-f]{6}$')

        def safe_color(val, default):
            val = (val or '').strip()
            return val if hex_re.match(val) else default

        settings_obj.navbar_color  = safe_color(request.POST.get('navbar_color'),  '#212529')
        settings_obj.primary_color = safe_color(request.POST.get('primary_color'), '#0d6efd')
        settings_obj.hero_color    = safe_color(request.POST.get('hero_color'),    '#212529')

        # ── Google OAuth ────────────────────────────────────────────────────
        settings_obj.google_oauth_enabled  = request.POST.get('google_oauth_enabled') == 'on'
        settings_obj.google_oauth_client_id = request.POST.get('google_oauth_client_id', '').strip()
        new_secret = request.POST.get('google_oauth_client_secret', '').strip()
        if new_secret:
            settings_obj.google_oauth_client_secret = new_secret
        if request.POST.get('clear_secret') == '1':
            settings_obj.google_oauth_client_secret = ''

        settings_obj.save()
        messages.success(request, '平台設定已儲存。')
        return redirect('dashboard:settings')

    return render(request, 'dashboard/settings.html', {'settings_obj': settings_obj})


@login_required
def class_stats(request):
    """Teacher/Admin class statistics."""
    if not hasattr(request.user, 'profile') or not request.user.profile.is_teacher_or_admin():
        from django.contrib import messages
        messages.error(request, '此功能僅限教師或管理員。')
        return dashboard_index(request)

    my_classes = ClassRoom.objects.filter(created_by=request.user, is_active=True)
    return render(request, 'dashboard/class_stats.html', {'my_classes': my_classes})
