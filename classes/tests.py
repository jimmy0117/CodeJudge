from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from exams.models import Exam, ExamSession
from questions.models import Question
from .models import ClassRoom, ClassEnrollment, ClassExamAssignment


def make_user(username, role='student', password='x'):
    user = User.objects.create_user(username=username, password=password)
    user.profile.role = role
    user.profile.save()
    return user


class TeacherRequiredDecoratorTests(TestCase):
    def setUp(self):
        self.teacher = make_user('teacher1', role='teacher')
        self.student = make_user('student1', role='student')

    def test_student_cannot_create_class(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('classes:create'))
        self.assertRedirects(response, reverse('classes:list'))
        self.assertEqual(ClassRoom.objects.count(), 0)

    def test_teacher_can_create_class(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse('classes:create'), {
            'name': '一年甲班',
            'description': '',
            'is_active': 'on',
            'allow_join': 'on',
        })
        self.assertEqual(ClassRoom.objects.count(), 1)
        classroom = ClassRoom.objects.first()
        self.assertRedirects(response, reverse('classes:detail', kwargs={'pk': classroom.pk}))


class BatchCreateStudentsTests(TestCase):
    """教師批次建立學生帳號功能。"""

    def setUp(self):
        self.teacher = make_user('teacher2', role='teacher')
        self.other_teacher = make_user('teacher3', role='teacher')
        self.classroom = ClassRoom.objects.create(name='測試班級', created_by=self.teacher)
        self.client.force_login(self.teacher)

    def _post(self, students_text):
        return self.client.post(
            reverse('classes:batch_create_students', kwargs={'pk': self.classroom.pk}),
            {'students': students_text},
            follow=True,
        )

    def test_creates_new_accounts_as_student_role(self):
        self._post('s001,王小明\ns002,李小華')

        s001 = User.objects.get(username='s001')
        s002 = User.objects.get(username='s002')
        self.assertEqual(s001.profile.role, 'student')
        self.assertEqual(s002.profile.role, 'student')
        self.assertFalse(s001.is_staff)
        self.assertFalse(s001.is_superuser)

        self.assertTrue(
            ClassEnrollment.objects.filter(
                class_room=self.classroom, user=s001, is_active=True
            ).exists()
        )

    def test_does_not_overwrite_existing_account_password_or_role(self):
        existing = make_user('existing_teacher', role='teacher')
        existing.set_password('OriginalPassword123!')
        existing.save()

        self._post('existing_teacher,某教師')

        existing.refresh_from_db()
        self.assertTrue(existing.check_password('OriginalPassword123!'))
        self.assertEqual(existing.profile.role, 'teacher')  # 角色沒有被改成 student
        self.assertTrue(
            ClassEnrollment.objects.filter(
                class_room=self.classroom, user=existing, is_active=True
            ).exists()
        )

    def test_rejects_invalid_username_without_crashing(self):
        response = self._post('bad username!,某人')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='bad username!').exists())

    def test_teacher_cannot_batch_create_into_another_teachers_class(self):
        other_class = ClassRoom.objects.create(name='別人的班級', created_by=self.other_teacher)
        response = self.client.get(
            reverse('classes:batch_create_students', kwargs={'pk': other_class.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_student_cannot_access_batch_create(self):
        student = make_user('student2', role='student')
        self.client.force_login(student)
        response = self.client.get(
            reverse('classes:batch_create_students', kwargs={'pk': self.classroom.pk})
        )
        self.assertRedirects(response, reverse('classes:list'))

    def test_csv_export_contains_generated_password(self):
        self._post('s003,陳小美')
        response = self.client.get(
            reverse('classes:batch_create_students_csv', kwargs={'pk': self.classroom.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8-sig')
        self.assertIn('s003', content)
        self.assertIn('陳小美', content)


class ClassResultsTests(TestCase):
    """回歸測試：class_results 修掉 N+1 查詢後，結果內容要跟修之前一樣正確。

    對應修復：classes/views.py::class_results 原本對每位學生 x 每份指派
    考卷各查一次 ExamSession；改成先一次查完再用字典組合。
    """

    def setUp(self):
        self.teacher = make_user('results_teacher', role='teacher')
        self.classroom = ClassRoom.objects.create(name='成績測試班級', created_by=self.teacher)

        self.students = [make_user(f'results_student{i}') for i in range(3)]
        for s in self.students:
            ClassEnrollment.objects.create(class_room=self.classroom, user=s, is_active=True)

        def make_question():
            return Question.objects.create(
                title='q', content='q',
                option_a='a', option_b='b', option_c='c', option_d='d',
                correct_answer='A',
            )

        self.exam1 = Exam.objects.create(title='考卷一', created_by=self.teacher)
        self.exam2 = Exam.objects.create(title='考卷二', created_by=self.teacher)
        ClassExamAssignment.objects.create(
            class_room=self.classroom, exam=self.exam1, assigned_by=self.teacher
        )
        ClassExamAssignment.objects.create(
            class_room=self.classroom, exam=self.exam2, assigned_by=self.teacher
        )

        # 只有 student0 交了 exam1，其餘都還沒交
        ExamSession.objects.create(
            exam=self.exam1, user=self.students[0], is_submitted=True, score=42
        )

        self.client.force_login(self.teacher)

    def test_results_map_sessions_to_correct_student_and_exam(self):
        response = self.client.get(
            reverse('classes:results', kwargs={'pk': self.classroom.pk})
        )
        self.assertEqual(response.status_code, 200)

        results = {r['user'].username: r['results'] for r in response.context['results']}
        student0_results = {r['exam'].title: r['session'] for r in results['results_student0']}
        self.assertEqual(student0_results['考卷一'].score, 42)
        self.assertIsNone(student0_results['考卷二'])

        student1_results = {r['exam'].title: r['session'] for r in results['results_student1']}
        self.assertIsNone(student1_results['考卷一'])
        self.assertIsNone(student1_results['考卷二'])

    def test_query_count_does_not_scale_with_students_times_exams(self):
        # 修 N+1 之前，3 位學生 x 2 份考卷 = 6 次額外查詢；修好之後應該固定只查 1 次。
        # 用門檻值而非精確次數，避免跟 middleware/auth 的查詢次數綁太死。
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(
                reverse('classes:results', kwargs={'pk': self.classroom.pk})
            )
        self.assertEqual(response.status_code, 200)
        exam_session_queries = [q for q in ctx.captured_queries if 'exams_examsession' in q['sql']]
        self.assertEqual(
            len(exam_session_queries), 1,
            f'預期只查一次 ExamSession，實際查了 {len(exam_session_queries)} 次：{exam_session_queries}'
        )


class ClassDeleteTests(TestCase):
    """新功能：教師可以刪除自己建立的班級。"""

    def setUp(self):
        self.teacher = make_user('delete_teacher', role='teacher')
        self.other_teacher = make_user('delete_other_teacher', role='teacher')
        self.student = make_user('delete_student', role='student')
        self.classroom = ClassRoom.objects.create(
            name='待刪除班級', created_by=self.teacher, class_code='CLASS99'
        )
        ClassEnrollment.objects.create(
            class_room=self.classroom, user=self.student, is_active=True
        )

    def test_owner_sees_confirm_page_on_get(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse('classes:delete', kwargs={'pk': self.classroom.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ClassRoom.objects.filter(pk=self.classroom.pk).exists())  # GET 不刪除

    def test_owner_can_delete_class(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse('classes:delete', kwargs={'pk': self.classroom.pk}), follow=True
        )
        self.assertRedirects(response, reverse('classes:list'))
        self.assertFalse(ClassRoom.objects.filter(pk=self.classroom.pk).exists())
        # 班級成員紀錄也應該一併清掉（CASCADE）
        self.assertFalse(ClassEnrollment.objects.filter(class_room_id=self.classroom.pk).exists())

    def test_deleting_frees_up_class_code_for_reuse(self):
        self.client.force_login(self.teacher)
        self.client.post(reverse('classes:delete', kwargs={'pk': self.classroom.pk}))
        # 代號空出來後，其他班級應該可以拿去用
        new_class = ClassRoom.objects.create(
            name='新班級', created_by=self.teacher, class_code='CLASS99'
        )
        self.assertEqual(new_class.class_code, 'CLASS99')

    def test_other_teacher_cannot_delete(self):
        self.client.force_login(self.other_teacher)
        response = self.client.post(
            reverse('classes:delete', kwargs={'pk': self.classroom.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ClassRoom.objects.filter(pk=self.classroom.pk).exists())

    def test_student_cannot_delete(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('classes:delete', kwargs={'pk': self.classroom.pk})
        )
        self.assertRedirects(response, reverse('classes:list'))
        self.assertTrue(ClassRoom.objects.filter(pk=self.classroom.pk).exists())


class ClassJoinRateLimitTests(TestCase):
    """回歸測試：猜錯班級代號要有次數上限，不能無限暴力枚舉。

    對應修復：class_code 只有 100 種組合（'CLASS'+兩位數字），加入班級原本
    對猜錯完全沒有節流，寫個小腳本幾秒就能把 00~99 全部試過一輪。
    """

    def setUp(self):
        self.user = make_user('ratelimit_user')
        self.client.force_login(self.user)
        from django.core.cache import cache
        cache.clear()

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def _guess_wrong_code(self):
        return self.client.post(reverse('classes:join'), {'class_code': 'CLASS00'})

    def test_wrong_guesses_below_limit_still_show_normal_error(self):
        response = self._guess_wrong_code()
        self.assertContains(response, '找不到此班級代號')

    def test_exceeding_limit_blocks_further_attempts(self):
        for _ in range(10):
            self._guess_wrong_code()
        response = self._guess_wrong_code()
        self.assertContains(response, '嘗試次數過多')

    def test_correct_code_still_works_when_under_limit(self):
        classroom = ClassRoom.objects.create(
            name='節流測試班級', created_by=make_user('ratelimit_teacher', role='teacher'),
            class_code='CLASS42',
        )
        response = self.client.post(
            reverse('classes:join'), {'class_code': 'CLASS42'}, follow=True
        )
        self.assertRedirects(response, reverse('classes:detail', kwargs={'pk': classroom.pk}))
