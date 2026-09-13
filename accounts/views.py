from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from imest_app.models import Student, Teacher
from .forms import LoginForm, ProfileForm, SignUpForm


def limited(request, scope):
    # Configure a shared cache for multi-process deployments.
    key = f'auth:{scope}:{request.META.get("REMOTE_ADDR", "")}'
    count = cache.get(key, 0)
    cache.set(key, count + 1, 300)
    return count >= 20


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST':
        if limited(request, 'signup'):
            form.add_error(None, 'Слишком много попыток. Повторите через 5 минут.')
        elif form.is_valid():
            with transaction.atomic():
                user = form.save()
                data = form.cleaned_data
                if data['role'] == 'teacher':
                    Teacher.objects.create(user=user, school=data['school'])
                else:
                    Student.objects.create(user=user, name=data['first_name'], surname=data['last_name'],
                        school=data['school'], classroom=data['classroom'])
            login(request, user)
            return redirect('home')
    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        if limited(request, 'login'):
            form.add_error(None, 'Слишком много попыток. Повторите через 5 минут.')
        elif form.is_valid():
            login(request, form.get_user())
            return redirect('home')
    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def profile(request):
    student = Student.objects.filter(user=request.user).first()
    if not student:
        return redirect('home')
    form = ProfileForm(request.POST or None, initial={'first_name': student.name,
        'last_name': student.surname, 'school': student.school, 'classroom': student.classroom})
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            student.name, student.surname = data['first_name'], data['last_name']
            student.school, student.classroom = data['school'], data['classroom']
            student.save()
            request.user.first_name, request.user.last_name = student.name, student.surname
            request.user.save(update_fields=['first_name', 'last_name'])
        messages.success(request, 'Профиль сохранён.')
        return redirect('home')
    return render(request, 'accounts/profile.html', {'form': form})
