from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Train the period-specific prediction models."

    def handle(self, *args, **options):
        self.stdout.write("train_models is not implemented yet.")