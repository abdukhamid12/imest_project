from django.core.management.base import BaseCommand
from django.utils import timezone
from imest_app.models import TestAttempt
from imest_app.services import update_attempt


class Command(BaseCommand):
    help = 'Finalize expired attempts from their last server-saved answers.'

    def handle(self, *args, **options):
        ids = list(TestAttempt.objects.filter(finished_at__isnull=True, deadline__lte=timezone.now()).values_list('id', flat=True))
        for pk in ids:
            update_attempt(pk)
        self.stdout.write(self.style.SUCCESS(f'Finalized {len(ids)} expired attempts.'))
