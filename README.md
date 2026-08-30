# praca-magisterska

Repozytorium robocze do pracy magisterskiej.

## FIRE-PL Simulator

Deterministyczny, miesięczny model symulacji akumulacji kapitału w ramach koncepcji FIRE (Financial Independence, Retire Early) w warunkach polskiego systemu podatkowo-emerytalnego. Testuje 4 scenariusze (2 archetypy gospodarstw domowych × z/bez wykorzystania wehikułów podatkowych IKE/IKZE/PPK/OKI) i stanowi podstawę rozdziału IV pracy magisterskiej ("Studium przypadku realizacji założeń FIRE na polskim rynku kapitałowym"). Metodologia opisana jest szczegółowo w rozdziale III pracy (podrozdziały 3.1–3.4).

### Status

- **Silnik podatkowy (`src/tax_engine.py`)** — zaimplementowany i przetestowany. Kaskadowa alokacja nadwyżki budżetowej (PPK → IKZE → IKE → OKI → rachunek standardowy), mechanika PPK, kompensacja strat kapitałowych, harmonogram zwrotu ulgi IKZE.
- **Pipeline danych historycznych (`src/data_loader.py`)** — zaimplementowany i przetestowany. Automatyczne pobieranie (Damodaran, NBP, GUS) zweryfikowane na żywo; WIG i TBSP.Index (oba opcjonalne) wymagają ręcznego pobrania pliku (patrz niżej).
- **Pętla symulacyjna i scenariusze (`src/simulation.py`, `src/scenarios.py`)** — zaimplementowane i przetestowane. Uruchomione na realnych danych 2008–2026 (`results/summary.csv`).

### Dane historyczne

**Noga akcyjna portfela to jeden globalny ETF (iShares MSCI ACWI, ticker `ACWI`), nie osobno S&P 500 i WIG**, a **noga obligacyjna to wyłącznie polskie detaliczne obligacje EDO (10-letnie, indeksowane inflacją)** — bez TBSP.Index i bez globalnych obligacji (Damodaran/UST10Y). Trzy świadome decyzje, odejście od oryginalnej metodologii z sekcji 2/3.2 pracy, które warto odzwierciedlić przy pisaniu rozdziału IV. `fetch_damodaran_returns` zostaje w kodzie i jest przetestowana, ale nie jest już częścią głównego pipeline'u.

| Źródło | Zmienna | Sposób pobrania |
|---|---|---|
| Aswath Damodaran (NYU Stern) | 10-letnie obligacje skarbowe USA — **niewykorzystywane w głównym pipeline** (patrz sekcja "Symulacja i scenariusze") | Automatyczny (`fetch_damodaran_returns`), dostępne opcjonalnie |
| NBP, tabela A | Kurs średni USD/PLN | Automatyczny (`fetch_nbp_usdpln_monthly`) — **wyłącznie od 2002 r.**, wcześniejszych danych publiczne API NBP nie udostępnia |
| GUS BDL API | CPI (inflacja), przeciętne miesięczne wynagrodzenie brutto | Automatyczny (`fetch_gus_cpi`, `fetch_gus_avg_wage`) |
| iShares MSCI ACWI ETF (Yahoo Finance) | Globalny ETF akcyjny — zastępuje S&P 500 + WIG | **Zrzut z sesji przeglądarki** (`data/raw/acwi_monthly.csv`) — patrz niżej, nie jest to wynik automatycznego zapytania |
| Ministerstwo Finansów, obligacjeskarbowe.pl | Marże serii obligacji EDO — zastępują TBSP.Index | **Zebrane skryptem** (`data/raw/edo_margins.csv`) ze statycznych stron ofertowych — patrz niżej |
| NBP, archiwum stóp procentowych | Stopa referencyjna NBP — formuła zastępcza tam, gdzie marża EDO nieznana | Automatyczny/zrzut (`data/raw/nbp_reference_rate.csv`, `fetch_nbp_reference_rate`) |
| GPW / stooq.pl | Indeks WIG | **Ręczny, opcjonalny** — nieużywany w głównym pipeline od czasu przejścia na globalny ETF; `load_wig_manual` pozostaje dostępny na potrzeby ewentualnego porównania z rynkiem polskim w rozdziale IV |
| GPW Benchmark | TBSP.Index | **Ręczny, opcjonalny** — analogicznie, `load_tbsp_manual` pozostaje dostępny na potrzeby porównania |

