import random
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q
from questions.models import Question
from .models import PracticeRecord, WrongQuestion, FavoriteQuestion, QuestionNote
from .forms import PracticeStartForm, NoteForm


def calculate_next_review(wrong_count):
    if wrong_count == 1:
        return timezone.now() + timedelta(days=1)
    elif wrong_count == 2:
        return timezone.now() + timedelta(days=3)
    else:
        return timezone.now() + timedelta(days=7)


@login_required
def practice_start(request):
    if request.method == 'POST':
        form = PracticeStartForm(request.POST)
        if form.is_valid():
            mode = form.cleaned_data['mode']
            category = form.cleaned_data.get('category')
            difficulty = form.cleaned_data.get('difficulty')
            count = form.cleaned_data.get('count', 10)

            questions = Question.objects.filter(is_active=True)

            if mode == 'wrong':
                wrong_ids = WrongQuestion.objects.filter(
                    user=request.user, is_resolved=False
                ).values_list('question_id', flat=True)
                questions = questions.filter(id__in=wrong_ids)
            elif mode == 'favorite':
                fav_ids = FavoriteQuestion.objects.filter(
                    user=request.user
                ).values_list('question_id', flat=True)
                questions = questions.filter(id__in=fav_ids)
            elif mode == 'weakness':
                from django.db.models import Count
                weak_categories = PracticeRecord.objects.filter(
                    user=request.user, is_correct=False
                ).values('question__category').annotate(
                    cnt=Count('id')
                ).order_by('-cnt').values_list('question__category', flat=True)[:3]
                questions = questions.filter(category__in=weak_categories)

            if category:
                questions = questions.filter(category=category)
            if difficulty:
                questions = questions.filter(difficulty=difficulty)

            q_list = list(questions)
            random.shuffle(q_list)
            q_list = q_list[:count]

            if not q_list:
                messages.warning(request, '沒有符合條件的題目，請調整篩選條件。')
                return redirect('practice:start')

            q_ids = [q.id for q in q_list]
            request.session['practice_queue'] = q_ids
            request.session['practice_index'] = 0
            request.session['practice_mode'] = mode
            return redirect('practice:question')
    else:
        form = PracticeStartForm()
    return render(request, 'practice/start.html', {'form': form})


@login_required
def practice_question(request):
    queue = request.session.get('practice_queue', [])
    index = request.session.get('practice_index', 0)

    if not queue or index >= len(queue):
        messages.info(request, '練習完畢！')
        return redirect('practice:start')

    question = get_object_or_404(Question, pk=queue[index])

    if request.method == 'POST':
        selected = request.POST.get('answer', '')
        confidence = request.POST.get('confidence', '')

        if not selected:
            messages.error(request, '請選擇一個答案。')
            return render(request, 'practice/question.html', {
                'question': question,
                'index': index + 1,
                'total': len(queue),
            })

        # selected_answer/confidence 在 DB 只有 1 / 10 個字元長，這裡先擋掉不合法
        # 的值，避免未經驗證的 POST 資料直接寫進 model 造成 DataError（未攔截的 500）。
        valid_answers = dict(Question.ANSWER_CHOICES).keys()
        if selected not in valid_answers:
            messages.error(request, '答案格式不正確，請重新作答。')
            return render(request, 'practice/question.html', {
                'question': question,
                'index': index + 1,
                'total': len(queue),
            })
        if confidence not in ('', 'sure', 'unsure', 'guess'):
            confidence = ''

        is_correct = (selected == question.correct_answer)

        # Save practice record
        PracticeRecord.objects.create(
            user=request.user,
            question=question,
            selected_answer=selected,
            confidence=confidence,
            is_correct=is_correct,
        )

        # Update wrong question tracking
        if not is_correct:
            wrong_q, created = WrongQuestion.objects.get_or_create(
                user=request.user,
                question=question,
                defaults={'wrong_count': 1}
            )
            if not created:
                wrong_q.wrong_count += 1
                wrong_q.is_resolved = False
                wrong_q.review_count = 0
            wrong_q.next_review_at = calculate_next_review(wrong_q.wrong_count)
            wrong_q.save()
        else:
            # If answered correctly, update review count
            try:
                wrong_q = WrongQuestion.objects.get(user=request.user, question=question)
                wrong_q.review_count += 1
                if wrong_q.review_count >= 2:
                    wrong_q.is_resolved = True
                wrong_q.save()
            except WrongQuestion.DoesNotExist:
                pass

        # Check if favorited
        is_favorited = FavoriteQuestion.objects.filter(
            user=request.user, question=question
        ).exists()

        # Get existing note
        note = None
        try:
            note = QuestionNote.objects.get(user=request.user, question=question)
        except QuestionNote.DoesNotExist:
            pass

        return render(request, 'practice/result.html', {
            'question': question,
            'selected': selected,
            'is_correct': is_correct,
            'index': index + 1,
            'total': len(queue),
            'has_next': (index + 1) < len(queue),
            'is_favorited': is_favorited,
            'note': note,
            'note_form': NoteForm(initial={'content': note.content if note else ''}),
        })

    return render(request, 'practice/question.html', {
        'question': question,
        'index': index + 1,
        'total': len(queue),
    })


@login_required
def practice_next(request):
    queue = request.session.get('practice_queue', [])
    index = request.session.get('practice_index', 0)
    request.session['practice_index'] = index + 1
    return redirect('practice:question')


@login_required
def wrong_list(request):
    wrong_questions = WrongQuestion.objects.filter(
        user=request.user, is_resolved=False
    ).select_related('question', 'question__category').order_by('next_review_at')
    now = timezone.now()
    return render(request, 'practice/wrong_list.html', {
        'wrong_questions': wrong_questions,
        'now': now,
    })


@login_required
def favorites(request):
    fav_questions = FavoriteQuestion.objects.filter(
        user=request.user
    ).select_related('question', 'question__category').order_by('-created_at')
    return render(request, 'practice/favorites.html', {'fav_questions': fav_questions})


@login_required
def toggle_favorite(request, pk):
    if request.method == 'POST':
        question = get_object_or_404(Question, pk=pk)
        fav, created = FavoriteQuestion.objects.get_or_create(
            user=request.user, question=question
        )
        if not created:
            fav.delete()
            return JsonResponse({'status': 'removed'})
        return JsonResponse({'status': 'added'})
    return JsonResponse({'error': 'Invalid method'}, status=405)


@login_required
def note_edit(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if request.method == 'POST':
        form = NoteForm(request.POST)
        if form.is_valid():
            content = form.cleaned_data['content']
            note, _ = QuestionNote.objects.update_or_create(
                user=request.user,
                question=question,
                defaults={'content': content}
            )
            messages.success(request, '筆記已儲存。')
            # HTTP_REFERER 是使用者端可任意偽造的 header，直接拿來 redirect
            # 會是開放重新導向（open redirect）：惡意連結可以在存完筆記後
            # 把使用者導去外部網站。這裡驗證 referer 是不是同一個網站，
            # 不是的話一律退回安全的預設頁面。
            referer = request.META.get('HTTP_REFERER', '')
            if referer and url_has_allowed_host_and_scheme(
                referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(referer)
            return redirect('practice:start')
    return redirect('practice:start')


@login_required
def notes_list(request):
    notes = QuestionNote.objects.filter(
        user=request.user
    ).select_related('question').order_by('-updated_at')
    return render(request, 'practice/notes.html', {'notes': notes})
