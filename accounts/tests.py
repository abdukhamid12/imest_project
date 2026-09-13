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
        for role, model in [('teacher',Teacher),('student',Student)]:
            self.client.logout()
            response = self.client.post('/accounts/signup/', self.data(role))
            self.assertEqual(response.status_code,302)
            self.assertTrue(model.objects.filter(user__username=role).exists())
            self.assertFalse(User.objects.get(username=role).is_staff)

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
