from django.core.management import BaseCommand
from WikiData import fetch_top_politicians

class Command(BaseCommand):

    help = "Command used to seed N politicians into PostgreSQL Database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Number of politicians to fetch from the Wikidata",
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        self.stdout.write(self.style.NOTICE(f"Fetching information about {limit} politicians..."))

        try:
            politicians_data = fetch_top_politicians()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to process the data: {e}"))
            return

        for element in politicians_data[:limit]:
            print(type(element), element)





