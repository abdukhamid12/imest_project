"""Independent SQLite smoke test. Does not read or modify the project database."""
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
handle, database_path = tempfile.mkstemp(prefix='imest-concurrency-', suffix='.sqlite3')
os.close(handle)
os.environ['DJANGO_DB_PATH'] = database_path
os.environ['DJANGO_SETTINGS_MODULE'] = 'imest_project.settings'
import django
django.setup()
from django.core.management import call_command
from django.db import close_old_connections
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient
from imest_app.models import Teacher, Student, Test, Question, AnswerOption, TestAttempt

call_command('migrate', verbosity=0)
teacher = Teacher.objects.create(user=User.objects.create(username='teacher'), school='Demo')
test = Test.objects.create(teacher=teacher, title='Concurrent test', status='published')
q = Question.objects.create(test=test, text='2+2')
answer = AnswerOption.objects.create(question=q, text='4', is_correct=True)
AnswerOption.objects.create(question=q, text='5')
users = []
for i in range(20):
    user = User.objects.create(username=f'student{i}')
    Student.objects.create(user=user, name='Demo', surname=str(i), school='Demo', classroom='1')
    users.append(user)


def run_student(user):
    close_old_connections()
    try:
        client = APIClient()
        client.force_authenticate(user)
        started = client.post(f'/api/tests/{test.code}/start/', {}, format='json')
        assert started.status_code == 201, (started.status_code, str(started.data))
        pk = started.data['attempt_id']
        saved = client.post(f'/api/attempts/{pk}/save/', {'revision':0, 'answers':[{'question_id':q.id,'answer_id':answer.id}]}, format='json')
        assert saved.status_code == 200, (saved.status_code, str(saved.data))
        submitted = client.post(f'/api/attempts/{pk}/submit/', {'revision':saved.data['revision'], 'answers':[{'question_id':q.id,'answer_id':answer.id}]}, format='json')
        assert submitted.status_code == 200 and submitted.data['score'] == 1, str(submitted.data)
        return pk
    finally:
        close_old_connections()


start = perf_counter()
with override_settings(ALLOWED_HOSTS=['testserver']):
    with ThreadPoolExecutor(max_workers=20) as pool:
        result = list(pool.map(run_student, users))
assert len(set(result)) == 20
assert TestAttempt.objects.filter(score=1, finished_at__isnull=False).count() == 20
print(f'PASS: 20 simultaneous students, 60 successful requests, {perf_counter()-start:.2f}s')
print(f'Isolated verification database: {database_path}')

# Competing starts by the same student must reuse one attempt.
race_test = Test.objects.create(teacher=teacher, title='Race', status='published')
race_q = Question.objects.create(test=race_test, text='Race question')
race_a = AnswerOption.objects.create(question=race_q, text='Yes', is_correct=True)
AnswerOption.objects.create(question=race_q, text='No')
def race_start(_):
    close_old_connections()
    try:
        client = APIClient(); client.force_authenticate(users[0])
        response = client.post(f'/api/tests/{race_test.code}/start/', {}, format='json')
        assert response.status_code in (200,201), str(response.data)
        return response.data['attempt_id']
    finally:
        close_old_connections()
with override_settings(ALLOWED_HOSTS=['testserver']):
    with ThreadPoolExecutor(max_workers=8) as pool:
        race_ids = list(pool.map(race_start, range(8)))
assert len(set(race_ids)) == 1

def race_save(_):
    close_old_connections()
    try:
        client = APIClient(); client.force_authenticate(users[0])
        response = client.post(f'/api/attempts/{race_ids[0]}/save/', {
            'revision':0,'answers':[{'question_id':race_q.id,'answer_id':race_a.id}]},format='json')
        return response.status_code
    finally:
        close_old_connections()
with override_settings(ALLOWED_HOSTS=['testserver']):
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(race_save,range(8)))
assert statuses.count(200) == 1 and statuses.count(409) == 7, statuses
print('PASS: 8 competing starts reuse one attempt; 8 stale saves produce one commit and seven conflicts.')
