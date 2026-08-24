import csv
import secrets
import string

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponse
from .models import ClassRoom, ClassEnrollment, ClassExamAssignment
from .forms import ClassRoomForm, ClassJoinForm, AssignExamForm, BatchCreateStudentsForm
from exams.models import ExamSession
from config.csv_utils import csv_safe


def teacher_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.is_teacher_or_admin():
            messages.error(request, '此功能僅限教師或管理員使用。')
            return redirect('classes:list')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
def class_list(request):
    is_privileged = hasattr(request.user, 'profile') and request.user.profile.is_teacher_or_admin()
    if is_privileged:
        my_classes = ClassRoom.objects.filter(created_by=request.user, is_active=True)
    else:
        enrolled_ids = ClassEnrollment.objects.filter(
            user=request.user, is_active=True
        ).values_list('class_room_id', flat=True)
        my_classes = ClassRoom.objects.filter(id__in=enrolled_ids, is_active=True)
    return render(request, 'classes/list.html', {
        'classes': my_classes,
        'is_privileged': is_privileged
    })


@teacher_required
def class_create(request):
    if request.method == 'POST':
        form = ClassRoomForm(request.POST)
        if form.is_valid():
            classroom = form.save(commit=False)
            classroom.created_by = request.user
            classroom.save()
            messages.success(request, f'班級「{classroom.name}」已建立，代號：{classroom.class_code}')
            return redirect('classes:detail', pk=classroom.pk)
    else:
        form = ClassRoomForm()
    return render(request, 'classes/create.html', {'form': form})


@login_required
def class_detail(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk, is_active=True)
    is_owner = classroom.created_by == request.user
    is_enrolled = ClassEnrollment.objects.filter(
        class_room=classroom, user=request.user, is_active=True
    ).exists()

    if not is_owner and not is_enrolled:
        messages.error(request, '您沒有權限查看此班級。')
        return redirect('classes:list')

    assignments = classroom.exam_assignments.select_related('exam').order_by('-created_at')
    return render(request, 'classes/detail.html', {
        'classroom': classroom,
        'assignments': assignments,
        'is_owner': is_owner,
        'is_enrolled': is_enrolled,
    })


# class_code 只有 'CLASS' + 兩位數字，全站固定只有 100 種組合，寫個小腳本
# 幾秒鐘就能把 00～99 全部試過一輪。這裡對「猜錯代號」做簡單節流：同一個
# 使用者短時間內猜錯太多次就先擋一陣子，增加暴力枚舉的成本。
# 注意：這是用 Django 預設的 local-memory cache 做的陽春節流，多台/多 process
# 部署時每個 process 各自計數不會共用，只能當作基本防護，不是完整解法。
_JOIN_RATE_LIMIT_MAX_ATTEMPTS = 10
_JOIN_RATE_LIMIT_WINDOW_SECONDS = 300


def _class_join_rate_limit_key(user_id):
    return f'class_join_fail_count_{user_id}'


@login_required
def class_join(request):
    if request.method == 'POST':
        rate_limit_key = _class_join_rate_limit_key(request.user.pk)
        fail_count = cache.get(rate_limit_key, 0)
        if fail_count >= _JOIN_RATE_LIMIT_MAX_ATTEMPTS:
            messages.error(request, '嘗試次數過多，請稍後再試（約 5 分鐘後可再試）。')
            return render(request, 'classes/join.html', {'form': ClassJoinForm()})

        form = ClassJoinForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['class_code']
            try:
                classroom = ClassRoom.objects.get(class_code=code, is_active=True, allow_join=True)
            except ClassRoom.DoesNotExist:
                cache.set(rate_limit_key, fail_count + 1, _JOIN_RATE_LIMIT_WINDOW_SECONDS)
                messages.error(request, '找不到此班級代號，或班級目前不開放加入。')
                return render(request, 'classes/join.html', {'form': form})

            enrollment, created = ClassEnrollment.objects.get_or_create(
                class_room=classroom, user=request.user,
                defaults={'is_active': True}
            )
            if not created:
                if enrollment.is_active:
                    messages.info(request, f'您已在班級「{classroom.name}」中。')
                else:
                    enrollment.is_active = True
                    enrollment.save()
                    messages.success(request, f'您已重新加入班級「{classroom.name}」。')
            else:
                messages.success(request, f'您已成功加入班級「{classroom.name}」！')
            return redirect('classes:detail', pk=classroom.pk)
    else:
        form = ClassJoinForm()
    return render(request, 'classes/join.html', {'form': form})


