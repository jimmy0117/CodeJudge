import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import Q, F
from .models import Exam, ExamQuestion, ExamSession, ExamAnswer
from .forms import ExamForm, ExamJoinForm
from questions.models import Question, Category
from config.csv_utils import csv_safe


def teacher_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.is_teacher_or_admin():
            messages.error(request, '此功能僅限教師或管理員使用。')
            return redirect('exams:list')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
def exam_list(request):
    is_privileged = hasattr(request.user, 'profile') and request.user.profile.is_teacher_or_admin()
    if is_privileged:
        exams = Exam.objects.filter(created_by=request.user).order_by('-created_at')
    else:
        # Students see exams they've taken or can join
        session_exam_ids = ExamSession.objects.filter(
            user=request.user
        ).values_list('exam_id', flat=True)
        exams = Exam.objects.filter(id__in=session_exam_ids)
    return render(request, 'exams/list.html', {'exams': exams, 'is_privileged': is_privileged})


@teacher_required
def exam_create(request):
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.created_by = request.user
            exam.save()
            messages.success(request, f'考卷「{exam.title}」已建立，代號：{exam.code}')
            return redirect('exams:detail', pk=exam.pk)
    else:
        form = ExamForm()
    return render(request, 'exams/create.html', {'form': form, 'action': '新增'})


@teacher_required
def exam_edit(request, pk):
    exam = get_object_or_404(Exam, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam)
        if form.is_valid():
            form.save()
            messages.success(request, '考卷已更新。')
            return redirect('exams:detail', pk=exam.pk)
    else:
        form = ExamForm(instance=exam)
    return render(request, 'exams/create.html', {'form': form, 'exam': exam, 'action': '編輯'})


@teacher_required
def exam_detail(request, pk):
    # 跟同檔案其他 view（exam_edit / exam_update_scores / exam_results 等）一致，
    # 一定要限定 created_by=request.user，否則任何教師只要知道別人考卷的 pk
    # 就能看到完整題目與配分（IDOR）。
    exam = get_object_or_404(Exam, pk=pk, created_by=request.user)
    exam_questions = exam.exam_questions.select_related('question', 'question__category').all()
    existing_ids = exam_questions.values_list('question_id', flat=True)
    all_questions = Question.objects.filter(is_active=True).exclude(
        pk__in=existing_ids
    ).select_related('category')
    categories = Category.objects.all()
    return render(request, 'exams/detail.html', {
        'exam': exam,
        'exam_questions': exam_questions,
        'all_questions': all_questions,
        'categories': categories,
    })


@teacher_required
def exam_add_question(request, pk):
    exam = get_object_or_404(Exam, pk=pk, created_by=request.user)
    if request.method == 'POST':
        raw_ids = request.POST.get('question_ids', '')
        ids = [int(x) for x in raw_ids.split(',') if x.strip().isdigit()]
        try:
            default_score = int(request.POST.get('default_score', 5))
        except (TypeError, ValueError):
            default_score = 5
        default_score = max(default_score, 0)

        if not ids:
            messages.warning(request, '請至少選擇一題再加入。')
            return redirect('exams:detail', pk=pk)

        existing_ids = set(exam.exam_questions.values_list('question_id', flat=True))
        next_order = exam.exam_questions.count() + 1
        questions = Question.objects.filter(pk__in=ids, is_active=True)
        added = 0
        for question in questions:
            if question.pk in existing_ids:
                continue
            ExamQuestion.objects.create(
                exam=exam, question=question, order=next_order, score=default_score
            )
            next_order += 1
            added += 1

        if added:
            messages.success(request, f'已加入 {added} 題，每題 {default_score} 分。')
        else:
            messages.info(request, '所選題目皆已在考卷中。')
    return redirect('exams:detail', pk=pk)


@teacher_required
def question_preview(request, pk):
    question = get_object_or_404(Question, pk=pk, is_active=True)
    html = render_to_string(
        'exams/_question_preview.html', {'question': question}, request=request
    )
    return JsonResponse({'html': html, 'title': question.title})


@teacher_required
def exam_update_scores(request, pk):
    exam = get_object_or_404(Exam, pk=pk, created_by=request.user)
    if request.method == 'POST':
        updated = 0
        for eq in exam.exam_questions.all():
            field_name = f'score_{eq.pk}'
            if field_name not in request.POST:
                continue
            try:
                new_score = int(request.POST[field_name])
            except (TypeError, ValueError):
                continue
            new_score = max(new_score, 0)
            if new_score != eq.score:
                eq.score = new_score
                eq.save(update_fields=['score'])
                updated += 1
        if updated:
            messages.success(request, f'已更新 {updated} 題的分數，考卷滿分 {exam.total_score()} 分。')
        else:
            messages.info(request, '分數沒有變更。')
    return redirect('exams:detail', pk=pk)


