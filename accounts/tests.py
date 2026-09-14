from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from imest_app.models import Teacher, Student


class AccountTests(TestCase):
    def setUp(self):
        cache.clear()

    def data(self, role):
        return {'username':role, 'first_name':'Имя','last_name':'Фамилия','school':'Школа 1',
            'classroom':'9А','role':role,'password1':'strong-account-password-42','password2':'strong-account-password-42'}

    def test_registration_creates_matching_profile(self):
        for role, model in [('teacher',Student),('student',Student)]:
            self.client.logout()
            response = self.client.post('/accounts/signup/', self.data(role))
            self.assertEqual(response.status_code,302)
            self.assertTrue(model.objects.filter(user__username=role).exists())
            self.assertFalse(User.objects.get(username=role).is_staff)
            self.assertFalse(Teacher.objects.filter(user__username=role).exists())

    def test_student_class_required(self):
        data = self.data('student')
        data['classroom'] = ''
        self.assertEqual(self.client.post('/accounts/signup/',data).status_code,200)
        self.assertFalse(User.objects.exists())

    def test_legacy_user_receives_student_profile(self):
        user = User.objects.create_user('legacy')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertTrue(Student.objects.filter(user=user).exists())


    def test_admin_creates_teacher_with_password_and_private_dashboard(self):
        admin = User.objects.create_superuser('admin', password='admin-secret-123')
        self.client.force_login(admin)
        url = '/admin/imest_app/teacher/add/'
        self.assertEqual(self.client.get(url).status_code, 200)
        data = self.data('newteacher')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='newteacher')
        self.assertTrue(user.check_password(data['password1']))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(Teacher.objects.filter(user=user).exists())
        self.assertFalse(Student.objects.filter(user=user).exists())
        self.client.logout()
        self.assertTrue(self.client.login(username=user.username, password=data['password1']))
        self.assertTemplateUsed(self.client.get('/'), 'teacher_dashboard.html')
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_admin_teacher_invalid_password_creates_nothing(self):
        admin = User.objects.create_superuser('admin', password='admin-secret-123')
        self.client.force_login(admin)
        data = self.data('newteacher')
        data.update(password1='123', password2='123')
        self.assertEqual(self.client.post('/admin/imest_app/teacher/add/', data).status_code, 200)
        self.assertFalse(User.objects.filter(username='newteacher').exists())
