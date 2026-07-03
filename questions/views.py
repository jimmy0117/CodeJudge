from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Question, Category, Tag
from .forms import QuestionForm, CategoryForm, QuestionFilterForm


def teacher_required(view_func):
    """Decorator: requires teacher or admin role."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.is_teacher_or_admin():
            messages.error(request, '此功能僅限教師或管理員使用。')
            return redirect('questions:list')
        return view_func(request, *args, **kwargs)
    return wrapper


def question_list(request):
    questions = Question.objects.filter(is_active=True).select_related('category')
    form = QuestionFilterForm(request.GET)

    if form.is_valid():
        if form.cleaned_data.get('category'):
            questions = questions.filter(category=form.cleaned_data['category'])
        if form.cleaned_data.get('difficulty'):
            questions = questions.filter(difficulty=form.cleaned_data['difficulty'])
        if form.cleaned_data.get('year'):
            questions = questions.filter(year=form.cleaned_data['year'])
        if form.cleaned_data.get('keyword'):
            kw = form.cleaned_data['keyword']
            questions = questions.filter(
                Q(title__icontains=kw) | Q(content__icontains=kw)
            )

    paginator = Paginator(questions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all()
    return render(request, 'questions/list.html', {
        'page_obj': page_obj,
        'form': form,
        'categories': categories,
    })


@login_required
def question_detail(request, pk):
    question = get_object_or_404(Question, pk=pk, is_active=True)
    is_privileged = hasattr(request.user, 'profile') and request.user.profile.is_teacher_or_admin()
    return render(request, 'questions/detail.html', {
        'question': question,
        'is_privileged': is_privileged,
    })


@teacher_required
def question_create(request):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save()
            messages.success(request, f'題目「{question.title}」已成功建立。')
            return redirect('questions:detail', pk=question.pk)
    else:
        form = QuestionForm()
    return render(request, 'questions/create.html', {'form': form, 'action': '新增'})


@teacher_required
def question_edit(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, '題目已成功更新。')
            return redirect('questions:detail', pk=question.pk)
    else:
        form = QuestionForm(instance=question)
    return render(request, 'questions/create.html', {
        'form': form,
        'question': question,
        'action': '編輯'
    })


@teacher_required
def question_delete(request, pk):
    question = get_object_or_404(Question, pk=pk)
    if request.method == 'POST':
        title = question.title
        question.is_active = False
        question.save()
        messages.success(request, f'題目「{title}」已停用。')
        return redirect('questions:list')
    return render(request, 'questions/confirm_delete.html', {'question': question})


def category_list(request):
    categories = Category.objects.all()
    return render(request, 'questions/category_list.html', {'categories': categories})


@teacher_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f'分類「{cat.name}」已建立。')
            return redirect('questions:category_list')
    else:
        form = CategoryForm()
    return render(request, 'questions/category_form.html', {'form': form, 'action': '新增'})


@teacher_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, '分類已更新。')
            return redirect('questions:category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'questions/category_form.html', {
        'form': form,
        'category': category,
        'action': '編輯'
    })


@teacher_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'分類「{name}」已刪除。')
        return redirect('questions:category_list')
    return render(request, 'questions/category_confirm_delete.html', {'category': category})
