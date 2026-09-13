import sqlite3
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create and verify a consistent SQLite backup.'

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if database['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Use the native backup utility for your database engine.')
        directory = settings.BASE_DIR / 'backups'
        directory.mkdir(exist_ok=True)
        target = directory / f'db-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3'
        uri = Path(database['NAME']).resolve().as_uri() + '?mode=ro'
        with sqlite3.connect(uri, uri=True) as source, sqlite3.connect(target) as backup:
            source.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise CommandError('Backup integrity verification failed.')
        self.stdout.write(self.style.SUCCESS(str(target)))