@login_required
def class_leave(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk)
    enrollment = get_object_or_404(ClassEnrollment, class_room=classroom, user=request.user)
    if request.method == 'POST':
        enrollment.is_active = False
        enrollment.save()
        messages.success(request, f'您已退出班級「{classroom.name}」。')
        return redirect('classes:list')
    return render(request, 'classes/confirm_leave.html', {'classroom': classroom})


@teacher_required
def class_delete(request, pk):
    """刪除班級（僅限建立者）。連同班級成員、考卷指派紀錄一併刪除（models.py 設定 CASCADE）。

    順帶效果：刪除後 class_code 會空出來，之後 generate_class_code() 才能重新配到
    這個代號——目前代號空間只有 'CLASS' + 兩位數字共 100 組，讓教師能清掉不用的
    班級，是緩解代號用完問題的實際作法。
    """
    classroom = get_object_or_404(ClassRoom, pk=pk, created_by=request.user)
    if request.method == 'POST':
        name = classroom.name
        classroom.delete()
        messages.success(request, f'班級「{name}」已刪除。')
        return redirect('classes:list')
    return render(request, 'classes/confirm_delete.html', {'classroom': classroom})


@teacher_required
def class_students(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk, created_by=request.user)
    enrollments = classroom.enrollments.filter(is_active=True).select_related('user')
    return render(request, 'classes/students.html', {
        'classroom': classroom,
        'enrollments': enrollments,
    })


def _generate_temp_password():
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(10))


