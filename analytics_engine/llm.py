import ollama


class News_LLM:
    def __init__(self, model_name):
        self.model_name = model_name

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
        return response


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

        return response