import ollama


class News_LLM:
    def __init__(self, model_name):
        self.model = model_name

    def tag_cluster(self, title_list):
        prompt = f"""
        Jesteś surowym systemem tagującym dla portalu informacyjnego. Twoim zadaniem jest przypisanie tagów do grupy artykułów.
        Masz całkowity zakaz pisania jakichkolwiek wstępów, wyjaśnień czy podsumowań. Zwracasz TYLKO surową tablicę JSON.

        ZASADY:
        1. Wybierz od 1 do 2 tagów z tej zamkniętej listy kategorii:
           [Polityka, Świat, Polska, Gospodarka, Biznes, Kryminalne, Społeczeństwo, Prawo, Konflikty zbrojne, Pogoda]
        2. Dodaj od 1 do 3 tagów będących wyłącznie NAZWAMI WŁASNYMI (np. państwo, miasto, nazwisko, organizacja).
        3. Łączna liczba tagów nie może przekroczyć 5.

        TYTUŁY ARTYKUŁÓW:
        {title_list}

        OCZEKIWANY FORMAT ODPOWIEDZI (dokładnie tak, nic więcej):
        ["Tag1", "Tag2", "Tag3"]
        """
        response = ollama.chat(
            model="qwen3.6:35b",
            messages={[role ]}

        )