@teacher_required
def class_batch_create_students(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = BatchCreateStudentsForm(request.POST)
        if form.is_valid():
            username_validator = UnicodeUsernameValidator()
            lines = [
                line.strip() for line in form.cleaned_data['students'].splitlines()
                if line.strip()
            ]
            results = []
            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                username = parts[0]
                full_name = parts[1] if len(parts) > 1 else ''
                if not username:
                    continue

                try:
                    username_validator(username)
                except ValidationError as e:
                    results.append({
                        'username': username, 'name': full_name, 'password': '',
                        'status': 'invalid', 'note': '；'.join(e.messages),
                    })
                    continue

                existing = User.objects.filter(username=username).first()
                if existing:
                    # 帳號已存在：只加入班級，絕不覆蓋既有密碼或角色
                    enrollment, created = ClassEnrollment.objects.get_or_create(
                        class_room=classroom, user=existing, defaults={'is_active': True}
                    )
                    if not created and not enrollment.is_active:
                        enrollment.is_active = True
                        enrollment.save()
                    results.append({
                        'username': username, 'name': full_name, 'password': '',
                        'status': 'existing', 'note': '帳號已存在，已加入班級（密碼未變更）',
                    })
                    continue

                temp_password = _generate_temp_password()
                user = User(username=username)
                if full_name:
                    user.first_name = full_name
                user.set_password(temp_password)
                user.save()
                # UserProfile 由 accounts.models.create_user_profile signal 自動建立，
                # 一律預設為 student（不接受指定 teacher/admin，避免權限提升）。
                ClassEnrollment.objects.create(class_room=classroom, user=user, is_active=True)
                results.append({
                    'username': username, 'name': full_name, 'password': temp_password,
                    'status': 'created', 'note': '已建立新帳號並加入班級',
                })

            request.session[f'batch_credentials_{classroom.pk}'] = results
            created_count = sum(1 for r in results if r['status'] == 'created')
            existing_count = sum(1 for r in results if r['status'] == 'existing')
            invalid_count = sum(1 for r in results if r['status'] == 'invalid')
            summary = f'處理完成：新建立 {created_count} 個帳號、加入既有帳號 {existing_count} 個'
            if invalid_count:
                summary += f'、{invalid_count} 筆使用者名稱格式錯誤已略過'
            messages.success(request, summary + '。')
            return redirect('classes:batch_create_students_result', pk=classroom.pk)
    else:
        form = BatchCreateStudentsForm()
    return render(request, 'classes/batch_create_students.html', {
        'classroom': classroom,
        'form': form,
    })


@teacher_required
def class_batch_create_students_result(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk, created_by=request.user)
    results = request.session.get(f'batch_credentials_{classroom.pk}')
    if not results:
        messages.info(request, '沒有可顯示的批次建立結果，請重新操作一次。')
        return redirect('classes:batch_create_students', pk=classroom.pk)
    return render(request, 'classes/batch_create_students_result.html', {
        'classroom': classroom,
        'results': results,
    })


@teacher_required
def class_batch_create_students_csv(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk, created_by=request.user)
    results = request.session.get(f'batch_credentials_{classroom.pk}')
    if not results:
        messages.info(request, '沒有可匯出的批次建立結果，請重新操作一次。')
        return redirect('classes:batch_create_students', pk=classroom.pk)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{classroom.class_code}_students.csv"'
    response.write('﻿')  # BOM，讓 Excel 開啟時中文不會亂碼
    writer = csv.writer(response)
    writer.writerow(['使用者名稱', '姓名', '密碼', '狀態', '備註'])
    status_label = {'created': '新建立', 'existing': '已存在', 'invalid': '格式錯誤'}
    for r in results:
        # username/name 可能來自既有帳號（其他使用者自己設定的），未經處理直接
        # 寫進 CSV 會有公式注入風險，用 csv_safe() 中和開頭的 =/+/-/@。
        # 密碼是系統隨機產生（只有英數字），不會觸發，不需要處理。
        writer.writerow([
            csv_safe(r['username']), csv_safe(r['name']), r['password'],
            status_label.get(r['status'], r['status']), r['note'],
        ])
    return response


@teacher_required
def class_assign_exam(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = AssignExamForm(request.POST, user=request.user)
        if form.is_valid():
            assignment, created = ClassExamAssignment.objects.get_or_create(
                class_room=classroom,
                exam=form.cleaned_data['exam'],
                defaults={
                    'assigned_by': request.user,
                    'start_time': form.cleaned_data.get('start_time'),
                    'end_time': form.cleaned_data.get('end_time'),
                    'is_required': form.cleaned_data.get('is_required', True),
                }
            )
            if created:
                messages.success(request, f'考卷已指派給班級「{classroom.name}」。')
            else:
                messages.info(request, '此考卷已指派給此班級。')
            return redirect('classes:detail', pk=pk)
    else:
        form = AssignExamForm(user=request.user)
    return render(request, 'classes/assign_exam.html', {
        'classroom': classroom,
        'form': form,
    })


@teacher_required
def class_results(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk, created_by=request.user)
    # 注意：assignments 維持 QuerySet（不轉成 list），因為樣板用了
    # {{ assignments.count }}；QuerySet 完整迭代過一次後結果會被快取，
    # 下面重複用來組 id 清單、再迭代組結果，不會變成兩次查詢。
    enrollments = classroom.enrollments.filter(is_active=True).select_related('user')
    assignments = classroom.exam_assignments.select_related('exam').all()

    # 原本這裡是「每位學生 x 每份指派考卷」各查一次 ExamSession，
    # O(學生數 x 考卷數) 次查詢；改成一次查完全部相關 session，
    # 用 (exam_id, user_id) 當 key 在記憶體裡組合，固定只查 1 次。
    exam_ids = [a.exam_id for a in assignments]
    sessions = ExamSession.objects.filter(
        exam_id__in=exam_ids,
        user__in=[e.user_id for e in enrollments],
        is_submitted=True,
    )
    session_map = {(s.exam_id, s.user_id): s for s in sessions}

    results = []
    for enrollment in enrollments:
        user_results = []
        for assignment in assignments:
            user_results.append({
                'exam': assignment.exam,
                'session': session_map.get((assignment.exam_id, enrollment.user_id)),
            })
        results.append({
            'user': enrollment.user,
            'results': user_results,
        })

    return render(request, 'classes/results.html', {
        'classroom': classroom,
        'assignments': assignments,
        'results': results,
    })
