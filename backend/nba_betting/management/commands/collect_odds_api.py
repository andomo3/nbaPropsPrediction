from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Collect historical player props from the Odds API."

    def handle(self, *args, **options):
        self.stdout.write("collect_odds_api is not implemented yet.")