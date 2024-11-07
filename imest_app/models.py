from django.db import models
from django.contrib.auth.models import User

# Модель учителя
class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    school = models.CharField(max_length=100)

    def __str__(self):
        return self.user.username

# Модель студента
class Student(models.Model):
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    school = models.CharField(max_length=100)
    classroom = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name} {self.surname}"

# Модель теста
class Test(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    classroom = models.CharField(max_length=50)
    start_date = models.DateTimeField()
    duration = models.IntegerField(default=60)  # Время теста в минутах
    is_finished = models.BooleanField(default=False)  # New field to indicate if the test is finished
    finished_at = models.DateTimeField(null=True, blank=True)  # Store when the test was finished

    def __str__(self):
        return self.title

# Модель вопроса
class Question(models.Model):
    test = models.ForeignKey(Test, related_name="questions", on_delete=models.CASCADE)
    text = models.TextField()
    difficulty = models.IntegerField(default=1)
    correct_answer = models.CharField(max_length=255)

    def __str__(self):
        return self.text

# Варианты ответа на вопрос
class AnswerOption(models.Model):
    question = models.ForeignKey(Question, related_name="options", on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)  # New field to indicate the correct answer

    def __str__(self):
        return self.text

# Ответы студентов
class StudentAnswer(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.ForeignKey(AnswerOption, on_delete=models.CASCADE)
    points_awarded = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.student.name} {self.student.surname} - {self.test.title}"