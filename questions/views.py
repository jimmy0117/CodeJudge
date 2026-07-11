import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
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


@teacher_required
def question_import(request):
    """CSV 批量匯入題目。"""
    context = {}

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, '請選擇 CSV 檔案。')
            return render(request, 'questions/import.html', context)

        if not csv_file.name.endswith('.csv'):
            messages.error(request, '請上傳 .csv 格式的檔案。')
            return render(request, 'questions/import.html', context)

        # 嘗試多種編碼（支援 Excel 輸出的 Big5 / UTF-8 BOM）
        raw = csv_file.read()
        content = None
        for encoding in ('utf-8-sig', 'utf-8', 'big5', 'cp950'):
            try:
                content = raw.decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if content is None:
            messages.error(request, '無法解析檔案編碼，請將 CSV 儲存為 UTF-8 格式。')
            return render(request, 'questions/import.html', context)

        reader = csv.DictReader(io.StringIO(content))

        # 驗證必要欄位
        REQUIRED = {'title', 'content', 'option_a', 'option_b',
                    'option_c', 'option_d', 'correct_answer'}
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED - fieldnames
        if missing:
            messages.error(request, f'CSV 缺少必要欄位：{", ".join(sorted(missing))}')
            return render(request, 'questions/import.html', context)

        success_rows, error_rows = [], []

        for row_num, row in enumerate(reader, start=2):
            try:
                # ── 必填欄位 ──────────────────────────────────────────────
                for col in REQUIRED:
                    if not row.get(col, '').strip():
                        raise ValueError(f'欄位「{col}」不能為空')

                correct_answer = row['correct_answer'].strip().upper()
                if correct_answer not in ('A', 'B', 'C', 'D', 'E'):
                    raise ValueError(
                        f'correct_answer 必須是 A/B/C/D/E，目前為「{correct_answer}」'
                    )

                # ── 選填欄位 ──────────────────────────────────────────────
                difficulty = row.get('difficulty', '').strip().lower()
                if difficulty not in ('easy', 'medium', 'hard'):
                    difficulty = 'medium'

                year = None
                raw_year = row.get('year', '').strip()
                if raw_year:
                    try:
                        year = int(raw_year)
                    except ValueError:
                        raise ValueError(f'year 必須是整數，目前為「{raw_year}」')

                # Category：不存在則自動建立
                category = None
                cat_name = row.get('category', '').strip()
                if cat_name:
                    category, _ = Category.objects.get_or_create(name=cat_name)

                is_active_str = row.get('is_active', 'True').strip().lower()
                is_active = is_active_str not in ('false', '0', 'no', '否', 'f')

                # ── 建立題目 ──────────────────────────────────────────────
                question = Question.objects.create(
                    title=row['title'].strip(),
                    content=row['content'].strip(),
                    option_a=row['option_a'].strip(),
                    option_b=row['option_b'].strip(),
                    option_c=row['option_c'].strip(),
                    option_d=row['option_d'].strip(),
                    option_e=row.get('option_e', '').strip(),
                    correct_answer=correct_answer,
                    category=category,
                    difficulty=difficulty,
                    year=year,
                    hint=row.get('hint', '').strip(),
                    solution_idea=row.get('solution_idea', '').strip(),
                    explanation=row.get('explanation', '').strip(),
                    is_active=is_active,
                )

                # Tags：逗號分隔，不存在則自動建立
                tags_str = row.get('tags', '').strip()
                if tags_str:
                    for tag_name in tags_str.split(','):
                        tag_name = tag_name.strip()
                        if tag_name:
                            tag, _ = Tag.objects.get_or_create(name=tag_name)
                            question.tags.add(tag)

                success_rows.append({'row': row_num, 'title': question.title})

            except Exception as exc:
                error_rows.append({
                    'row': row_num,
                    'title': (row.get('title', '') or '')[:60],
                    'error': str(exc),
                })

        context.update({
            'done': True,
            'success_rows': success_rows,
            'error_rows': error_rows,
            'success_count': len(success_rows),
            'error_count': len(error_rows),
        })

        if success_rows:
            messages.success(request, f'成功匯入 {len(success_rows)} 題。')
        if error_rows:
            messages.warning(request, f'{len(error_rows)} 筆因格式錯誤略過，詳見下方錯誤清單。')

    return render(request, 'questions/import.html', context)


def download_sample_csv(request):
    """下載範例 CSV（UTF-8 BOM，Excel 可直接開啟）。"""
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="questions_sample.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'title', 'content',
        'option_a', 'option_b', 'option_c', 'option_d', 'option_e',
        'correct_answer', 'category', 'difficulty', 'year',
        'hint', 'solution_idea', 'explanation', 'tags', 'is_active',
    ])
    writer.writerow([
        '以下哪個是 Python 的迴圈語法？',
        '在 Python 中，哪個關鍵字用於建立計次迴圈？',
        'for', 'loop', 'repeat', 'iterate', '',
        'A', '基礎語法', 'easy', '2023',
        '想想 Python 的基本控制流程關鍵字。',
        '回想學過的迴圈寫法。',
        'Python 以 for 和 while 作為迴圈，for 最常用於計次迴圈。',
        'Python,迴圈,基礎', 'True',
    ])
    writer.writerow([
        '下列哪段程式碼的時間複雜度為 O(n²)？',
        'int s=0;\nfor(int i=0;i<n;i++)\n  for(int j=0;j<n;j++)\n    s++;',
        'O(n)',
        'O(n²)',
        'O(log n)',
        'O(1)',
        '以上皆非',
        'B', '時間複雜度', 'hard', '2022',
        '計算迴圈執行次數。',
        '最外層迴圈執行 n 次，內層也執行 n 次。',
        '兩層嵌套迴圈各執行 n 次，總共 n×n = n² 次，時間複雜度為 O(n²)。',
        '時間複雜度,演算法', 'True',
    ])
    return response


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
