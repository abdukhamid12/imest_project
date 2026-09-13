from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class LegacyMigrationTests(TransactionTestCase):
    def test_existing_tests_receive_distinct_codes_and_safe_states(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('imest_app','0001_initial')])
        apps = executor.loader.project_state([('imest_app','0001_initial')]).apps
        User = apps.get_model('auth','User')
        Teacher = apps.get_model('imest_app','Teacher')
        Test = apps.get_model('imest_app','Test')
        user = User.objects.create(username='legacy_migration')
        teacher = Teacher.objects.create(user_id=user.id, school='Legacy')
        Test.objects.create(teacher_id=teacher.id, title='First', start_date=timezone.now(), classroom='9', duration=0)
        Test.objects.create(teacher_id=teacher.id, title='Second', start_date=timezone.now(), classroom='9', is_finished=True)
        try:
            executor = MigrationExecutor(connection)
            target = ('imest_app','0002_testattempt_alter_answeroption_options_and_more')
            executor.migrate([target])
            models = executor.loader.project_state([target]).apps
            tests = list(models.get_model('imest_app','Test').objects.order_by('id'))
            self.assertEqual(len(tests),2)
            self.assertEqual(len({t.code for t in tests}),2)
            self.assertTrue(all(len(t.code) == 12 for t in tests))
            self.assertEqual(tests[0].duration,1)
            self.assertEqual(tests[1].status,'archived')
        finally:
            MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
