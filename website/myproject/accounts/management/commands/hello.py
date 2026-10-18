from django.core.management.base import BaseCommand



class Command(BaseCommand):
    help = "komenda testowa do przywitania"

    def handle(self, *args, **options):
        self.stdout.write("Hello world")