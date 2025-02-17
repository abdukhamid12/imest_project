# Generated by Django 5.1.3 on 2024-11-07 06:25

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('difficulty', models.IntegerField(default=1)),
                ('correct_answer', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('surname', models.CharField(max_length=100)),
                ('school', models.CharField(max_length=100)),
                ('classroom', models.CharField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name='AnswerOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=255)),
                ('is_correct', models.BooleanField(default=False)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='imest_app.question')),
            ],
        ),
        migrations.CreateModel(
            name='Teacher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school', models.CharField(max_length=100)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Test',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('classroom', models.CharField(max_length=50)),
                ('start_date', models.DateTimeField()),
                ('duration', models.IntegerField(default=60)),
                ('is_finished', models.BooleanField(default=False)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='imest_app.teacher')),
            ],
        ),
        migrations.CreateModel(
            name='StudentAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('points_awarded', models.IntegerField(default=0)),
                ('answer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='imest_app.answeroption')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='imest_app.question')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='imest_app.student')),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='imest_app.test')),
            ],
        ),
        migrations.AddField(
            model_name='question',
            name='test',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='imest_app.test'),
        ),
    ]
