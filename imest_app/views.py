import csv
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import AnswerOption, Question, Student, Teacher, Test, TestAttempt
from .serializers import AttemptInput, TestInput
from .services import attempt_data, update_attempt


def teacher_for(user):
    return get_object_or_404(Teacher, user=user)


def student_for(user):
    return get_object_or_404(Student, user=user)


def accessible_test(user, code):
    code = code.upper().replace('-', '').replace(' ', '')
    test = get_object_or_404(Test.objects.select_related('teacher'), code=code, status=Test.Status.PUBLISHED)
    student = student_for(user)
    if student.school.casefold().strip() != test.teacher.school.casefold().strip():
        raise PermissionDenied('Этот тест предназначен для другой школы.')
    if test.classroom and student.classroom.casefold().strip() != test.classroom.casefold().strip():
        raise PermissionDenied('Этот тест предназначен для другого класса.')
    return test, student


def draft_data(test):
    return {
        'id': test.id, 'code': test.code, 'title': test.title, 'classroom': test.classroom,
        'start_date': test.start_date.isoformat(), 'duration': test.duration, 'status': test.status,
        'questions': [{'text': q.text, 'options': [
            {'text': o.text, 'is_correct': o.is_correct} for o in q.options.all()
        ]} for q in test.questions.all()],
    }


@login_required
def home(request):
    teacher = Teacher.objects.filter(user=request.user).first()
    if teacher:
        tests = Test.objects.filter(teacher=teacher).order_by('-id')
        return render(request, 'teacher_dashboard.html', {'tests': Paginator(tests, 12).get_page(request.GET.get('page'))})
    student, _ = Student.objects.get_or_create(user=request.user, defaults={
        'name': request.user.first_name or request.user.username,
        'surname': request.user.last_name, 'school': '', 'classroom': '',
    })
    for attempt in student.attempts.filter(finished_at__isnull=True, deadline__lte=timezone.now()):
        update_attempt(attempt.id)
    return render(request, 'index.html', {
        'attempts': Paginator(student.attempts.select_related('test'), 12).get_page(request.GET.get('page')), 'student': student,
    })


@login_required
def editor(request, pk=None):
    teacher = teacher_for(request.user)
    test = get_object_or_404(Test.objects.prefetch_related('questions__options'), pk=pk, teacher=teacher) if pk else None
    return render(request, 'editor.html', {'test': test, 'initial': draft_data(test) if test else None})


@login_required
def room(request, pk):
    attempt = get_object_or_404(TestAttempt, pk=pk, student__user=request.user)
    return render(request, 'room.html', {'attempt_id': attempt.id})


@login_required
def results(request, pk):
    test = get_object_or_404(Test, pk=pk, teacher__user=request.user)
    for attempt in test.attempts.filter(finished_at__isnull=True, deadline__lte=timezone.now()):
        update_attempt(attempt.id)
    attempts = test.attempts.select_related('student').order_by('-score', 'started_at')
    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="results-{test.code}.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['Ученик', 'Класс', 'Баллы', 'Всего', 'Статус', 'Начало', 'Завершение'])
        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
        for a in attempts:
            writer.writerow([safe(a.student), safe(a.student.classroom), a.score if a.finished_at else '',
                len(a.snapshot), 'Завершён' if a.finished_at else 'В процессе',
                timezone.localtime(a.started_at).isoformat(),
                timezone.localtime(a.finished_at).isoformat() if a.finished_at else ''])
        return response
    return render(request, 'results.html', {'test': test, 'attempts': Paginator(attempts, 50).get_page(request.GET.get('page'))})


class LookupThrottle(UserRateThrottle):
    rate = '30/min'


class LookupAPI(APIView):
    throttle_classes = [LookupThrottle]

    def get(self, request):
        test, student = accessible_test(request.user, request.query_params.get('code', ''))
        attempt = TestAttempt.objects.filter(test=test, student=student).first()
        return Response({'title': test.title, 'code': test.code, 'duration': test.duration,
            'start_date': test.start_date, 'can_start': timezone.now() >= test.start_date,
            'question_count': test.questions.count(), 'attempt_id': attempt.id if attempt else None})


