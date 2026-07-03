from django.shortcuts import render
from django.contrib.auth.decorators import login_required
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
def class_stats(request):
    """Teacher/Admin class statistics."""
    if not hasattr(request.user, 'profile') or not request.user.profile.is_teacher_or_admin():
        from django.contrib import messages
        messages.error(request, '此功能僅限教師或管理員。')
        return dashboard_index(request)

    my_classes = ClassRoom.objects.filter(created_by=request.user, is_active=True)
    return render(request, 'dashboard/class_stats.html', {'my_classes': my_classes})
