from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(label='Имя', max_length=100)
    last_name = forms.CharField(label='Фамилия', max_length=100)
    school = forms.CharField(label='Школа', max_length=100, help_text='Укажите название так же, как ваш учитель.')
    classroom = forms.CharField(label='Класс', max_length=50, help_text='Например, 9А.')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'school', 'classroom', 'password1', 'password2']

    def clean(self):
        data = super().clean()
        if not data.get('classroom'):
            self.add_error('classroom', 'Укажите свой класс.')
        return data


class LoginForm(AuthenticationForm):
    pass


class ProfileForm(forms.Form):
    first_name = forms.CharField(label='Имя', max_length=100)
    last_name = forms.CharField(label='Фамилия', max_length=100)
    school = forms.CharField(label='Школа', max_length=100)
    classroom = forms.CharField(label='Класс', max_length=50)
