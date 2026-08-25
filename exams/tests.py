from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from questions.models import Question
from .models import Exam, ExamQuestion, ExamSession, ExamAnswer


def make_question(correct_answer='A'):
    return Question.objects.create(
        title='測試題目',
        content='1 + 1 = ?',
        option_a='2', option_b='3', option_c='4', option_d='5',
        correct_answer=correct_answer,
    )


def make_user(username, role='student', password='x'):
    user = User.objects.create_user(username=username, password=password)
    user.profile.role = role
    user.profile.save()
    return user


class ExamAutoGradingTests(TestCase):
    """考卷自動批改邏輯（exams/views.py::exam_submit）。"""

    def setUp(self):
        self.teacher = User.objects.create_user(username='grader_teacher', password='x')
        self.teacher.profile.role = 'teacher'
        self.teacher.profile.save()
        self.student = User.objects.create_user(username='grader_student', password='x')

        self.exam = Exam.objects.create(title='小考', created_by=self.teacher)
        self.q1 = make_question(correct_answer='A')
        self.q2 = make_question(correct_answer='B')
        self.q3 = make_question(correct_answer='C')
        ExamQuestion.objects.create(exam=self.exam, question=self.q1, order=1, score=10)
        ExamQuestion.objects.create(exam=self.exam, question=self.q2, order=2, score=20)
        ExamQuestion.objects.create(exam=self.exam, question=self.q3, order=3, score=30)

        self.session = ExamSession.objects.create(exam=self.exam, user=self.student)
        self.client.force_login(self.student)

    def _submit(self):
        return self.client.post(
            reverse('exams:submit', kwargs={'pk': self.session.pk}), follow=True
        )

    def test_save_answer_rejects_oversized_value_instead_of_crashing(self):
        """回歸測試：exam_save_answer 對超長 answer 要回傳錯誤，不能讓 DB 500。"""
        ExamAnswer.objects.create(exam_session=self.session, question=self.q1)
        response = self.client.post(
            reverse('exams:save_answer', kwargs={'pk': self.session.pk}),
            {'question_id': self.q1.pk, 'answer': 'AAAAAAAAAAAAAAAA', 'confidence': ''},
        )
        self.assertEqual(response.status_code, 400)
        answer = ExamAnswer.objects.get(exam_session=self.session, question=self.q1)
        self.assertEqual(answer.selected_answer, '')  # 沒有被寫入不合法的值

    def test_save_answer_accepts_valid_letter(self):
        ExamAnswer.objects.create(exam_session=self.session, question=self.q1)
        response = self.client.post(
            reverse('exams:save_answer', kwargs={'pk': self.session.pk}),
            {'question_id': self.q1.pk, 'answer': 'A', 'confidence': 'sure'},
        )
        self.assertEqual(response.status_code, 200)
        answer = ExamAnswer.objects.get(exam_session=self.session, question=self.q1)
        self.assertEqual(answer.selected_answer, 'A')
        self.assertEqual(answer.confidence, 'sure')

    def test_save_answer_ignores_invalid_confidence(self):
        ExamAnswer.objects.create(exam_session=self.session, question=self.q1)
        response = self.client.post(
            reverse('exams:save_answer', kwargs={'pk': self.session.pk}),
            {'question_id': self.q1.pk, 'answer': 'A', 'confidence': 'x' * 50},
        )
        self.assertEqual(response.status_code, 200)
        answer = ExamAnswer.objects.get(exam_session=self.session, question=self.q1)
        self.assertEqual(answer.confidence, '')

    def test_correct_answers_are_scored_and_marked_correct(self):
        ExamAnswer.objects.create(exam_session=self.session, question=self.q1, selected_answer='A')
        ExamAnswer.objects.create(exam_session=self.session, question=self.q2, selected_answer='X')  # 答錯
        # q3 完全沒作答

        self._submit()

        self.session.refresh_from_db()
        self.assertTrue(self.session.is_submitted)
        self.assertEqual(self.session.score, 10)  # 只有 q1 答對得分

        answer1 = ExamAnswer.objects.get(exam_session=self.session, question=self.q1)
        answer2 = ExamAnswer.objects.get(exam_session=self.session, question=self.q2)
        self.assertTrue(answer1.is_correct)
        self.assertFalse(answer2.is_correct)

    def test_all_correct_scores_full_marks(self):
        ExamAnswer.objects.create(exam_session=self.session, question=self.q1, selected_answer='A')
        ExamAnswer.objects.create(exam_session=self.session, question=self.q2, selected_answer='B')
        ExamAnswer.objects.create(exam_session=self.session, question=self.q3, selected_answer='C')

        self._submit()

        self.session.refresh_from_db()
        self.assertEqual(self.session.score, self.exam.total_score())
        self.assertEqual(self.session.score, 60)

    def test_no_answers_scores_zero(self):
        self._submit()
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_submitted)
        self.assertEqual(self.session.score, 0)

    def test_resubmitting_does_not_regrade(self):
        ExamAnswer.objects.create(exam_session=self.session, question=self.q1, selected_answer='A')
        self._submit()
        self.session.refresh_from_db()
        self.assertEqual(self.session.score, 10)

        # 交卷後把答案改掉（模擬重送請求），再次呼叫 submit 不應該重新計分
        answer = ExamAnswer.objects.get(exam_session=self.session, question=self.q1)
        answer.selected_answer = 'B'
        answer.save()

        self._submit()
        self.session.refresh_from_db()
        self.assertEqual(self.session.score, 10)

    def test_cannot_submit_another_users_session(self):
        other_student = User.objects.create_user(username='grader_student2', password='x')
        self.client.force_login(other_student)
        response = self._submit()
        self.assertEqual(response.status_code, 404)


