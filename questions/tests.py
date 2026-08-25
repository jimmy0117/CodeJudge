from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from exams.models import Exam, ExamQuestion, ExamSession
from .models import Question


def make_user(username, role='student', password='x'):
    user = User.objects.create_user(username=username, password=password)
    user.profile.role = role
    user.profile.save()
    return user


def make_question(title='q'):
    return Question.objects.create(
        title=title, content='q',
        option_a='a', option_b='b', option_c='c', option_d='d',
        correct_answer='A',
    )


class QuestionListLoginRequiredTests(TestCase):
    """回歸測試：題目列表要求登入，跟題目詳情頁行為一致。

    對應修復：questions/views.py::question_list 原本缺少 @login_required，
    導致沒登入的訪客也能瀏覽整個題庫列表。
    """

    def setUp(self):
        self.question = Question.objects.create(
            title='q', content='q',
            option_a='a', option_b='b', option_c='c', option_d='d',
            correct_answer='A',
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('questions:list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_anonymous_user_cannot_view_detail_either(self):
        response = self.client.get(
            reverse('questions:detail', kwargs={'pk': self.question.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_logged_in_user_can_view_list(self):
        user = User.objects.create_user(username='qlist_user', password='x')
        self.client.force_login(user)
        response = self.client.get(reverse('questions:list'))
        self.assertEqual(response.status_code, 200)


class CategoryListLoginRequiredTests(TestCase):
    """回歸測試：分類列表跟題目列表一樣要求登入。"""

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('questions:category_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_logged_in_user_can_view_list(self):
        user = User.objects.create_user(username='catlist_user', password='x')
        self.client.force_login(user)
        response = self.client.get(reverse('questions:category_list'))
        self.assertEqual(response.status_code, 200)


class QuestionDeleteTests(TestCase):
    """回歸測試：題目如果已經被用在已交卷的考卷裡，刪除要變成軟刪除。

    對應修復：ExamAnswer.question 是 on_delete=CASCADE，題目硬刪除會連帶
    刪掉已經改完分的考卷作答明細，但 ExamSession.score 不會跟著變，
    造成分數跟明細對不起來且無法復原。
    """

    def setUp(self):
        self.teacher = make_user('qdel_teacher', role='teacher')
        self.client.force_login(self.teacher)

    def test_deleting_unused_question_hard_deletes(self):
        question = make_question('沒被用過的題目')
        self.client.post(reverse('questions:delete', kwargs={'pk': question.pk}))
        self.assertFalse(Question.objects.filter(pk=question.pk).exists())

    def test_deleting_question_in_draft_exam_still_hard_deletes(self):
        # 只是被加進考卷、但還沒有人交卷 —— 沒有歷史成績要保護，可以真的刪除
        question = make_question('只在草稿考卷裡的題目')
        exam = Exam.objects.create(title='草稿考卷', created_by=self.teacher)
        ExamQuestion.objects.create(exam=exam, question=question, order=1, score=10)

        self.client.post(reverse('questions:delete', kwargs={'pk': question.pk}))
        self.assertFalse(Question.objects.filter(pk=question.pk).exists())

    def test_deleting_question_used_in_graded_exam_soft_deletes_instead(self):
        question = make_question('已經有人交卷的考卷用的題目')
        student = make_user('qdel_student', role='student')
        exam = Exam.objects.create(title='已交卷考卷', created_by=self.teacher)
        ExamQuestion.objects.create(exam=exam, question=question, order=1, score=10)
        ExamSession.objects.create(
            exam=exam, user=student, is_submitted=True, score=10,
            submitted_at=timezone.now(),
        )

        response = self.client.post(
            reverse('questions:delete', kwargs={'pk': question.pk}), follow=True
        )
        self.assertEqual(response.status_code, 200)

        # 題目還在，只是被停用；已交卷考卷的作答明細完全沒被動到
        question.refresh_from_db()
        self.assertFalse(question.is_active)
        self.assertEqual(ExamQuestion.objects.filter(question=question).count(), 1)
        self.assertEqual(
            ExamSession.objects.get(exam=exam, user=student).score, 10
        )