**Skąd wzięły się dane EDO i stopy referencyjnej NBP:**
- **Stopa referencyjna NBP** pochodzi z oficjalnego, w pełni maszynowo czytelnego archiwum `static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml` (bez zabezpieczeń antybotowych) — obejmuje okres od 26.02.1998 do dziś.
- **Marże EDO** zostały zebrane skryptem odpytującym ~150 statycznych stron ofertowych Ministerstwa Finansów (`obligacjeskarbowe.pl/oferta-obligacji/obligacje-10-letnie-edo/edoMMYY/`, gdzie `MMYY` to miesiąc/rok wykupu = miesiąc emisji + 10 lat) — strony te są server-rendered, więc dają się pobrać zwykłym zapytaniem HTTP. EDO wystartowało we wrześniu 2013 r., ale strony archiwalne przechowują konkretną wartość marży dopiero od stycznia 2017 r. — dla wcześniejszych miesięcy (wrzesień 2013 – grudzień 2016) i dla bieżącego roku, zanim GUS opublikuje jego CPI, stosowana jest formuła zastępcza: **stopa referencyjna NBP + 2 p.p.** (zgodnie z instrukcją — 2 p.p. to obowiązująca od dłuższego czasu marża EDO).

**Skąd wzięły się dane ACWI:** żadne z prawdziwie wypróbowanych źródeł nie dało się zeskryptować z tego środowiska — REST API Yahoo Finance blokuje zapytania („Edge: Too Many Requests” już przy pierwszym), `stooq.com`/`stooq.pl` mają wyzwanie antybotowe, `nasdaq.com` było nieosiągalne, `macrotrends.net` zwrócił 403. Dane w `data/raw/acwi_monthly.csv` pochodzą z rzeczywistej sesji przeglądarki na `finance.yahoo.com/quote/ACWI/history` (zakres „Max”, interwał „Monthly”) — to zrzut stanu na dzień pobrania, nie odtwarzalne jednym poleceniem. Odświeżenie o kolejne miesiące wymaga powtórzenia tych samych kroków ręcznie (lub poproszenia o to ponownie).

**Ręczne pobranie WIG i TBSP.Index (opcjonalne, tylko do analiz porównawczych — żadne z nich nie jest już wymagane przez `build_processed_dataset`):**
1. WIG: `stooq.pl/q/d/l/?s=wig&i=m` w przeglądarce, zapisz jako `data/raw/wig.csv`.
2. TBSP.Index: pobierz historyczne notowania z serwisu GPW Benchmark (`gpwbenchmark.pl`) i zapisz jako `data/raw/tbsp.csv`.
3. Oba pliki obsługiwane są zarówno w formacie polskim stooq (`Data;Otwarcie;...;Zamkniecie;Wolumen`), jak i angielskim (`Date,Open,...,Close,Volume`) — `load_wig_manual`/`load_tbsp_manual` same rozpoznają format.

**Ważne ograniczenie zweryfikowane podczas implementacji:** publiczne API NBP (potrzebne do przeliczenia zagranicznej części portfela na PLN) udostępnia dane dopiero od 2002 r. Fundusz ACWI powstał dopiero w marcu 2008 r. — to on, nie NBP, jest teraz wiążącym ograniczeniem dolnym dla pełnej symulacji wszystkich klas aktywów. Krótsza historia niż dawałby S&P 500 (od 1928 r.) jest świadomym kosztem przejścia na jeden, faktycznie inwestowalny globalny instrument.

### Struktura repozytorium

```
data/
├── raw/          # pobrane szeregi źródłowe (Damodaran, WIG, TBSP, GUS, NBP)
└── processed/    # ujednolicone dane (rok/miesiąc, PLN, realne)
src/
├── tax_engine.py  # kaskada podatkowa: IKE/IKZE/PPK/OKI, tax drag, kompensacja strat
├── data_loader.py # pobieranie i normalizacja danych: Damodaran, NBP, GUS, ACWI, EDO
├── simulation.py  # miesieczna petla symulacyjna, SimulationAssumptions
└── scenarios.py   # archetypy A/B, scenariusze A1/A2/B1/B2, run_all_scenarios()
tests/            # testy jednostkowe
results/          # wyniki symulacji (CSV/JSON)
```

### Uruchomienie testów

```bash
pip install -r requirements.txt
pytest
```

### Symulacja i scenariusze

`python -m src.scenarios` uruchamia wszystkie 4 scenariusze (macierz: 2 archetypy × z/bez wehikułów podatkowych, podrozdz. 3.4 pracy) w **3 wariantach alokacji akcje/obligacje (80/20, 60/40, 40/60)** — 12 przebiegów łącznie — na realnych danych historycznych (`build_processed_dataset()`, okno kwiecień 2008 – lipiec 2026) i zapisuje wyniki do `results/scenario_{kod}_equity{wariant}_monthly.csv` (pełna ścieżka miesięczna) oraz `results/summary.csv` (podsumowanie).