class ExamStartTimeWindowTests(TestCase):
    """回歸測試：exam_start 不能繞過代號流程的時間窗檢查。

    對應修復：exams/views.py::exam_start 原本只檢查 is_active，
    start_time/end_time 只在 exam_join 檢查；只要知道考卷 pk，
    就能在開放時間之外直接開始作答。
    """

    def setUp(self):
        self.teacher = make_user('window_teacher', role='teacher')
        self.student = make_user('window_student', role='student')
        self.client.force_login(self.student)

    def _start(self, exam):
        return self.client.get(reverse('exams:start', kwargs={'pk': exam.pk}), follow=True)

    def test_cannot_start_before_start_time(self):
        exam = Exam.objects.create(
            title='尚未開放', created_by=self.teacher,
            start_time=timezone.now() + timedelta(days=1),
        )
        self._start(exam)
        self.assertFalse(ExamSession.objects.filter(exam=exam, user=self.student).exists())

    def test_cannot_start_after_end_time(self):
        exam = Exam.objects.create(
            title='已截止', created_by=self.teacher,
            end_time=timezone.now() - timedelta(days=1),
        )
        self._start(exam)
        self.assertFalse(ExamSession.objects.filter(exam=exam, user=self.student).exists())

    def test_can_start_within_window(self):
        exam = Exam.objects.create(
            title='開放中', created_by=self.teacher,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
        )
        self._start(exam)
        self.assertTrue(ExamSession.objects.filter(exam=exam, user=self.student).exists())

    def test_in_progress_session_not_locked_out_after_end_time_passes(self):
        exam = Exam.objects.create(
            title='作答中考卷', created_by=self.teacher,
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(minutes=1),  # 已經過了截止時間
        )
        # 模擬學生在截止前就已經開始作答（session 已存在、尚未交卷）
        session = ExamSession.objects.create(exam=exam, user=self.student)

        response = self._start(exam)
        self.assertRedirects(response, reverse('exams:session', kwargs={'pk': session.pk}))


class ExamDetailOwnershipTests(TestCase):
    """回歸測試：exam_detail 要限定 created_by，避免教師互看考卷內容（IDOR）。"""

    def setUp(self):
        self.teacher_a = make_user('owner_teacher', role='teacher')
        self.teacher_b = make_user('other_teacher', role='teacher')
        self.exam = Exam.objects.create(title='教師A的考卷', created_by=self.teacher_a)

    def test_owner_can_view_detail(self):
        self.client.force_login(self.teacher_a)
        response = self.client.get(reverse('exams:detail', kwargs={'pk': self.exam.pk}))
        self.assertEqual(response.status_code, 200)

    def test_other_teacher_cannot_view_detail(self):
        self.client.force_login(self.teacher_b)
        response = self.client.get(reverse('exams:detail', kwargs={'pk': self.exam.pk}))
        self.assertEqual(response.status_code, 404)