@teacher_required
def exam_remove_question(request, pk, qpk):
    exam = get_object_or_404(Exam, pk=pk, created_by=request.user)
    eq = get_object_or_404(ExamQuestion, pk=qpk, exam=exam)
    if request.method == 'POST':
        eq.delete()
        messages.success(request, '題目已從考卷移除。')
    return redirect('exams:detail', pk=pk)


@teacher_required
def exam_results(request, pk):
    exam = get_object_or_404(Exam, pk=pk, created_by=request.user)
    sessions = ExamSession.objects.filter(
        exam=exam, is_submitted=True
    ).select_related('user').order_by('-score')
    return render(request, 'exams/exam_results.html', {'exam': exam, 'sessions': sessions})


@login_required
def exam_join(request):
    if request.method == 'POST':
        form = ExamJoinForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            try:
                exam = Exam.objects.get(code=code, is_active=True)
            except Exam.DoesNotExist:
                messages.error(request, '找不到此考卷代號，請確認後再試。')
                return render(request, 'exams/join.html', {'form': form})

            # Check timing
            now = timezone.now()
            if exam.start_time and now < exam.start_time:
                messages.error(request, f'考卷尚未開放，開始時間：{exam.start_time}')
                return render(request, 'exams/join.html', {'form': form})
            if exam.end_time and now > exam.end_time:
                messages.error(request, '考卷已截止。')
                return render(request, 'exams/join.html', {'form': form})

            return redirect('exams:start', pk=exam.pk)
    else:
        form = ExamJoinForm()
    return render(request, 'exams/join.html', {'form': form})


@login_required
def exam_start(request, pk):
    exam = get_object_or_404(Exam, pk=pk, is_active=True)
    # Check if already submitted
    existing = ExamSession.objects.filter(exam=exam, user=request.user, is_submitted=True).first()
    if existing:
        messages.info(request, '您已完成此考卷。')
        return redirect('exams:session_result', pk=existing.pk)

    # 時間窗檢查：跟 exam_join 保持一致，避免有人繞過「輸入考卷代號」那一步、
    # 直接用考卷 pk 存取 /exams/<pk>/start/，在開放時間之外開始作答。
    # 只擋「還沒開始作答」的情況——已經在作答中的 session 不因為過了 end_time
    # 而被鎖住，避免正在寫的學生卡在交卷前一刻。
    already_in_progress = ExamSession.objects.filter(
        exam=exam, user=request.user, is_submitted=False
    ).exists()
    if not already_in_progress:
        now = timezone.now()
        if exam.start_time and now < exam.start_time:
            messages.error(request, f'考卷尚未開放，開始時間：{exam.start_time}')
            return redirect('exams:list')
        if exam.end_time and now > exam.end_time:
            messages.error(request, '考卷已截止。')
            return redirect('exams:list')

    # Get or create session
    session, created = ExamSession.objects.get_or_create(exam=exam, user=request.user)
    if created:
        # Pre-create blank answers
        for eq in exam.exam_questions.all():
            ExamAnswer.objects.get_or_create(exam_session=session, question=eq.question)

    return redirect('exams:session', pk=session.pk)


@login_required
def exam_session(request, pk):
    session = get_object_or_404(ExamSession, pk=pk, user=request.user)
    if session.is_submitted:
        return redirect('exams:session_result', pk=pk)

    exam = session.exam
    exam_questions = exam.exam_questions.select_related('question').all()
    answers = {a.question_id: a for a in session.answers.all()}
    time_remaining = None
    if exam.time_limit:
        elapsed = (timezone.now() - session.started_at).total_seconds()
        time_remaining = max(0, exam.time_limit * 60 - int(elapsed))

    template = 'exams/session_official.html' if exam.official_ui else 'exams/session.html'
    return render(request, template, {
        'session': session,
        'exam': exam,
        'exam_questions': exam_questions,
        'answers': answers,
        'time_remaining': time_remaining,
    })


