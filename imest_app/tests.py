from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AnswerOption, Question, Student, Teacher, Test, TestAttempt
from .services import update_attempt


class AssessmentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.teacher_user = User.objects.create_user('teacher', password='secure-test-password')
        self.teacher = Teacher.objects.create(user=self.teacher_user, school='School')
        self.user = User.objects.create_user('student', password='secure-test-password')
        self.student = Student.objects.create(user=self.user, name='A', surname='B', school='School', classroom='9A')
        self.second_user = User.objects.create_user('second', password='secure-test-password')
        self.second_student = Student.objects.create(user=self.second_user, name='C', surname='D', school='School', classroom='9A')
        self.test = Test.objects.create(teacher=self.teacher, title='Algebra', classroom='9A', duration=2, status='published')
        self.q = Question.objects.create(test=self.test, text='<img src=x onerror=alert(1)>')
        self.correct = AnswerOption.objects.create(question=self.q, text='Correct', is_correct=True)
        self.wrong = AnswerOption.objects.create(question=self.q, text='Wrong')
        self.api = APIClient()
        self.api.force_login(self.user)

    def start(self, test=None):
        response = self.api.post(f'/api/tests/{(test or self.test).code}/start/', {}, format='json')
        self.assertIn(response.status_code, [200, 201], response.data)
        return TestAttempt.objects.get(pk=response.data['attempt_id'])

    def payload(self, attempt, answers=None):
        return {'revision': attempt.revision, 'answers': answers if answers is not None else [
            {'question_id': str(self.q.id), 'answer_id': str(self.correct.id)}]}

    def submit(self, attempt, data=None, operation='submit'):
        return self.api.post(f'/api/attempts/{attempt.id}/{operation}/', data or self.payload(attempt), format='json')

    def test_anonymous_cannot_access_or_delete(self):
        self.api.logout()
        self.assertEqual(self.api.get('/api/tests/lookup/', {'code': self.test.code}).status_code, 403)
        self.assertEqual(self.api.delete(f'/api/teacher/tests/{self.test.id}/').status_code, 403)
        self.assertTrue(Test.objects.filter(pk=self.test.pk).exists())

    def test_lookup_normalizes_code_and_does_not_leak_questions(self):
        code = self.test.code.lower()
        response = self.api.get('/api/tests/lookup/', {'code': code[:4] + '-' + code[4:]})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('questions', response.data)
        self.assertEqual(response.data['code'], self.test.code)

    def test_code_unique_and_collision_retried(self):
        with patch('imest_app.models.generate_test_code', return_value='ABCDEFGHJKLM'):
            other = Test.objects.create(teacher=self.teacher, title='Other', code=self.test.code)
        self.assertEqual(other.code, 'ABCDEFGHJKLM')
        self.assertNotEqual(other.code, self.test.code)

    def test_unique_code_database_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Test.objects.bulk_create([Test(teacher=self.teacher, title='Duplicate', code=self.test.code)])

    def test_future_start_denied(self):
        self.test.start_date = timezone.now() + timedelta(days=1)
        self.test.save()
        r = self.api.post(f'/api/tests/{self.test.code}/start/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(TestAttempt.objects.count(), 0)

    def test_wrong_school_or_class_denied(self):
        self.student.school = 'Other'
        self.student.save()
        self.assertEqual(self.api.get('/api/tests/lookup/', {'code':self.test.code}).status_code, 403)
        self.student.school, self.student.classroom = 'School', 'Other'
        self.student.save()
        self.assertEqual(self.api.post(f'/api/tests/{self.test.code}/start/', {}, format='json').status_code, 403)

    def test_draft_unavailable(self):
        self.test.status = 'draft'
        self.test.save()
        self.assertEqual(self.api.get('/api/tests/lookup/', {'code':self.test.code}).status_code, 404)

    def test_start_is_idempotent(self):
        first = self.start()
        self.assertEqual(first.id, self.start().id)
        self.assertEqual(TestAttempt.objects.count(), 1)
        self.assertEqual(first.deadline - first.started_at, timedelta(minutes=2))

    def test_private_answers_never_exposed(self):
        attempt = self.start()
        data = self.api.get(f'/api/attempts/{attempt.id}/').data
        self.assertNotIn('correct_id', str(data))
        self.assertNotIn('is_correct', str(data))
        self.assertIsNone(data['score'])

    def test_correct_string_ids_score_once(self):
        attempt = self.start()
        response = self.submit(attempt)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['score'], 1)

    def test_student_id_spoof_ignored(self):
        attempt = self.start()
        data = self.payload(attempt)
        data['student'] = self.second_student.id
        self.assertEqual(self.submit(attempt, data).status_code, 200)
        attempt.refresh_from_db()
        self.assertEqual(attempt.student_id, self.student.id)

    def test_two_students_finish_independently(self):
        first = self.start()
        self.submit(first)
        self.api.force_login(self.second_user)
        second = self.start()
        self.assertEqual(self.submit(second).data['score'], 1)
        self.test.refresh_from_db()
        self.assertEqual(self.test.status, 'published')
        self.assertFalse(self.test.is_finished)

    def test_duplicate_answers_rejected_without_writes(self):
        attempt = self.start()
        data = self.payload(attempt)
        data['answers'] *= 4
        self.assertEqual(self.submit(attempt, data).status_code, 400)
        attempt.refresh_from_db()
        self.assertEqual(attempt.answers, {})
        self.assertEqual(attempt.revision, 0)

    def test_cross_question_option_rejected_atomically(self):
        attempt = self.start()
        q = Question.objects.create(test=self.test, text='New')
        a = AnswerOption.objects.create(question=q, text='Foreign', is_correct=True)
        data = self.payload(attempt)
        data['answers'].append({'question_id':q.id,'answer_id':a.id})
        self.assertEqual(self.submit(attempt, data).status_code, 400)
        attempt.refresh_from_db()
        self.assertEqual(attempt.answers, {})
        self.assertEqual(attempt.revision, 0)

    def test_answer_from_wrong_question_rejected(self):
        attempt = self.start()
        q = Question.objects.create(test=self.test, text='Other')
        a = AnswerOption.objects.create(question=q, text='Other')
        data = self.payload(attempt, [{'question_id':self.q.id,'answer_id':a.id}])
        self.assertEqual(self.submit(attempt, data).status_code, 400)

    def test_stale_revision_conflicts(self):
        attempt = self.start()
        data = self.payload(attempt)
        self.assertEqual(self.submit(attempt, data, 'save').status_code, 200)
        data['answers'] = []
        self.assertEqual(self.submit(attempt, data, 'save').status_code, 409)
        attempt.refresh_from_db()
        self.assertEqual(attempt.answers[str(self.q.id)], self.correct.id)

    def test_repeated_submit_returns_original_result(self):
        attempt = self.start()
        self.submit(attempt)
        data = self.payload(attempt, [])
        second = self.submit(attempt, data)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['score'], 1)

    def test_expiry_grades_only_saved_answers(self):
        attempt = self.start()
        self.submit(attempt, operation='save')
        attempt.refresh_from_db()
        TestAttempt.objects.filter(pk=attempt.id).update(deadline=timezone.now() - timedelta(seconds=1))
        response = self.submit(attempt, self.payload(attempt, []))
        self.assertEqual(response.data['score'], 1)
        self.assertIsNotNone(response.data['finished_at'])

    def test_expiry_with_no_answers_finishes_zero(self):
        attempt = self.start()
        TestAttempt.objects.filter(pk=attempt.id).update(deadline=timezone.now() - timedelta(seconds=1))
        response = self.submit(attempt)
        self.assertEqual(response.data['score'], 0)

    def test_get_finalizes_expired_attempt(self):
        attempt = self.start()
        TestAttempt.objects.filter(pk=attempt.id).update(deadline=timezone.now() - timedelta(seconds=1))
        self.assertIsNotNone(self.api.get(f'/api/attempts/{attempt.id}/').data['finished_at'])

    def test_resume_returns_saved_answers_and_same_deadline(self):
        attempt = self.start()
        self.submit(attempt, operation='save')
        response = self.api.get(f'/api/attempts/{attempt.id}/')
        self.assertEqual(response.data['answers'], {str(self.q.id):self.correct.id})
        self.assertEqual(response.data['deadline'], attempt.deadline)

    def test_other_student_cannot_read_write_attempt(self):
        attempt = self.start()
        self.api.force_login(self.second_user)
        self.assertEqual(self.api.get(f'/api/attempts/{attempt.id}/').status_code, 404)
        self.assertEqual(self.submit(attempt).status_code, 404)

    def test_snapshot_survives_question_change(self):
        attempt = self.start()
        self.correct.is_correct = False
        self.correct.save()
        self.assertEqual(self.submit(attempt).data['score'], 1)

    def test_csrf_required_for_session_write(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(f'/api/tests/{self.test.code}/start/', {}, format='json').status_code, 403)

    def test_student_cannot_manage_tests(self):
        self.assertEqual(self.api.post('/api/teacher/tests/', {}, format='json').status_code, 404)
        self.assertEqual(self.api.get(f'/teacher/tests/{self.test.id}/results/').status_code, 404)

    def draft_payload(self):
        return {'title':'New assessment', 'classroom':'9A', 'start_date':timezone.now().isoformat(),
            'duration':15, 'questions':[{'text':'Question','options':[
                {'text':'Yes','is_correct':True},{'text':'No','is_correct':False}]}]}

    def test_teacher_create_publish_duplicate_archive(self):
        self.api.force_login(self.teacher_user)
        created = self.api.post('/api/teacher/tests/', self.draft_payload(), format='json')
        self.assertEqual(created.status_code, 200)
        pk = created.data['id']
        self.assertEqual(self.api.post(f'/api/teacher/tests/{pk}/publish/', {}, format='json').status_code, 200)
        self.assertEqual(self.api.post(f'/api/teacher/tests/{pk}/', self.draft_payload(), format='json').status_code, 400)
        copy = self.api.post(f'/api/teacher/tests/{pk}/duplicate/', {}, format='json')
        self.assertEqual(copy.status_code, 200)
        self.assertNotEqual(copy.data['code'], created.data['code'])
        self.assertEqual(Test.objects.get(pk=copy.data['id']).status, 'draft')
        self.assertEqual(self.api.post(f'/api/teacher/tests/{pk}/archive/', {}, format='json').status_code, 200)

    def test_teacher_cannot_manage_others_tests(self):
        other = User.objects.create_user('otherteacher')
        Teacher.objects.create(user=other, school='School')
        self.api.force_login(other)
        self.assertEqual(self.api.post(f'/api/teacher/tests/{self.test.id}/archive/', {}, format='json').status_code, 404)
        self.assertEqual(self.api.get(f'/teacher/tests/{self.test.id}/results/').status_code, 404)

    def test_invalid_editor_input_rejected(self):
        self.api.force_login(self.teacher_user)
        for field, value in [('duration',0),('questions',[])]:
            data = self.draft_payload()
            data[field] = value
            self.assertEqual(self.api.post('/api/teacher/tests/', data, format='json').status_code, 400)
        data = self.draft_payload()
        data['questions'][0]['options'][1]['is_correct'] = True
        self.assertEqual(self.api.post('/api/teacher/tests/', data, format='json').status_code, 400)

    def test_archiving_does_not_interrupt_existing_attempt(self):
        attempt = self.start()
        self.test.status = 'archived'
        self.test.save()
        self.assertEqual(self.submit(attempt).status_code, 200)
        self.api.force_login(self.second_user)
        self.assertEqual(self.api.post(f'/api/tests/{self.test.code}/start/', {}, format='json').status_code, 404)

    def test_pages_render_and_export_formula_safe(self):
        attempt = self.start()
        self.student.name = '=1+1'
        self.student.save()
        self.api.force_login(self.teacher_user)
        for url in ['/', '/teacher/new/', f'/teacher/tests/{self.test.id}/', f'/teacher/tests/{self.test.id}/results/']:
            self.assertEqual(self.api.get(url).status_code, 200, url)
        response = self.api.get(f'/teacher/tests/{self.test.id}/results/?format=csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=1+1", response.content.decode('utf-8-sig'))

    def test_logout_requires_post(self):
        self.assertEqual(self.api.get('/accounts/logout/').status_code, 405)
        self.assertEqual(self.api.post('/accounts/logout/').status_code, 302)

    def test_unknown_operation_rejected(self):
        attempt = self.start()
        self.assertEqual(self.api.post(f'/api/attempts/{attempt.id}/unknown/', self.payload(attempt), format='json').status_code, 400)


    def test_weighted_grading_immutable_and_maximum(self):
        self.q.points = 6
        self.q.save()
        q2 = Question.objects.create(test=self.test, text='Second', points=4)
        AnswerOption.objects.create(question=q2, text='Yes', is_correct=True)
        AnswerOption.objects.create(question=q2, text='No')
        attempt = self.start()
        self.q.points = 99
        self.q.save()
        response = self.submit(attempt)
        self.assertEqual(response.data['score'], 6)
        self.assertEqual(response.data['max_score'], 10)
        self.assertEqual(response.data['total'], 2)
        self.assertNotIn('correct_id', response.data['questions'][0])

    def test_legacy_snapshot_defaults_to_one_point(self):
        attempt = self.start()
        attempt.snapshot[0].pop('points')
        attempt.save()
        response = self.submit(attempt)
        self.assertEqual(response.data['score'], 1)
        self.assertEqual(response.data['max_score'], 1)

    def test_teacher_points_validation_and_copy(self):
        self.api.force_login(self.teacher_user)
        for points in [0, -1, 1001, 1.5]:
            data = self.draft_payload()
            data['questions'][0]['points'] = points
            self.assertEqual(self.api.post('/api/teacher/tests/', data, format='json').status_code, 400)
        data['questions'][0]['points'] = 6
        response = self.api.post('/api/teacher/tests/', data, format='json')
        pk = response.data['id']
        self.assertEqual(Test.objects.get(pk=pk).questions.get().points, 6)
        copied = self.api.post(f'/api/teacher/tests/{pk}/duplicate/', {}, format='json')
        self.assertEqual(Test.objects.get(pk=copied.data['id']).questions.get().points, 6)

    def test_public_rating_automatic_finished_only_and_ties(self):
        attempt = self.start()
        self.api.logout()
        self.assertEqual(list(self.api.get('/rating/').context['students']), [])
        self.api.force_login(self.user)
        self.submit(attempt)
        self.api.force_login(self.second_user)
        second = self.start()
        self.submit(second)
        self.api.logout()
        response = self.api.get('/')
        self.assertEqual(response.status_code, 200)
        rows = list(response.context['students'])
        self.assertEqual([(r.total_points, r.place, r.completed) for r in rows], [(1,1,1),(1,1,1)])
        # More points from another completed test accumulate without manual ranking entries.
        extra = Test.objects.create(teacher=self.teacher, title='Extra')
        TestAttempt.objects.create(student=self.student, test=extra, deadline=timezone.now(), finished_at=timezone.now(), score=6)
        rows = list(self.api.get('/rating/').context['students'])
        self.assertEqual([(r.total_points, r.place) for r in rows], [(7,1),(1,2)])

    def test_events_owner_validation_deduplication_and_teacher_visibility(self):
        from uuid import uuid4
        attempt = self.start()
        url = f'/api/attempts/{attempt.pk}/events/'
        data = {'event_id':str(uuid4()), 'kind':'hidden'}
        self.assertEqual(self.api.post(url, data, format='json').status_code, 200)
        self.api.post(url, data, format='json')
        self.assertEqual(attempt.events.count(), 1)
        self.assertEqual(self.api.post(url, dict(data,kind='invalid'), format='json').status_code, 400)
        self.api.force_login(self.second_user)
        self.assertEqual(self.api.post(url, data, format='json').status_code, 404)
        self.api.force_login(self.teacher_user)
        response = self.api.get(f'/teacher/tests/{self.test.pk}/results/')
        self.assertEqual(list(response.context['attempts'])[0].event_count, 1)
        self.api.force_login(self.user)
        self.submit(attempt)
        self.api.post(url, dict(data,event_id=str(uuid4())), format='json')
        self.assertEqual(attempt.events.count(), 1)


    def test_active_attempt_never_exposes_question_points(self):
        self.q.points = 6
        self.q.save()
        attempt = self.start()
        for response in [self.api.get(f'/api/attempts/{attempt.id}/'), self.submit(attempt, operation='save')]:
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.data['max_score'])
            self.assertIsNone(response.data['score'])
            for question in response.data['questions']:
                self.assertNotIn('points', question)
                self.assertNotIn('correct_id', question)
        attempt.refresh_from_db()
        finished = self.submit(attempt)
        self.assertEqual(finished.data['score'], 6)
        self.assertEqual(finished.data['max_score'], 6)
