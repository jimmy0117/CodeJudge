from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from .models import ClassRoom, ClassEnrollment, ClassExamAssignment
from .forms import ClassRoomForm, ClassJoinForm, AssignExamForm
from exams.models import ExamSession


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


@login_required
def class_join(request):
    if request.method == 'POST':
        form = ClassJoinForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['class_code']
            try:
                classroom = ClassRoom.objects.get(class_code=code, is_active=True, allow_join=True)
            except ClassRoom.DoesNotExist:
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
def class_students(request, pk):
    classroom = get_object_or_404(ClassRoom, pk=pk, created_by=request.user)
    enrollments = classroom.enrollments.filter(is_active=True).select_related('user')
    return render(request, 'classes/students.html', {
        'classroom': classroom,
        'enrollments': enrollments,
    })


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
    enrollments = classroom.enrollments.filter(is_active=True).select_related('user')
    assignments = classroom.exam_assignments.select_related('exam').all()

    results = []
    for enrollment in enrollments:
        user_results = []
        for assignment in assignments:
            session = ExamSession.objects.filter(
                exam=assignment.exam,
                user=enrollment.user,
                is_submitted=True
            ).first()
            user_results.append({
                'exam': assignment.exam,
                'session': session,
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
