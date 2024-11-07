from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from .models import Test, Question, AnswerOption, StudentAnswer
from .serializers import *


# ViewSet для управления тестами
class TestViewSet(viewsets.ModelViewSet):
    queryset = Test.objects.all()
    serializer_class = TestSerializer

    @action(detail=True, methods=['post'])
    def submit_answer(self, request, pk=None):
        test = self.get_object()
        if test.is_finished:
            return Response({'error': 'Test is already finished.'}, status=status.HTTP_400_BAD_REQUEST)

        student = request.data.get('student')
        answers = request.data.get('answers')

        total_points = 0
        response_data = []

        for ans in answers:
            try:
                question = Question.objects.get(id=ans['question_id'])
                correct_answer = AnswerOption.objects.filter(question=question, is_correct=True).first()

                points_awarded = 1 if correct_answer and ans['answer_id'] == correct_answer.id else 0

                student_answer = StudentAnswer.objects.create(
                    student_id=student,
                    test=test,
                    question_id=ans['question_id'],
                    answer_id=ans['answer_id'],
                    points_awarded=points_awarded
                )

                total_points += points_awarded
                response_data.append({
                    'question_id': question.id,
                    'points_awarded': points_awarded
                })

            except ObjectDoesNotExist:
                return Response({'error': 'Question or answer does not exist.'}, status=status.HTTP_400_BAD_REQUEST)

        test.is_finished = True
        test.finished_at = timezone.now()
        test.save()

        return Response({'status': 'answers submitted', 'total_points': total_points, 'details': response_data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def test_by_id(self, request):
        test_id = request.query_params.get('test_id')
        test = Test.objects.filter(id=test_id).first()
        if not test:
            return Response({'error': 'Invalid test ID'}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(test)
        return Response(serializer.data)

def home(request):
    return render(request, 'index.html')