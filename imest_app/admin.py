from django.contrib import admin
from .models import Teacher, Student, Test, Question, AnswerOption, StudentAnswer, TestAttempt


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'school')
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
