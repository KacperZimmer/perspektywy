document.addEventListener('DOMContentLoaded', () => {

    // ==========================================
    // 1. DATA - STRONA GŁÓWNA
    // ==========================================
    const dateOptions = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        dateElement.innerText = new Date().toLocaleDateString('pl-PL', dateOptions);
    }

    // ==========================================
    // 2. FADING FEED - STRONA POWITALNA
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

        function updateCardsState() {
            const cards = Array.from(feedContainer.children);

            cards.forEach((card, index) => {
                // Nowe bazowe klasy: zaokrąglenia, tło, cień, border
                let baseClasses = 'bg-white border border-slate-100 p-5 shadow-sm text-left transition-all duration-1000 ease-in-out shrink-0 w-full rounded-2xl transform origin-top absolute top-0 left-0 right-0';

                if (index === 0) {
                    card.className = `${baseClasses} translate-y-0 opacity-100 scale-100 z-50`;
                } else if (index === 1) {
                    card.className = `${baseClasses} translate-y-20 opacity-70 scale-[0.97] z-40`;
                } else if (index === 2) {
                    card.className = `${baseClasses} translate-y-36 opacity-40 scale-[0.93] z-30`;
                } else if (index === 3) {
                    card.className = `${baseClasses} translate-y-48 opacity-10 scale-[0.89] z-20`;
                } else {
                    card.className = `${baseClasses} translate-y-56 opacity-0 scale-75 z-10`;
                    setTimeout(() => card.remove(), 1000);
                }
            });
        }

        function pushNewArticle() {
            const articleData = mockArticles[articleIndex];
            const newCard = document.createElement('div');

            newCard.className = 'bg-white border border-slate-100 p-5 shadow-sm text-left transition-all duration-1000 ease-in-out shrink-0 w-full rounded-2xl transform origin-top -translate-y-10 opacity-0 scale-100 absolute top-0 left-0 right-0';

            // Nowy szablon karty dla feedu - usunięto szeryfy, zaokrąglono paski
            newCard.innerHTML = `
                <h3 class="font-sans text-lg font-bold leading-tight mb-4 text-slate-900">${articleData.title}</h3>
                <div class="w-full bg-slate-100 rounded-full h-2 flex overflow-hidden gap-1">
                    <div class="bg-bias-left h-2 rounded-l-full transition-all duration-1000 ease-out" style="width: 0%"></div>
                    <div class="bg-bias-center h-2 transition-all duration-1000 ease-out" style="width: 0%"></div>
                    <div class="bg-bias-right h-2 rounded-r-full transition-all duration-1000 ease-out" style="width: 0%"></div>
                </div>
                <div class="flex justify-between text-[10px] font-bold uppercase text-slate-400 mt-3">
                    <span class="text-red-500/80">Lewica ${articleData.left}%</span>
                    <span class="text-slate-500/80">Centrum ${articleData.center}%</span>
                    <span class="text-blue-500/80">Prawica ${articleData.right}%</span>
                </div>
            `;

            feedContainer.prepend(newCard);
            void newCard.offsetWidth; // Trigger reflow
            updateCardsState();

            // Animacja pasków błędu
            setTimeout(() => {
                const bars = newCard.querySelectorAll('.h-2 > div');
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

        setInterval(pushNewArticle, 4000);
    }
});