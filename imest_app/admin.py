from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from django.contrib import admin
from .models import Teacher, Student, Test, Question, AnswerOption, StudentAnswer, TestAttempt


class TeacherCreationForm(forms.ModelForm):
    username = forms.CharField(label='Логин', max_length=150, validators=User._meta.get_field('username').validators)
    first_name = forms.CharField(label='Имя', max_length=150, required=False)
    last_name = forms.CharField(label='Фамилия', max_length=150, required=False)
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Повторите пароль', widget=forms.PasswordInput)

    class Meta:
        model = Teacher
        fields = ['school']

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Этот логин уже занят.')
        return username

    def clean(self):
        data = super().clean()
        if data.get('password1') != data.get('password2'):
            self.add_error('password2', 'Пароли не совпадают.')
        if data.get('password1'):
            user = User(username=data.get('username', ''), first_name=data.get('first_name', ''), last_name=data.get('last_name', ''))
            try:
                validate_password(data['password1'], user)
            except ValidationError as error:
                self.add_error('password1', error)
        return data


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'school')

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = TeacherCreationForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        return ['username', 'first_name', 'last_name', 'school', 'password1', 'password2'] if obj is None else ['user', 'school']

    def get_readonly_fields(self, request, obj=None):
        return ['user'] if obj else []

    def save_model(self, request, obj, form, change):
        if not change:
            data = form.cleaned_data
            obj.user = User.objects.create_user(username=data['username'], password=data['password1'], first_name=data['first_name'], last_name=data['last_name'])
        super().save_model(request, obj, form, change)

    search_fields = ('user__username', 'school')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'surname', 'user', 'school', 'classroom')
    search_fields = ('name', 'surname', 'user__username', 'school')


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Test)
class TestAdmin(ReadOnlyAdmin):
    list_display = ('title', 'code', 'teacher', 'status', 'duration')
    list_filter = ('status', 'teacher')
    search_fields = ('title', 'code')


@admin.register(Question)
class QuestionAdmin(ReadOnlyAdmin):
    list_display = ('text', 'test')


@admin.register(TestAttempt)
class AttemptAdmin(ReadOnlyAdmin):
    list_display = ('student', 'test', 'started_at', 'finished_at', 'score')


@admin.register(StudentAnswer)
class LegacyAnswerAdmin(ReadOnlyAdmin):
    list_display = ('student', 'test', 'question', 'points_awarded')
