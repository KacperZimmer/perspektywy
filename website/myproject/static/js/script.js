document.addEventListener('DOMContentLoaded', () => {
    const dateOptions = {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    };

    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        dateElement.innerText = new Date().toLocaleDateString('pl-PL', dateOptions);
    }
});
document.addEventListener('DOMContentLoaded', () => {

    // ==========================================
    // 1. LOGIKA DLA STRONY GŁÓWNEJ (index.html)
    // ==========================================
    const dateOptions = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        dateElement.innerText = new Date().toLocaleDateString('pl-PL', dateOptions);
    }

    // ==========================================
    // 2. LOGIKA DLA STRONY POWITALNEJ (landing.html) - FADING FEED
    // ==========================================

    const mockArticles = [
        { title: "Debata o wolności słowa w internecie. Nowe przepisy budzą obawy.", left: 20, center: 30, right: 50 },
        { title: "Protesty rolników blokują drogi. Rząd zapowiada interwencję.", left: 15, center: 15, right: 70 },
        { title: "Szczyt klimatyczny zakończony. Sukces czy wizerunkowa wydmuszka?", left: 65, center: 25, right: 10 },
        { title: "Nowy system podatkowy wchodzi w życie. Kto zyska, a kto straci?", left: 33, center: 34, right: 33 },
        { title: "Sztuczna inteligencja w szkołach. Ministerstwo Edukacji ogłasza pilotaż.", left: 40, center: 40, right: 20 },
        { title: "Napięcia na granicy. Wojsko zwiększa obecność.", left: 10, center: 20, right: 70 },
        { title: "Kolejne podwyżki stóp procentowych. Raty kredytów znów w górę.", left: 50, center: 30, right: 20 }
    ];

    const feedContainer = document.getElementById('live-feed-container');

    if (feedContainer) {
        let articleIndex = 0;

        // Ta funkcja aktualizuje wygląd wszystkich kart za każdym razem, gdy dodajemy nową
        function updateCardsState() {
            const cards = Array.from(feedContainer.children);

            cards.forEach((card, index) => {
                // Podstawowe klasy wspólne dla wszystkich kart
                let baseClasses = 'bg-white border border-gray-200 p-4 shadow-sm text-left transition-all duration-1000 ease-in-out shrink-0 w-full rounded-sm transform origin-top';

                // W zależności od pozycji na liście (index), zmieniamy przezroczystość i skalę
                if (index === 0) {
                    // Najnowszy (na samej górze) - 100% widoczny, pełny rozmiar
                    card.className = `${baseClasses} translate-y-0 opacity-100 scale-100 z-50`;
                } else if (index === 1) {
                    // Drugi - lekko przezroczysty, minimalnie mniejszy
                    card.className = `${baseClasses} translate-y-0 opacity-70 scale-95 z-40`;
                } else if (index === 2) {
                    // Trzeci - mocniej przezroczysty, jeszcze mniejszy
                    card.className = `${baseClasses} translate-y-0 opacity-40 scale-90 z-30`;
                } else if (index === 3) {
                    // Czwarty - ledwo widoczny
                    card.className = `${baseClasses} translate-y-0 opacity-10 scale-75 z-20`;
                } else {
                    card.className = `${baseClasses} translate-y-4 opacity-0 scale-50 z-10`;
                    setTimeout(() => card.remove(), 1000);
                }
            });
        }

        function pushNewArticle() {
            const articleData = mockArticles[articleIndex];
            const newCard = document.createElement('div');

            // Stan początkowy dla nowej karty: przesunięta w górę i ukryta
            newCard.className = 'bg-white border border-gray-200 p-4 shadow-sm text-left transition-all duration-1000 ease-in-out shrink-0 w-full rounded-sm transform origin-top -translate-y-12 opacity-0 scale-100';

            newCard.innerHTML = `
                <h3 class="font-serif text-lg font-bold leading-tight mb-3 text-gray-900">${articleData.title}</h3>
                <div class="w-full bg-gray-100 rounded-full h-1.5 flex overflow-hidden">
                    <div class="bg-bias-left h-1.5 transition-all duration-1000 ease-out" style="width: 0%"></div>
                    <div class="bg-bias-center h-1.5 transition-all duration-1000 ease-out" style="width: 0%"></div>
                    <div class="bg-bias-right h-1.5 transition-all duration-1000 ease-out" style="width: 0%"></div>
                </div>
                <div class="flex justify-between text-[9px] font-bold uppercase text-gray-400 mt-2">
                    <span>Lewica: ${articleData.left}%</span>
                    <span>Centrum: ${articleData.center}%</span>
                    <span>Prawica: ${articleData.right}%</span>
                </div>
            `;

            feedContainer.prepend(newCard);

            void newCard.offsetWidth;

            updateCardsState();

            setTimeout(() => {
                const bars = newCard.querySelectorAll('.h-1\\.5 > div');
                if(bars.length === 3) {
                    bars[0].style.width = `${articleData.left}%`;
                    bars[1].style.width = `${articleData.center}%`;
                    bars[2].style.width = `${articleData.right}%`;
                }
            }, 100);

            articleIndex = (articleIndex + 1) % mockArticles.length;
        }

        pushNewArticle();

        setTimeout(pushNewArticle, 500);
        setTimeout(pushNewArticle, 1000);

        setInterval(pushNewArticle, 3500);
    }
});