**Portfel ma dwie nogi: akcje (globalny ETF ACWI) i obligacje (wyłącznie polskie detaliczne EDO)** — bez globalnych obligacji (Damodaran/UST10Y) i bez TBSP.Index, na wyraźną decyzję użytkownika. Testowanie kilku proporcji akcje/obligacje to bezpośrednia realizacja "elastycznej alokacji aktywów" z hipotezy badawczej pracy (patrz Wstęp).

**Metodologia horyzontu:** symulacja biegnie jedną, nieprzetworzoną historyczną sekwencją zwrotów od pierwszego do ostatniego dostępnego miesiąca — bez cyklicznego powielania danych i bez wielu okien startowych (Monte Carlo). Jeśli cel FIRE (25-krotność rocznych wydatków, aktualizowana co miesiąc wraz ze wzrostem wynagrodzeń) nie zostanie osiągnięty w tym ~18-letnim oknie, wynik jawnie to raportuje (`fire_reached=False`) zamiast ekstrapolować nieistniejące dane.

**Realny wynik (uruchomienie 2026-08):**

| Scenariusz | Alokacja | Cel FIRE osiągnięty? | Lata do FIRE | Wartość portfela na koniec okna |
|---|---|---|---|---|
| A1 (Informatyk, z programami) | 80/20 | **Tak** | 18,0 | 9,03 mln zł |
| A1 | 60/40 | Nie | — | 8,14 mln zł |
| A1 | 40/60 | Nie | — | 7,31 mln zł |
| A2 (Informatyk, bez programów) | 80/20 | **Tak** | 18,2 | 8,66 mln zł |
| A2 | 60/40 | Nie | — | 7,82 mln zł |
| A2 | 40/60 | Nie | — | 7,08 mln zł |
| B1 (Rodzina 2+2, z programami) | 80/20 | Nie | — | 2,74 mln zł |
| B2 (Rodzina 2+2, bez programów) | 80/20 | Nie | — | 2,37 mln zł |

(B1/B2 przy 60/40 i 40/60 analogicznie niżej — pełne dane w `results/summary.csv`.)

Dwie ilustracje bezpośrednio odpowiadające na pytania hipotezy badawczej:
- **Wartość tarczy podatkowej (A1 vs A2, ta sama alokacja 80/20):** oba scenariusze osiągają cel w tym samym ~18-letnim oknie, ale A1 (z IKE/IKZE/PPK/OKI) robi to **szybciej** (18,0 vs 18,2 roku) i kończy z **wyższym** portfelem (9,03 mln vs 8,66 mln zł) — różnica to policzalna wartość korzyści podatkowej III filaru.
- **Wpływ alokacji (80/20 vs 60/40 vs 40/60, ten sam scenariusz):** wyższy udział akcji wyraźnie przyspiesza dojście do celu (tylko wariant 80/20 domyka się w dostępnym oknie danych) kosztem większej zmienności portfela, której ta tabela nie pokazuje wprost — miesięczne ścieżki w `results/*_monthly.csv` pozwalają to zobaczyć.

**Założenia modelu (`SimulationAssumptions`, `src/simulation.py`) — jawnie udokumentowane uproszczenia:**

| Założenie | Wartość | Uzasadnienie |
|---|---|---|
| Alokacja portfela | 80/20, 60/40 lub 40/60 (akcje ACWI / obligacje EDO) | Testowane równolegle jako realizacja "elastycznej alokacji aktywów" z hipotezy pracy |
| TER ACWI | 0,20% rocznie | Realny TER UCITS Acc iShares MSCI ACWI (zweryfikowany) |
| Stopa dywidendy ACWI | 1,5% rocznie | W widełkach realnego trailing yield (1,4–1,6%) |
| Koszt transakcyjny | 0,29% od nowych zakupów | Typowa prowizja maklerska za zagraniczne ETF-y |
| Rebalancing | Raz w roku (grudzień), niezależnie w obrębie każdego konta | Uproszczenie względem "zbiorczego" rebalancingu z podrozdz. 3.3 — patrz niżej |
| PPK: podstawa składek | Dochód netto zamiast brutto | Pełne odtworzenie ZUS/PIT wykracza poza zakres tego etapu — nieznacznie zaniża realne składki i limity |
| Rodzina 2+2 | `household_multiplier=2` (podwójne limity IKE/IKZE/PPK) zamiast dwóch osobno symulowanych osób | Znaczne uproszczenie złożoności bez utraty rzędu wielkości wyniku |
| ROS/ROD (obligacje rodzinne) | Nie zamodelowane w tym etapie | Wymagałoby analogicznego do EDO badania realnych marż tych instrumentów |
| Globalne obligacje (UST10Y) | Nie zamodelowane — noga obligacyjna to wyłącznie EDO | Na wyraźną decyzję użytkownika; `fetch_damodaran_returns` zostaje w kodzie, przetestowana, na wypadek przyszłego porównania |