class StartAPI(APIView):
    throttle_classes = [LookupThrottle]

    @transaction.atomic
    def post(self, request, code):
        test, student = accessible_test(request.user, code)
        # Serialize starts and publication/archive against this test.
        Test.objects.filter(pk=test.id).update(title=F('title'))
        test.refresh_from_db()
        if test.status != Test.Status.PUBLISHED:
            raise ValidationError('Тест закрыт.')
        existing = TestAttempt.objects.filter(test=test, student=student).first()
        if existing:
            return Response({'attempt_id': existing.id})
        if timezone.now() < test.start_date:
            raise ValidationError('Время начала теста ещё не наступило.')
        snapshot = []
        for q in test.questions.prefetch_related('options'):
            options = list(q.options.all())
            correct = [o.id for o in options if o.is_correct]
            if len(options) < 2 or len(correct) != 1:
                raise ValidationError('В тесте некорректный вопрос. Обратитесь к учителю.')
            snapshot.append({'id': q.id, 'text': q.text, 'correct_id': correct[0],
                'options': [{'id': o.id, 'text': o.text} for o in options]})
        if not snapshot:
            raise ValidationError('В тесте нет вопросов.')
        now = timezone.now()
        attempt = TestAttempt.objects.create(test=test, student=student, snapshot=snapshot,
            started_at=now, deadline=now + timedelta(minutes=test.duration))
        return Response({'attempt_id': attempt.id}, status=201)


class AttemptAPI(APIView):
    def get(self, request, pk):
        attempt = get_object_or_404(TestAttempt.objects.select_related('test'), pk=pk, student__user=request.user)
        if not attempt.finished_at and timezone.now() >= attempt.deadline:
            attempt = update_attempt(attempt.id)
        return Response(attempt_data(attempt))

    def post(self, request, pk, operation='save'):
        if operation not in {'save', 'submit'}:
            raise ValidationError('Неизвестная операция.')
        get_object_or_404(TestAttempt, pk=pk, student__user=request.user)
        serializer = AttemptInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = update_attempt(pk, serializer.validated_data, submit=operation == 'submit')
        return Response(attempt_data(attempt))


class TeacherTestAPI(APIView):
    @transaction.atomic
    def post(self, request, pk=None, operation=None):
        if operation not in {None, 'publish', 'archive', 'duplicate'}:
            raise ValidationError('Неизвестная операция.')
        teacher = teacher_for(request.user)
        test = None
        if pk:
            # A no-op write acquires a lock on all supported databases.
            if not Test.objects.filter(pk=pk, teacher=teacher).update(title=F('title')):
                get_object_or_404(Test, pk=pk, teacher=teacher)
            test = Test.objects.get(pk=pk, teacher=teacher)
        if operation == 'archive':
            test.status = Test.Status.ARCHIVED
            test.save(update_fields=['status'])
            return Response({'id': test.id, 'code': test.code})
        if operation == 'duplicate':
            data = draft_data(test)
            data['title'] = data['title'][:245] + ' (копия)'
            test = None
        elif operation == 'publish':
            if test.status != Test.Status.DRAFT:
                raise ValidationError('Опубликовать можно только черновик.')
            serializer = TestInput(data=draft_data(test))
            serializer.is_valid(raise_exception=True)
            test.status = Test.Status.PUBLISHED
            test.save(update_fields=['status'])
            return Response({'id': test.id, 'code': test.code})
        else:
            data = request.data
        if test and test.status != Test.Status.DRAFT:
            raise ValidationError('Опубликованный тест неизменяем. Создайте копию для редактирования.')
        serializer = TestInput(data=data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        questions = values.pop('questions')
        if test is None:
            test = Test.objects.create(teacher=teacher, **values)
        else:
            for key, value in values.items():
                setattr(test, key, value)
            test.save()
            test.questions.all().delete()
        for question in questions:
            q = Question.objects.create(test=test, text=question['text'])
            AnswerOption.objects.bulk_create([AnswerOption(question=q, **o) for o in question['options']])
        return Response({'id': test.id, 'code': test.code})
