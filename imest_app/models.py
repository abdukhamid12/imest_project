import secrets

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import IntegrityError, models, transaction
from django.utils import timezone


def generate_test_code():
    return ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(12))


class Teacher(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    school = models.CharField(max_length=100)

    def __str__(self):
        return self.user.username


class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    school = models.CharField(max_length=100)
    classroom = models.CharField(max_length=50)

    def __str__(self):
        return f'{self.name} {self.surname}'


class Test(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Черновик'
        PUBLISHED = 'published', 'Опубликован'
        ARCHIVED = 'archived', 'В архиве'

    teacher = models.ForeignKey(Teacher, on_delete=models.PROTECT)
    code = models.CharField(max_length=12, unique=True, default=generate_test_code, editable=False)
    title = models.CharField(max_length=255)
    classroom = models.CharField(max_length=50, blank=True)
    start_date = models.DateTimeField(default=timezone.now)
    duration = models.IntegerField(default=60, validators=[MinValueValidator(1), MaxValueValidator(480)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    is_finished = models.BooleanField(default=False)  # Historical records.
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(duration__gte=1, duration__lte=480), name='test_valid_duration')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            return super().save(*args, **kwargs)
        for retry in range(5):
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if not type(self).objects.filter(code=self.code).exists() or retry == 4:
                    raise
                self.code = generate_test_code()

    def __str__(self):
        return self.title


class Question(models.Model):
    test = models.ForeignKey(Test, related_name='questions', on_delete=models.CASCADE)
    text = models.TextField()
    points = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(1000)])
    difficulty = models.IntegerField(default=1)
    correct_answer = models.CharField(max_length=255, blank=True)  # Legacy; is_correct is authoritative.

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.text


class AnswerOption(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.text


class TestAttempt(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='attempts')
    test = models.ForeignKey(Test, on_delete=models.PROTECT, related_name='attempts')
    started_at = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    snapshot = models.JSONField(default=list)  # Private immutable grading key.
    answers = models.JSONField(default=dict)
    score = models.PositiveIntegerField(default=0)
    revision = models.PositiveIntegerField(default=0)

    @property
    def max_score(self):
        return sum(q.get('points', 1) for q in self.snapshot)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['student', 'test'], name='one_attempt_per_student_test')]
        ordering = ['-started_at']


class StudentAnswer(models.Model):
    """Historical answers retained without destructive migration."""
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    test = models.ForeignKey(Test, on_delete=models.PROTECT)
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    answer = models.ForeignKey(AnswerOption, on_delete=models.PROTECT)
    points_awarded = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.student} — {self.test}'


class AttemptEvent(models.Model):
    attempt = models.ForeignKey(TestAttempt, on_delete=models.CASCADE, related_name='events')
    event_id = models.UUIDField()
    kind = models.CharField(max_length=30, choices=[(v, v) for v in ['hidden', 'blur', 'fullscreen_exit', 'page_exit', 'shortcut']])
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['attempt', 'event_id'], name='unique_attempt_event')]