**Rebalancing — istotne odejście od podrozdz. 3.3 pracy:** tekst pracy opisuje rebalancing jako operację na całym portfelu gospodarstwa domowego, z preferencją korekty przez konta IKE/IKZE przed sięgnięciem po rachunek standardowy. Zaimplementowana wersja rebalansuje **każde konto niezależnie** — prostsze obliczeniowo, wciąż w pełni oddaje kluczowy mechanizm podatkowy (rebalancing na IKE/IKZE/OKI/PPK jest bezpodatkowy, na rachunku standardowym generuje realny podatek Belki, widoczny w wynikach jako `cumulative_rebalancing_tax`), ale nie optymalizuje *które* konto sprzedaje, tak jak zrobiłby to racjonalny inwestor.

### Ograniczenia modelu

Model, zgodnie z podrozdziałem 3.4 pracy, ma charakter ilustracyjnego studium przypadku, nie dowodu o sile statystycznej porównywalnej z klasycznymi badaniami (Bengen, Trinity Study):

- **Tylko 2 archetypy** gospodarstw domowych — nie próba reprezentatywna.
- **Stała stopa oszczędności** — model nie uwzględnia utraty pracy, przerw w karierze, rozwodu ani innych szoków dochodowych.
- **Założenie pełnej racjonalności inwestora** — brak paniki sprzedażowej, brak pogoni za wynikiem, konsekwentne stosowanie algorytmu przez cały horyzont symulacji.
- **Niezmienność polskiego prawa podatkowego** w całym horyzoncie symulacji, mimo że w ostatnich trzech dekadach miały miejsce m.in. reforma 1999, reforma OFE 2014, wprowadzenie PPK w 2019 oraz OKI (uchwalone 2026, w życie od 1.01.2027).
- **Krótka historia polskich danych rynkowych** (~35 lat dla WIG, ~15–20 lat dla obligacji) w porównaniu do niemal stuletniej historii amerykańskiej — liczba niezależnych, nienakładających się 30-letnich okresów możliwych do wyodrębnienia z danych PL jest rzędu pojedynczych sztuk. Wyniki należy traktować jako ilustrację rzędu wielkości, nie dowód statystyczny.
- **Praktyczna dolna granica pełnej symulacji to marzec 2008 r.** (data powstania funduszu ACWI), nie 2002 r. (zakres NBP) ani 1991 r. (start WIG) — patrz sekcja "Dane historyczne" wyżej.
- **Roczne dane (Damodaran, GUS) rozbite na miesiące metodą równomiernej kapitalizacji geometrycznej** (`data_loader.annualize_to_monthly`) — każdy miesiąc danego roku dostaje tę samą stopę zwrotu; rzeczywista wewnątrzroczna zmienność i sezonowość nie są odwzorowane.
- **Noga akcyjna to jeden globalny ETF (ACWI), nie osobno rynek USA i Polski** — odejście od architektury z sekcji 2/3.2 pracy (na decyzję użytkownika), kosztem krótszej historii (2008+ zamiast 1928+ dla USA) w zamian za jeden, spójny, faktycznie inwestowalny instrument zamiast dwóch teoretycznych indeksów.
- **Polska noga obligacji to EDO, nie TBSP.Index** — kolejne odejście od architektury z sekcji 2/3.2 pracy (na decyzję użytkownika). Dla 40 z 156 miesięcy istnienia EDO (wrzesień 2013 – grudzień 2016) oraz dla bieżącego, jeszcze niezakończonego roku kalendarzowego rzeczywista marża/CPI nie są znane, więc stosowana jest formuła zastępcza `stopa referencyjna NBP + 2 p.p.` zamiast faktycznej konstrukcji EDO — patrz sekcja "Dane historyczne" wyżej.
- **Portfel nie zawiera globalnych obligacji** — dwie nogi (akcje ACWI, obligacje EDO), nie trzy z pierwotnego briefu (akcje globalne + obligacje globalne + obligacje polskie). Uproszczenie na wyraźną decyzję użytkownika; obniża dywersyfikację geograficzną części dłużnej portfela.
