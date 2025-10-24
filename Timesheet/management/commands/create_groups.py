from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = 'Create default groups: Admin, Accounting, User'

    def handle(self, *args, **options):
        groups = ['Admin', 'Accounting', 'User']
        for g in groups:
            obj, created = Group.objects.get_or_create(name=g)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group {g}'))
            else:
                self.stdout.write(self.style.NOTICE(f'Group {g} already exists'))

        self.stdout.write(self.style.SUCCESS('Done'))
