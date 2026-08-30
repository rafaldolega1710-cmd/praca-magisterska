# praca-magisterska

Repozytorium robocze do pracy magisterskiej.

## FIRE-PL Simulator

Deterministyczny, miesięczny model symulacji akumulacji kapitału w ramach koncepcji FIRE (Financial Independence, Retire Early) w warunkach polskiego systemu podatkowo-emerytalnego. Testuje 4 scenariusze (2 archetypy gospodarstw domowych × z/bez wykorzystania wehikułów podatkowych IKE/IKZE/PPK/OKI) i stanowi podstawę rozdziału IV pracy magisterskiej ("Studium przypadku realizacji założeń FIRE na polskim rynku kapitałowym"). Metodologia opisana jest szczegółowo w rozdziale III pracy (podrozdziały 3.1–3.4).

### Status

- **Silnik podatkowy (`src/tax_engine.py`)** — zaimplementowany i przetestowany. Kaskadowa alokacja nadwyżki budżetowej (PPK → IKZE → IKE → OKI → rachunek standardowy), mechanika PPK, kompensacja strat kapitałowych, harmonogram zwrotu ulgi IKZE.
- **Pipeline danych historycznych (`src/data_loader.py`)** — zaimplementowany i przetestowany. Automatyczne pobieranie (Damodaran, NBP, GUS) zweryfikowane na żywo; WIG i TBSP.Index wymagają ręcznego pobrania pliku (patrz niżej).
- **Pętla symulacyjna i scenariusze (`src/simulation.py`, `src/scenarios.py`)** — w toku.

### Dane historyczne

**Noga akcyjna portfela to jeden globalny ETF (iShares MSCI ACWI, ticker `ACWI`), nie osobno S&P 500 i WIG**, jak pierwotnie zakładał brief (sekcja 2/3.2 pracy) — świadoma decyzja, uproszczenie względem oryginalnej metodologii, którą warto odzwierciedlić przy pisaniu rozdziału IV. Noga obligacji (globalne UST10Y + polski TBSP.Index) pozostaje bez zmian.

| Źródło | Zmienna | Sposób pobrania |
|---|---|---|
| Aswath Damodaran (NYU Stern) | 10-letnie obligacje skarbowe USA (globalna noga obligacji) | Automatyczny (`fetch_damodaran_returns`) |
| NBP, tabela A | Kurs średni USD/PLN | Automatyczny (`fetch_nbp_usdpln_monthly`) — **wyłącznie od 2002 r.**, wcześniejszych danych publiczne API NBP nie udostępnia |
| GUS BDL API | CPI (inflacja), przeciętne miesięczne wynagrodzenie brutto | Automatyczny (`fetch_gus_cpi`, `fetch_gus_avg_wage`) |
| iShares MSCI ACWI ETF (Yahoo Finance) | Globalny ETF akcyjny — zastępuje S&P 500 + WIG | **Zrzut z sesji przeglądarki** (`data/raw/acwi_monthly.csv`) — patrz niżej, nie jest to wynik automatycznego zapytania |
| GPW Benchmark | TBSP.Index (polskie obligacje) | **Ręczny** — brak stabilnego, darmowego API |
| GPW / stooq.pl | Indeks WIG | **Ręczny, opcjonalny** — nieużywany w głównym pipeline od czasu przejścia na globalny ETF; `load_wig_manual` pozostaje dostępny na potrzeby ewentualnego porównania z rynkiem polskim w rozdziale IV |

**Skąd wzięły się dane ACWI:** żadne z prawdziwie wypróbowanych źródeł nie dało się zeskryptować z tego środowiska — REST API Yahoo Finance blokuje zapytania („Edge: Too Many Requests” już przy pierwszym), `stooq.com`/`stooq.pl` mają wyzwanie antybotowe, `nasdaq.com` było nieosiągalne, `macrotrends.net` zwrócił 403. Dane w `data/raw/acwi_monthly.csv` pochodzą z rzeczywistej sesji przeglądarki na `finance.yahoo.com/quote/ACWI/history` (zakres „Max”, interwał „Monthly”) — to zrzut stanu na dzień pobrania, nie odtwarzalne jednym poleceniem. Odświeżenie o kolejne miesiące wymaga powtórzenia tych samych kroków ręcznie (lub poproszenia o to ponownie).

**Ręczne pobranie TBSP.Index (i opcjonalnie WIG):**
1. TBSP.Index: pobierz historyczne notowania z serwisu GPW Benchmark (`gpwbenchmark.pl`) i zapisz jako `data/raw/tbsp.csv`.
2. WIG (opcjonalnie, do analiz porównawczych): `stooq.pl/q/d/l/?s=wig&i=m` w przeglądarce, zapisz jako `data/raw/wig.csv`.
3. Oba pliki obsługiwane są zarówno w formacie polskim stooq (`Data;Otwarcie;...;Zamkniecie;Wolumen`), jak i angielskim (`Date,Open,...,Close,Volume`) — `load_wig_manual`/`load_tbsp_manual` same rozpoznają format.

**Ważne ograniczenie zweryfikowane podczas implementacji:** publiczne API NBP (potrzebne do przeliczenia zagranicznej części portfela na PLN) udostępnia dane dopiero od 2002 r. Fundusz ACWI powstał dopiero w marcu 2008 r. — to on, nie NBP, jest teraz wiążącym ograniczeniem dolnym dla pełnej symulacji wszystkich klas aktywów. Krótsza historia niż dawałby S&P 500 (od 1928 r.) jest świadomym kosztem przejścia na jeden, faktycznie inwestowalny globalny instrument.

### Struktura repozytorium

```
data/
├── raw/          # pobrane szeregi źródłowe (Damodaran, WIG, TBSP, GUS, NBP)
└── processed/    # ujednolicone dane (rok/miesiąc, PLN, realne)
src/
├── tax_engine.py  # kaskada podatkowa: IKE/IKZE/PPK/OKI, tax drag, kompensacja strat
├── data_loader.py # pobieranie i normalizacja danych: Damodaran, NBP, GUS, WIG, TBSP
├── simulation.py     (planowane)
└── scenarios.py       (planowane)
tests/            # testy jednostkowe
results/          # wyniki symulacji (CSV/JSON)
```

### Uruchomienie testów

```bash
pip install -r requirements.txt
pytest
```

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
