from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .forms import RegisterForm


class RegisterRoleEscalationTests(TestCase):
    """回歸測試：註冊表單不得讓使用者自選 teacher/admin 角色。

    對應修復：accounts/forms.py 的 RegisterForm 曾經把
    UserProfile.ROLE_CHOICES（含 admin）直接暴露成公開註冊表單欄位，
    任何訪客都能在註冊時勾選「管理員」取得教師/管理員權限。
    """

    def test_register_form_has_no_role_field(self):
        form = RegisterForm()
        self.assertNotIn('role', form.fields)

    def test_register_view_ignores_role_in_post_data(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'sneaky',
            'email': 'sneaky@example.com',
            'password1': 'S0meStrongPassw0rd!',
            'password2': 'S0meStrongPassw0rd!',
            'role': 'admin',  # 惡意嘗試在 POST 塞入 role 欄位
        })
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(username='sneaky')
        self.assertEqual(user.profile.role, 'student')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_new_user_via_orm_defaults_to_student_profile(self):
        user = User.objects.create_user(username='plainuser', password='x')
        self.assertEqual(user.profile.role, 'student')

    def test_superuser_creation_still_gets_admin_profile(self):
        user = User.objects.create_superuser(
            username='root', email='root@example.com', password='x'
        )
        self.assertEqual(user.profile.role, 'admin')


class RegisterEmailUniquenessTests(TestCase):
    """回歸測試：註冊 email 要唯一，避免兩個帳號共用同一個 email。

    對應修復：多個帳號共用同一 email 時，忘記密碼會把好幾組不同帳號的
    重設連結一起寄到同一封信裡（Django PasswordResetForm.get_users 會
    回傳所有 email 相符的帳號）。
    """

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(
            username='first_owner', email='shared@example.com', password='x'
        )
        form = RegisterForm({
            'username': 'second_owner',
            'email': 'shared@example.com',
            'password1': 'Str0ngPassw0rd!X',
            'password2': 'Str0ngPassw0rd!X',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertFalse(User.objects.filter(username='second_owner').exists())

    def test_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            username='first_owner2', email='Shared@Example.com', password='x'
        )
        form = RegisterForm({
            'username': 'second_owner2',
            'email': 'shared@example.com',
            'password1': 'Str0ngPassw0rd!X',
            'password2': 'Str0ngPassw0rd!X',
        })
        self.assertFalse(form.is_valid())

    def test_unique_email_is_accepted(self):
        form = RegisterForm({
            'username': 'unique_owner',
            'email': 'unique@example.com',
            'password1': 'Str0ngPassw0rd!X',
            'password2': 'Str0ngPassw0rd!X',
        })
        self.assertTrue(form.is_valid(), form.errors)


class ProfileEmailUniquenessTests(TestCase):
    """profile 編輯頁也要擋掉改成別人已經在用的 email。"""

    def test_cannot_change_email_to_someone_elses(self):
        from .forms import ProfileUpdateForm

        User.objects.create_user(
            username='owner_a', email='taken@example.com', password='x'
        )
        user_b = User.objects.create_user(
            username='owner_b', email='original@example.com', password='x'
        )
        form = ProfileUpdateForm({
            'first_name': '', 'last_name': '', 'email': 'taken@example.com',
        }, instance=user_b)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_can_keep_own_email(self):
        from .forms import ProfileUpdateForm

        user = User.objects.create_user(
            username='owner_c', email='mine@example.com', password='x'
        )
        form = ProfileUpdateForm({
            'first_name': '', 'last_name': '', 'email': 'mine@example.com',
        }, instance=user)
        self.assertTrue(form.is_valid(), form.errors)


class PasswordResetFlowTests(TestCase):
    """忘記密碼自助重設流程。"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='forgetful', email='forgetful@example.com', password='OldPassw0rd!'
        )

    def test_password_reset_request_sends_email(self):
        response = self.client.post(reverse('accounts:password_reset'), {
            'email': 'forgetful@example.com',
        })
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('forgetful', mail.outbox[0].body)

    def test_password_reset_unknown_email_does_not_leak_existence(self):
        # Django 的行為：不論帳號是否存在都導向同一個「已寄出」頁面，不寄信給不存在的帳號。
        response = self.client.post(reverse('accounts:password_reset'), {
            'email': 'nobody@example.com',
        })
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_confirm_changes_password(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        # 第一次 GET 會把 token 換成 session 內部標記並轉址到 set-password 表單
        confirm_url = reverse('accounts:password_reset_confirm', kwargs={
            'uidb64': uid, 'token': token,
        })
        response = self.client.get(confirm_url, follow=True)
        self.assertEqual(response.status_code, 200)

        set_password_url = response.redirect_chain[-1][0]
        response = self.client.post(set_password_url, {
            'new_password1': 'BrandNewPassw0rd!',
            'new_password2': 'BrandNewPassw0rd!',
        })
        self.assertRedirects(response, reverse('accounts:password_reset_complete'))

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNewPassw0rd!'))


class LoginNextRedirectTests(TestCase):
    """回歸測試：登入頁的 ?next= 不能被拿來做開放重新導向。

    對應修復：accounts/views.py::login_view 曾經把 GET 參數 next
    未經檢查直接丟給 redirect()，攻擊者可以用平台真實網域包裝
    釣魚連結（帳密登入真的成功，但登入後被導去外部網站）。
    """

    def setUp(self):
        self.user = User.objects.create_user(username='next_user', password='TestPassw0rd!123')

    def _login(self, next_param):
        return self.client.post(f"{reverse('accounts:login')}?next={next_param}", {
            'username': 'next_user', 'password': 'TestPassw0rd!123',
        })

    def test_external_next_is_ignored(self):
        response = self._login('http://evil.example.com/phish')
        self.assertRedirects(response, reverse('home'))

    def test_protocol_relative_next_is_ignored(self):
        # //evil.example.com 沒有 http/https，但瀏覽器一樣會當成跨網域網址處理
        response = self._login('//evil.example.com/phish')
        self.assertRedirects(response, reverse('home'))

    def test_same_site_next_is_honored(self):
        response = self._login(reverse('dashboard:index'))
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_missing_next_defaults_to_home(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'next_user', 'password': 'TestPassw0rd!123',
        })
        self.assertRedirects(response, reverse('home'))
