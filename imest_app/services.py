from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from .models import TestAttempt


class Conflict(APIException):
    status_code = 409
    default_detail = 'Попытка изменена в другой вкладке. Обновите страницу, чтобы загрузить сохранённые ответы.'


def finish(attempt, now):
    attempt.score = sum(attempt.answers.get(str(q['id'])) == q['correct_id'] for q in attempt.snapshot)
    attempt.finished_at = min(now, attempt.deadline)


@transaction.atomic
def update_attempt(attempt_id, payload=None, submit=False):
    # UPDATE acquires a write lock on SQLite too. Revisions prevent stale writes.
    query = TestAttempt.objects.filter(pk=attempt_id, finished_at__isnull=True)
    if payload is not None:
        query = query.filter(revision=payload['revision'])
    changed = query.update(revision=F('revision') + 1)
    attempt = TestAttempt.objects.select_related('test', 'student').get(pk=attempt_id)
    if attempt.finished_at:
        return attempt
    if not changed:
        raise Conflict()
    now = timezone.now()
    if now >= attempt.deadline:
        finish(attempt, now)
    elif payload is not None:
        allowed = {q['id']: {o['id'] for o in q['options']} for q in attempt.snapshot}
        for answer in payload['answers']:
            if answer['answer_id'] not in allowed.get(answer['question_id'], set()):
                raise ValidationError('Вопрос или вариант ответа не относится к этой попытке.')
        attempt.answers = {str(a['question_id']): a['answer_id'] for a in payload['answers']}
        if submit:
            finish(attempt, now)
    attempt.save(update_fields=['answers', 'score', 'finished_at'])
    return attempt


def attempt_data(attempt):
    return {
        'id': attempt.id, 'title': attempt.test.title, 'code': attempt.test.code,
        'revision': attempt.revision, 'started_at': attempt.started_at,
        'deadline': attempt.deadline, 'server_time': timezone.now(),
        'finished_at': attempt.finished_at, 'answers': attempt.answers,
        'questions': [{k: v for k, v in q.items() if k != 'correct_id'} for q in attempt.snapshot],
        'score': attempt.score if attempt.finished_at else None, 'total': len(attempt.snapshot),
    }