class CsvSafeTests(TestCase):
    """config.csv_utils.csv_safe：中和 CSV 公式注入的開頭字元。"""

    def test_neutralizes_formula_trigger_prefixes(self):
        from config.csv_utils import csv_safe
        for payload in ('=1+1', '+1+1', '-1+1', '@SUM(A1)'):
            self.assertTrue(csv_safe(payload).startswith("'"))
            self.assertEqual(csv_safe(payload)[1:], payload)

    def test_leaves_normal_values_untouched(self):
        from config.csv_utils import csv_safe
        self.assertEqual(csv_safe('王小明'), '王小明')
        self.assertEqual(csv_safe('student01'), 'student01')

    def test_handles_none(self):
        from config.csv_utils import csv_safe
        self.assertEqual(csv_safe(None), '')


class ExportResultsCsvInjectionTests(TestCase):
    """回歸測試：匯出成績 CSV 不能讓學生自己填的姓名/帳號變成公式注入。

    對應修復：exams/views.py::export_results_csv 曾經把
    user.username / user.get_full_name() 原封不動寫進 CSV；
    這兩個欄位使用者可以自己填，first_name/last_name 完全沒有字元
    限制，設成 =HYPERLINK(...) 之類的值，老師用 Excel 開啟匯出的
    CSV 時可能被當公式執行。
    """

    def test_malicious_name_is_neutralized_in_export(self):
        teacher = make_user('csv_teacher', role='teacher')
        student = make_user('csv_student', role='student')
        student.first_name = '=1+1+cmd'
        student.last_name = '|calc'
        student.save()

        exam = Exam.objects.create(title='CSV 測試考卷', created_by=teacher)
        q = make_question()
        ExamQuestion.objects.create(exam=exam, question=q, order=1, score=10)
        ExamSession.objects.create(
            exam=exam, user=student, is_submitted=True, score=10,
            submitted_at=timezone.now(),
        )

        self.client.force_login(teacher)
        response = self.client.get(reverse('exams:export_csv', kwargs={'pk': exam.pk}))
        content = response.content.decode('utf-8-sig')

        # 姓名欄位裡的公式字串前面應該被補上單引號中和，不能原封不動出現
        self.assertNotIn(",=1+1+cmd", content)
        self.assertIn(",'=1+1+cmd", content)


class SubmitResultAnswerVisibilityTests(TestCase):
    """回歸測試：交卷結果頁的「正確答案」要尊重 exam.show_explanation。

    對應修復：templates/exams/submit_result.html 曾經不管
    show_score/show_explanation 開關，正確答案一律顯示——老師關掉
    這兩個選項通常是同一份考卷要給不同班級/時段重複用，先交卷的
    學生卻還是能看到正解，等於洩題。
    """

    def setUp(self):
        self.teacher = make_user('reveal_teacher', role='teacher')
        self.student = make_user('reveal_student', role='student')
        self.question = make_question(correct_answer='B')

    def _create_submitted_session(self, exam):
        ExamQuestion.objects.create(exam=exam, question=self.question, order=1, score=10)
        session = ExamSession.objects.create(
            exam=exam, user=self.student, is_submitted=True, score=0,
            submitted_at=timezone.now(),
        )
        ExamAnswer.objects.create(
            exam_session=session, question=self.question, selected_answer='A', is_correct=False
        )
        return session

    def test_correct_answer_hidden_when_show_explanation_off(self):
        exam = Exam.objects.create(
            title='關閉詳解的考卷', created_by=self.teacher, show_explanation=False
        )
        session = self._create_submitted_session(exam)

        self.client.force_login(self.student)
        response = self.client.get(reverse('exams:session_result', kwargs={'pk': session.pk}))
        self.assertNotContains(response, '正確答案')

    def test_correct_answer_shown_when_show_explanation_on(self):
        exam = Exam.objects.create(
            title='開啟詳解的考卷', created_by=self.teacher, show_explanation=True
        )
        session = self._create_submitted_session(exam)

        self.client.force_login(self.student)
        response = self.client.get(reverse('exams:session_result', kwargs={'pk': session.pk}))
        self.assertContains(response, '正確答案')
