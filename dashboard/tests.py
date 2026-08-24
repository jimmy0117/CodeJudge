from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import SiteSettings


def make_user(username, role='student', password='x'):
    user = User.objects.create_user(username=username, password=password)
    user.profile.role = role
    user.profile.save()
    return user


class SiteSettingsPermissionTests(TestCase):
    """回歸測試：平台設定頁面只能給 admin 用，教師不行。

    對應修復：dashboard/views.py::site_settings_view 曾經用
    is_teacher_or_admin() 判斷，導致任何教師都能修改全站的
    Google OAuth Client ID/Secret、網站名稱、顏色主題等設定。
    """

    def test_teacher_cannot_view_settings(self):
        teacher = make_user('settings_teacher', role='teacher')
        self.client.force_login(teacher)
        response = self.client.get(reverse('dashboard:settings'))
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_teacher_cannot_change_google_oauth_settings(self):
        teacher = make_user('settings_teacher2', role='teacher')
        self.client.force_login(teacher)
        self.client.post(reverse('dashboard:settings'), {
            'site_name': '被入侵的網站',
            'google_oauth_client_id': 'attacker-client-id',
        })
        settings_obj = SiteSettings.get_solo()
        self.assertNotEqual(settings_obj.google_oauth_client_id, 'attacker-client-id')

    def test_admin_can_view_and_change_settings(self):
        admin = make_user('settings_admin', role='admin')
        self.client.force_login(admin)
        response = self.client.get(reverse('dashboard:settings'))
        self.assertEqual(response.status_code, 200)

        self.client.post(reverse('dashboard:settings'), {
            'site_name': '新網站名稱',
            'google_oauth_client_id': 'legit-client-id',
        })
        settings_obj = SiteSettings.get_solo()
        self.assertEqual(settings_obj.site_name, '新網站名稱')
        self.assertEqual(settings_obj.google_oauth_client_id, 'legit-client-id')

    def test_student_cannot_view_settings(self):
        student = make_user('settings_student', role='student')
        self.client.force_login(student)
        response = self.client.get(reverse('dashboard:settings'))
        self.assertRedirects(response, reverse('dashboard:index'))
