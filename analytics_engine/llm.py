import ollama


class News_LLM:
    def __init__(self, model_name):
        self.model_name = model_name

    def _extract_text(self, response):
        """Pomocnicza funkcja wyciągająca sam tekst niezależnie od wersji biblioteki ollama"""
        if hasattr(response, 'response'):
            return response.response
        elif isinstance(response, dict):
            return response.get('response', '')
        return str(response)

    def generate_title(self, title_list):
        prompt = f"""
                Jesteś doświadczonym redaktorem portalu informacyjnego. Twoim zadaniem jest stworzenie krótkiego i rzetelnego tytułu na podstawie dostarcznoych naglowkow z innych gazet.
                Masz całkowity zakaz pisania jakichkolwiek wstępów, wyjaśnień, cudzysłowów czy komentarzy. Zwracasz TYLKO i wyłącznie sam tytuł, ktory ma byc obiektywny i pozbawiuony emocji patosu i tym podobnych.

                TEKST ARTYKUŁU:
                {title_list}

                OCZEKIWANY FORMAT ODPOWIEDZI:
                Tytuł artykułu
                """

        response = ollama.generate(
            prompt=prompt,
            model=self.model_name
        )
        return self._extract_text(response)

    def generate_summary(self, description_list):
        prompt = f"""
        Jesteś bezstronnym analitykiem informacji. Twoim zadaniem jest stworzenie rzeczowego podsumowania na podstawie dostarczonych opisów (leadów) z różnych artykułów.
        Masz całkowity zakaz pisania wstępów (np. "Oto podsumowanie:", "Z tekstu wynika, że:"), zakończeń czy własnych komentarzy. Zwracasz TYLKO wypunktowane podsumowanie.

        ZASADY:
        1. Stwórz MASYMALNIE 5 krótkich punktów (bullet pointów) podsumowujących najważniejsze fakty.
        2. Zachowaj całkowity obiektywizm i chłodny, informacyjny ton.
        3. Opieraj się TYLKO I WYŁĄCZNIE na dostarczonych opisach. Nie dodawaj wiedzy z zewnątrz.
        4. IGNORUJ ZNIEKSZTAŁCENIA: Jeśli fragment tekstu to kod HTML, skrypty JS, losowe znaki, błędy systemu CMS lub zdania urwane w połowie – zignoruj je.
        5. Jeśli po odrzuceniu śmieci nie ma żadnych sensownych informacji, zwróć dokładnie jedno zdanie: "Brak wystarczających informacji do wygenerowania podsumowania."
        6. Każdy punkt musi zaczynać się od myślnika "- ".

        OPISY ARTYKUŁÓW:
        {description_list}

        OCZEKIWANY FORMAT ODPOWIEDZI:
        - Fakt pierwszy.
        - Fakt drugi.
        - Fakt trzeci.
        """

        response = ollama.generate(
            model=self.model_name,
            prompt=prompt
        )
        return self._extract_text(response)

    def tag_cluster(self, title_list):
        prompt = f"""
        Jesteś surowym systemem tagującym dla portalu informacyjnego. Twoim zadaniem jest przypisanie tagów do grupy artykułów.
        Masz całkowity zakaz pisania jakichkolwiek wstępów, wyjaśnień czy podsumowań. Zwracasz TYLKO surową tablicę JSON.

        ZASADY:
        1. Wybierz od 1 do 2 tagów z tej zamkniętej listy kategorii:
           [Polityka, Świat, Polska, Gospodarka, Biznes, Społeczeństwo, Prawo, Konflikty zbrojne, Pogoda]
        2. Dodaj od 1 do 3 tagów będących wyłącznie NAZWAMI WŁASNYMI (np. państwo, miasto, nazwisko, organizacja).
        3. Łączna liczba tagów nie może przekroczyć 5.

        TYTUŁY ARTYKUŁÓW:
        {title_list}

        OCZEKIWANY FORMAT ODPOWIEDZI (dokładnie tak, nic więcej):
        ["Tag1", "Tag2", "Tag3"]
        """
        response = ollama.generate(
            model=self.model_name,
            prompt=prompt
        )
        return self._extract_text(response)