@login_required
def exam_begin_timer(request, pk):
    """official_ui 專用：學生按下「開始檢測並開始計時」後才重設計時起點，
    不讓填寫登入／注意事項畫面的時間被算進考試時間。"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    session = get_object_or_404(ExamSession, pk=pk, user=request.user)
    if session.is_submitted:
        return JsonResponse({'error': '已交卷'}, status=400)
    session.started_at = timezone.now()
    session.save(update_fields=['started_at'])
    exam = session.exam
    time_remaining = exam.time_limit * 60 if exam.time_limit else 1800
    return JsonResponse({'time_remaining': time_remaining})


@login_required
def record_cheat(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    session = get_object_or_404(ExamSession, pk=pk, user=request.user)
    if session.is_submitted:
        return JsonResponse({'error': '已交卷'}, status=400)
    ExamSession.objects.filter(pk=pk).update(cheat_count=F('cheat_count') + 1)
    session.refresh_from_db()
    return JsonResponse({'status': 'recorded', 'count': session.cheat_count})


# selected_answer/confidence 欄位在 DB 只有 1 / 10 個字元長，這裡先擋掉不合法的值，
# 避免未經驗證的 POST 資料直接寫進 model 造成 PostgreSQL DataError（未攔截的 500）。
_VALID_ANSWERS = {'', *dict(Question.ANSWER_CHOICES).keys()}
_VALID_CONFIDENCE = {'', 'sure', 'unsure', 'guess'}


@login_required
def exam_save_answer(request, pk):
    if request.method == 'POST':
        session = get_object_or_404(ExamSession, pk=pk, user=request.user)
        if session.is_submitted:
            return JsonResponse({'error': '已交卷'}, status=400)
        question_id = request.POST.get('question_id')
        selected = request.POST.get('answer', '')
        confidence = request.POST.get('confidence', '')
        if selected not in _VALID_ANSWERS:
            return JsonResponse({'error': '答案格式不正確'}, status=400)
        if confidence not in _VALID_CONFIDENCE:
            confidence = ''
        try:
            answer = ExamAnswer.objects.get(exam_session=session, question_id=question_id)
            answer.selected_answer = selected
            answer.confidence = confidence
            answer.save()
            return JsonResponse({'status': 'saved'})
        except ExamAnswer.DoesNotExist:
            return JsonResponse({'error': '題目不存在'}, status=404)
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
def exam_submit(request, pk):
    if request.method == 'POST':
        session = get_object_or_404(ExamSession, pk=pk, user=request.user)
        if session.is_submitted:
            return redirect('exams:session_result', pk=pk)

        # Grade answers
        total_score = 0
        for eq in session.exam.exam_questions.all():
            try:
                answer = ExamAnswer.objects.get(exam_session=session, question=eq.question)
                answer.is_correct = (answer.selected_answer == eq.question.correct_answer)
                if answer.is_correct:
                    total_score += eq.score
                answer.save()
            except ExamAnswer.DoesNotExist:
                pass

        session.score = total_score
        session.is_submitted = True
        session.submitted_at = timezone.now()
        session.save()
        messages.success(request, f'交卷成功！您的分數：{total_score} 分')
        return redirect('exams:session_result', pk=pk)
    return redirect('exams:session', pk=pk)


@login_required
def exam_session_result(request, pk):
    session = get_object_or_404(ExamSession, pk=pk, user=request.user)
    if not session.is_submitted:
        return redirect('exams:session', pk=pk)

    answers = session.answers.select_related('question').all()
    exam_questions = {eq.question_id: eq for eq in session.exam.exam_questions.all()}

    return render(request, 'exams/submit_result.html', {
        'session': session,
        'answers': answers,
        'exam_questions': exam_questions,
    })


@teacher_required
def export_results_csv(request, pk):
    exam = get_object_or_404(Exam, pk=pk, created_by=request.user)
    sessions = ExamSession.objects.filter(
        exam=exam, is_submitted=True
    ).select_related('user').order_by('-score')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="exam_{exam.code}_results.csv"'

    writer = csv.writer(response)
    headers = ['使用者名稱', '姓名', '分數', '滿分', '百分比', '交卷時間']
    if exam.anti_cheat:
        headers.append('切換視窗次數')
    writer.writerow(headers)
    total = exam.total_score()
    for s in sessions:
        pct = round(s.score / total * 100, 1) if total else 0
        # 帳號、姓名是使用者自己填的，未經處理直接寫進 CSV 會有公式注入風險
        # （例如姓名設成 =HYPERLINK(...)），用 csv_safe() 中和開頭的 =/+/-/@。
        row = [
            csv_safe(s.user.username),
            csv_safe(s.user.get_full_name() or s.user.username),
            s.score,
            total,
            f'{pct}%',
            s.submitted_at.strftime('%Y-%m-%d %H:%M') if s.submitted_at else '',
        ]
        if exam.anti_cheat:
            row.append(s.cheat_count)
        writer.writerow(row)
    return response
