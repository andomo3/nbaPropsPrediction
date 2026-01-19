from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Collect quarter-level NBA box score data."

    def handle(self, *args, **options):
        self.stdout.write("collect_nba_data is not implemented yet.")