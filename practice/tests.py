from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from questions.models import Question
from .models import QuestionNote


def make_question():
    return Question.objects.create(
        title='筆記測試題目',
        content='1 + 1 = ?',
        option_a='2', option_b='3', option_c='4', option_d='5',
        correct_answer='A',
    )


class NoteEditRedirectTests(TestCase):
    """回歸測試：note_edit 不能被拿來當開放重新導向（open redirect）。

    對應修復：practice/views.py::note_edit 曾經直接把 HTTP_REFERER
    這個使用者端可偽造的 header 當成 redirect 目標。
    """

    def setUp(self):
        self.user = User.objects.create_user(username='note_user', password='x')
        self.client.force_login(self.user)
        self.question = make_question()

    def _post(self, referer=None):
        extra = {'HTTP_REFERER': referer} if referer else {}
        return self.client.post(
            reverse('practice:note_edit', kwargs={'pk': self.question.pk}),
            {'content': '我的筆記'},
            **extra,
        )

    def test_note_is_saved(self):
        self._post()
        note = QuestionNote.objects.get(user=self.user, question=self.question)
        self.assertEqual(note.content, '我的筆記')

    def test_external_referer_is_not_followed(self):
        response = self._post(referer='http://evil.example.com/phishing')
        self.assertRedirects(response, reverse('practice:start'))

    def test_same_site_referer_is_followed(self):
        same_site_url = f'http://testserver{reverse("practice:question")}'
        response = self._post(referer=same_site_url)
        # redirect(referer) 保留原本的絕對網址，所以比對也用絕對網址；
        # fetch_redirect_response=False：practice:question 在沒有練習佇列時
        # 自己會再轉一次址，這裡只要確認 note_edit 導去了正確的目標 URL。
        self.assertRedirects(response, same_site_url, fetch_redirect_response=False)

    def test_missing_referer_falls_back_to_practice_start(self):
        response = self._post()
        self.assertRedirects(response, reverse('practice:start'))


class PracticeQuestionAnswerValidationTests(TestCase):
    """回歸測試：practice_question 對不合法的 answer 要擋下，不能讓 DB 500。"""

    def setUp(self):
        self.user = User.objects.create_user(username='practice_user', password='x')
        self.client.force_login(self.user)
        self.question = make_question()
        session = self.client.session
        session['practice_queue'] = [self.question.pk]
        session['practice_index'] = 0
        session.save()

    def test_oversized_answer_is_rejected_without_crashing(self):
        response = self.client.post(
            reverse('practice:question'), {'answer': 'AAAAAAAAAAAA', 'confidence': ''}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '答案格式不正確')
        from practice.models import PracticeRecord
        self.assertFalse(
            PracticeRecord.objects.filter(user=self.user, question=self.question).exists()
        )

    def test_valid_answer_is_accepted(self):
        response = self.client.post(
            reverse('practice:question'), {'answer': 'A', 'confidence': 'sure'}
        )
        self.assertEqual(response.status_code, 200)
        from practice.models import PracticeRecord
        record = PracticeRecord.objects.get(user=self.user, question=self.question)
        self.assertEqual(record.selected_answer, 'A')
