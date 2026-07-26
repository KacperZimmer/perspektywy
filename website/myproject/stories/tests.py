from django.test import TestCase
from django.db import connection


class DatabaseConnection(TestCase):

    def test_postgres_connection(self):
        connection.ensure_connection()

        print("\n--- DIAGNOSTYKA POŁĄCZENIA ---")
        print("Silnik bazy (Vendor):", connection.vendor)
        print("Użyta nazwa bazy:", connection.settings_dict['NAME'])
        print("Użyty użytkownik:", connection.settings_dict['USER'])
        print("------------------------------\n")

        self.assertTrue(connection.is_usable(), "Brak połączenia z baza danych ")