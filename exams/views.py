import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Q
from .models import Exam, ExamQuestion, ExamSession, ExamAnswer
from .forms import ExamForm, ExamJoinForm
from questions.models import Question, Category


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
    exam = get_object_or_404(Exam, pk=pk)
    exam_questions = exam.exam_questions.select_related('question').all()
    all_questions = Question.objects.filter(is_active=True).select_related('category')
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
        question_id = request.POST.get('question_id')
        score = int(request.POST.get('score', 5))
        question = get_object_or_404(Question, pk=question_id)
        order = exam.exam_questions.count() + 1
        ExamQuestion.objects.get_or_create(
            exam=exam, question=question,
            defaults={'order': order, 'score': score}
        )
        messages.success(request, f'題目已加入考卷。')
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

    return render(request, 'exams/session.html', {
        'session': session,
        'exam': exam,
        'exam_questions': exam_questions,
        'answers': answers,
        'time_remaining': time_remaining,
    })


@login_required
def exam_save_answer(request, pk):
    if request.method == 'POST':
        session = get_object_or_404(ExamSession, pk=pk, user=request.user)
        if session.is_submitted:
            return JsonResponse({'error': '已交卷'}, status=400)
        question_id = request.POST.get('question_id')
        selected = request.POST.get('answer', '')
        confidence = request.POST.get('confidence', '')
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
    writer.writerow(['使用者名稱', '姓名', '分數', '滿分', '百分比', '交卷時間'])
    total = exam.total_score()
    for s in sessions:
        pct = round(s.score / total * 100, 1) if total else 0
        writer.writerow([
            s.user.username,
            s.user.get_full_name() or s.user.username,
            s.score,
            total,
            f'{pct}%',
            s.submitted_at.strftime('%Y-%m-%d %H:%M') if s.submitted_at else '',
        ])
    return response
