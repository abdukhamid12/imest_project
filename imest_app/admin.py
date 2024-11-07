from django.contrib import admin
from .models import Teacher, Student, Test, Question, AnswerOption, StudentAnswer

class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 1  # Number of empty forms to display for new options
    fields = ('text', 'is_correct')  # Include the is_correct field
    list_display = ('text', 'is_correct')  # Show the field in the inline list

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'school')
    search_fields = ('user__username', 'school')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'surname', 'school', 'classroom')
    search_fields = ('name', 'surname')

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'classroom', 'start_date', 'duration')
    list_filter = ('teacher', 'classroom')
    search_fields = ('title',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'test', 'difficulty')
    list_filter = ('test',)
    inlines = [AnswerOptionInline]  # Allow adding multiple answer options inline

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('student', 'test', 'question', 'answer', 'points_awarded')
    list_filter = ('test', 'student')

    # Добавьте функциональность для подсчета общих баллов для каждого студента
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Вы можете добавить дополнительные обработки, если необходимо
        return qs
