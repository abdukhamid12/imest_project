from rest_framework import serializers


class OptionInput(serializers.Serializer):
    text = serializers.CharField(max_length=255)
    is_correct = serializers.BooleanField()


class QuestionInput(serializers.Serializer):
    text = serializers.CharField(max_length=5000)
    options = OptionInput(many=True, min_length=2, max_length=8)

    def validate_options(self, options):
        if sum(option['is_correct'] for option in options) != 1:
            raise serializers.ValidationError('Укажите ровно один правильный ответ.')
        if len({o['text'].casefold() for o in options}) != len(options):
            raise serializers.ValidationError('Варианты ответа не должны повторяться.')
        return options


class TestInput(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    classroom = serializers.CharField(max_length=50, allow_blank=True, default='')
    start_date = serializers.DateTimeField()
    duration = serializers.IntegerField(min_value=1, max_value=480)
    questions = QuestionInput(many=True, min_length=1, max_length=100)


class AnswerInput(serializers.Serializer):
    question_id = serializers.IntegerField(min_value=1)
    answer_id = serializers.IntegerField(min_value=1)


class AttemptInput(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    answers = AnswerInput(many=True, max_length=100)

    def validate_answers(self, answers):
        if len({a['question_id'] for a in answers}) != len(answers):
            raise serializers.ValidationError('Один вопрос может иметь только один ответ.')
        return answers
