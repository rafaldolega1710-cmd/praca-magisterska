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
| NBP, tabela A | Kurs średni USD/PLN | Automatyczny (`fetch_nbp_usdpln_monthly`) — **od 1995 r.**: żywe REST API dla 2002+, roczne pliki archiwalne `static.nbp.pl` dla 1995–2001 |
| GUS, stat.gov.pl | CPI (inflacja), przeciętne miesięczne wynagrodzenie **w gospodarce narodowej** | **Zrzut, od 1950 r.** (`load_gus_cpi_history`, `load_gus_avg_wage_history`) — patrz niżej; wersje BDL API (2002+) zostają dostępne jako alternatywa |
| MSCI ACWI Index (curvo.eu) | Globalny indeks akcyjny (~2500 spółek, rynki rozwinięte + rozwijające się) — zastępuje S&P 500 + WIG | **Zrzut** (`data/raw/acwi_monthly.csv`) — patrz niżej, nie jest to wynik automatycznego zapytania |
| Ministerstwo Finansów, obligacjeskarbowe.pl | Marże serii obligacji EDO — zastępują TBSP.Index | **Zebrane skryptem** (`data/raw/edo_margins.csv`) ze statycznych stron ofertowych — patrz niżej |
| NBP, archiwum stóp procentowych | Stopa referencyjna NBP — formuła zastępcza tam, gdzie marża EDO nieznana | Automatyczny/zrzut (`data/raw/nbp_reference_rate.csv`, `fetch_nbp_reference_rate`) |
| GPW / stooq.pl | Indeks WIG | **Ręczny, opcjonalny** — nieużywany w głównym pipeline od czasu przejścia na globalny ETF; `load_wig_manual` pozostaje dostępny na potrzeby ewentualnego porównania z rynkiem polskim w rozdziale IV |
| GPW Benchmark | TBSP.Index | **Ręczny, opcjonalny** — analogicznie, `load_tbsp_manual` pozostaje dostępny na potrzeby porównania |

**Skąd wzięły się dane EDO i stopy referencyjnej NBP:**
- **Stopa referencyjna NBP** pochodzi z oficjalnego, w pełni maszynowo czytelnego archiwum `static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml` (bez zabezpieczeń antybotowych) — obejmuje okres od 26.02.1998 do dziś.
- **Marże EDO** zostały zebrane skryptem odpytującym ~150 statycznych stron ofertowych Ministerstwa Finansów (`obligacjeskarbowe.pl/oferta-obligacji/obligacje-10-letnie-edo/edoMMYY/`, gdzie `MMYY` to miesiąc/rok wykupu = miesiąc emisji + 10 lat) — strony te są server-rendered, więc dają się pobrać zwykłym zapytaniem HTTP. EDO wystartowało we wrześniu 2013 r., ale strony archiwalne przechowują konkretną wartość marży dopiero od stycznia 2017 r. — dla wcześniejszych miesięcy (wrzesień 2013 – grudzień 2016) i dla bieżącego roku, zanim GUS opublikuje jego CPI, stosowana jest formuła zastępcza: **stopa referencyjna NBP + 2 p.p.** (zgodnie z instrukcją — 2 p.p. to obowiązująca od dłuższego czasu marża EDO).

**Skąd wzięły się dane MSCI ACWI:** pierwsza wersja używała notowań ETF-u iShares MSCI ACWI (od marca 2008 — data powstania funduszu), ale start tuż przed globalnym kryzysem finansowym 2008 nadmiernie obciążał wynik symulacji wrażliwością na wybór akurat tego, szczególnie niekorzystnego okresu jako punktu startowego. Zastąpiono to samym **indeksem** MSCI ACWI (nie konkretnym funduszem), którego historia sięga grudnia 1987 r. — REST API dostawców danych giełdowych (Yahoo Finance, stooq, nasdaq.com, macrotrends.net) było zablokowane lub niedostępne z tego środowiska, więc dane w `data/raw/acwi_monthly.csv` pochodzą z wbudowanej funkcji eksportu CSV serwisu `curvo.eu` (`curvo.eu/backtest/en/market-index/msci-acwi`, waluta USD) — to zamierzony, legalny sposób pobrania danych z tej strony (przycisk „CSV” pod wykresem), nie obejście żadnego zabezpieczenia. To zrzut stanu na dzień pobrania; odświeżenie o kolejne miesiące wymaga powtórzenia tego samego pobrania.

**Ręczne pobranie WIG i TBSP.Index (opcjonalne, tylko do analiz porównawczych — żadne z nich nie jest już wymagane przez `build_processed_dataset`):**
1. WIG: `stooq.pl/q/d/l/?s=wig&i=m` w przeglądarce, zapisz jako `data/raw/wig.csv`.
2. TBSP.Index: pobierz historyczne notowania z serwisu GPW Benchmark (`gpwbenchmark.pl`) i zapisz jako `data/raw/tbsp.csv`.
3. Oba pliki obsługiwane są zarówno w formacie polskim stooq (`Data;Otwarcie;...;Zamkniecie;Wolumen`), jak i angielskim (`Date,Open,...,Close,Volume`) — `load_wig_manual`/`load_tbsp_manual` same rozpoznają format.

**Skąd wzięły się dane NBP sprzed 2002 r.:** żywe REST API NBP (`api.nbp.pl`) ma dane dopiero od 2002 r., ale NBP publikuje też roczne pliki archiwalne (`static.nbp.pl/dane/kursy/Archiwum/archiwum_tab_a_{rok}.xls`) sięgające technicznie do co najmniej 1985 r. — bez zabezpieczeń antybotowych. Ten moduł obsługuje je od 1995 r.: wcześniejszy układ kolumn (dane tygodniowe, kolumny wg nazw krajów w kolejności alfabetycznej) jest inny i nieobsługiwany. `fetch_nbp_usdpln_monthly` sam dobiera właściwe źródło dla każdego roku.

**Skąd wzięły się dane GUS od 1950 r. — i dlaczego to też poprawka, nie tylko wydłużenie:** `stat.gov.pl` publikuje w treści dwóch swoich stron gotowe tablice roczne od 1950 r. — "Roczne wskaźniki cen towarów i usług konsumpcyjnych" (z eksportem CSV) i "Przeciętne miesięczne wynagrodzenie w gospodarce narodowej" (tabela w treści strony). Przy weryfikacji długości historii okazało się, że zmienna BDL API użyta pierwotnie dla wynagrodzenia (`fetch_gus_avg_wage`, raportowana na poziomie powiatu) to **inna seria**, niż ta, do której faktycznie odwołuje się ustawa o IKE (art. 13a: limit liczony od wynagrodzenia "w gospodarce narodowej") — dla 2002 r. różnica to 2239,56 zł (BDL) vs 2133,21 zł (gospodarka narodowa, prawidłowa). Wynagrodzenia sprzed denominacji 1995-01-01 są w źródle w starych złotych — przeliczone (/10 000) dla spójności. CPI nie miało tego problemu (wartości identyczne z BDL dla lat pokrywających się), więc to czyste wydłużenie.

**Ważne ograniczenie zweryfikowane podczas implementacji:** po wydłużeniu kursu NBP (do 1995 r.) i danych GUS (do 1950 r.), **jedynym pozostałym ograniczeniem dolnym jest stopa referencyjna NBP — od 6 lutego 1998 r.** — używana w formule zastępczej dla EDO. To jednak nie luka techniczna: stopa referencyjna jako narzędzie polityki pieniężnej **nie istniała** przed powstaniem Rady Polityki Pieniężnej na mocy ustawy o NBP z 1997 r. (zweryfikowano) — twardy, uzasadniony instytucjonalnie limit, nie coś do dalszego wydłużania. Efektywne okno symulacji to teraz **luty 1998 – grudzień 2025 (~27,9 roku)**, w górę z ~24,6 roku.

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

`python -m src.scenarios` uruchamia wszystkie 4 scenariusze (macierz: 2 archetypy × z/bez wehikułów podatkowych, podrozdz. 3.4 pracy) w **3 wariantach alokacji akcje/obligacje (80/20, 60/40, 40/60)** — 12 przebiegów łącznie — na realnych danych historycznych (`build_processed_dataset()`, efektywne okno luty 1998 – grudzień 2025, ~27,9 roku — patrz sekcja "Dane historyczne") i zapisuje wyniki do `results/scenario_{kod}_equity{wariant}_monthly.csv` (pełna ścieżka miesięczna) oraz `results/summary.csv` (podsumowanie).

**Portfel ma dwie nogi: akcje (indeks MSCI ACWI) i obligacje (wyłącznie polskie detaliczne EDO)** — bez globalnych obligacji (Damodaran/UST10Y) i bez TBSP.Index, na wyraźną decyzję użytkownika. Testowanie kilku proporcji akcje/obligacje to bezpośrednia realizacja "elastycznej alokacji aktywów" z hipotezy badawczej pracy (patrz Wstęp).

**Metodologia horyzontu:** symulacja biegnie jedną, nieprzetworzoną historyczną sekwencją zwrotów od pierwszego do ostatniego dostępnego miesiąca — bez cyklicznego powielania danych i bez wielu okien startowych (Monte Carlo). Jeśli cel FIRE (25-krotność rocznych wydatków, aktualizowana co miesiąc wraz ze wzrostem wynagrodzeń) nie zostanie osiągnięty w tym oknie, wynik jawnie to raportuje (`fire_reached=False`) zamiast ekstrapolować nieistniejące dane.

**Realny wynik (uruchomienie 2026-08, efektywne okno luty 1998 – grudzień 2025, ~27,9 roku — patrz "Ważne ograniczenie" wyżej):**

| Scenariusz | Alokacja | Cel FIRE osiągnięty? | Lata do FIRE | Wartość portfela na koniec okna |
|---|---|---|---|---|
| A1 (Informatyk, z programami) | 80/20 | **Tak** | 18,8 | 34,6 mln zł |
| A1 | 60/40 | **Tak** | 18,8 | 31,5 mln zł |
| A1 | 40/60 | **Tak** | 20,5 | 28,5 mln zł |
| A2 (Informatyk, bez programów) | 80/20 | **Tak** | 18,8 | 33,6 mln zł |
| A2 | 60/40 | **Tak** | 19,7 | 30,5 mln zł |
| A2 | 40/60 | **Tak** | 21,5 | 27,7 mln zł |
| B1 (Rodzina 2+2, z programami) | 80/20 | Nie | — | 10,6 mln zł |
| B1 | 60/40 | Nie | — | 9,63 mln zł |
| B1 | 40/60 | Nie | — | 8,67 mln zł |
| B2 (Rodzina 2+2, bez programów) | 80/20 | Nie | — | 9,18 mln zł |
| B2 | 60/40 | Nie | — | 8,34 mln zł |
| B2 | 40/60 | Nie | — | 7,57 mln zł |

(Pełna precyzja liczb — w `results/summary.csv`. Wartości bezwzględne wyraźnie wyższe niż w poprzednim, krótszym oknie — dłuższy horyzont i dodatkowe ~4 lata realnego wzrostu wynagrodzeń w bazie GUS przekładają się na wyższy, dynamicznie rosnący cel FIRE i więcej czasu na akumulację.)

**Rodzina 2+2 (B1/B2) nie domyka się w żadnym z 3 wariantów alokacji** w dostępnym ~27,9-letnim oknie — spójne z niższą (20%) stopą oszczędności tego archetypu. Mimo to wzorzec jest identyczny jak u archetypu A: wyższy udział akcji daje wyższy portfel na koniec okna (80/20: 10,6 mln zł vs 40/60: 8,67 mln zł dla B1), a B1 (z ulgami) wyprzedza B2 (bez ulg) przy każdej alokacji (10,6 vs 9,18 mln zł przy 80/20) — ten sam mechanizm tarczy podatkowej, tyle że u wolniej oszczędzającego gospodarstwa widoczny wyłącznie w wartości portfela, bo żaden wariant nie dociera do mety w dostępnym oknie danych.

Dwie ilustracje bezpośrednio odpowiadające na pytania hipotezy badawczej:
- **Wartość tarczy podatkowej (A1 vs A2, ta sama alokacja):** przy 80/20 oba warianty osiągają cel w tym samym miesiącu (listopad 2016, 18,75 roku), ale A1 kończy z wyraźnie wyższym portfelem (34,6 vs 33,6 mln zł — różnica to niższy skumulowany podatek od dywidend i rebalancingu, widoczny wprost w kolumnach `cumulative_dividend_tax`/`cumulative_rebalancing_tax` w `results/summary.csv`). Przy niższym udziale akcji różnica staje się widoczna też w **czasie**: przy 60/40 A1 domyka się w 18,8 roku, A2 dopiero w 19,7 (10 miesięcy różnicy); przy 40/60 to już 20,5 vs 21,5 roku — pełny rok. Im mniej "pracy" wykonuje sama giełda, tym bardziej liczy się tarcza podatkowa.
- **Wpływ alokacji (80/20 vs 60/40 vs 40/60, ten sam scenariusz):** dla obu wariantów archetypu A wyższy udział akcji konsekwentnie przyspiesza dojście do celu i podnosi wartość końcową, kosztem większej zmienności portfela, której ta tabela nie pokazuje wprost — miesięczne ścieżki w `results/*_monthly.csv` pozwalają to zobaczyć. Archetyp B (niższa stopa oszczędności) nie domyka się w żadnym wariancie w dostępnym ~27,9-letnim oknie.

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
- **Praktyczna dolna granica pełnej symulacji to 6 lutego 1998 r.** (data ustanowienia stopy referencyjnej NBP, używanej w formule zastępczej dla EDO) — nie luka techniczna, tylko fakt instytucjonalny: ten instrument polityki pieniężnej po prostu nie istniał wcześniej. Ani indeks ACWI (1987+), ani kurs NBP (1995+, po wydłużeniu w tym etapie), ani dane GUS (1950+, po wydłużeniu i poprawce w tym etapie) nie są już wiążącym ograniczeniem — patrz sekcja "Dane historyczne" wyżej.
- **Roczne dane (GUS) rozbite na miesiące metodą równomiernej kapitalizacji geometrycznej** (`data_loader.annualize_to_monthly`) — każdy miesiąc danego roku dostaje tę samą stopę zwrotu; rzeczywista wewnątrzroczna zmienność i sezonowość nie są odwzorowane.
- **Noga akcyjna to jeden globalny indeks (MSCI ACWI), nie osobno rynek USA i Polski** — odejście od architektury z sekcji 2/3.2 pracy (na decyzję użytkownika). Pierwotnie użyto notowań ETF-u (od 2008 r.), zastąpione samym indeksem (od 1987 r.) po tym, jak start tuż przed kryzysem 2008 okazał się nadmiernie obciążać wynik.
- **Polska noga obligacji to EDO, nie TBSP.Index** — kolejne odejście od architektury z sekcji 2/3.2 pracy (na decyzję użytkownika). Dla 40 z 156 miesięcy istnienia EDO (wrzesień 2013 – grudzień 2016) oraz dla bieżącego, jeszcze niezakończonego roku kalendarzowego rzeczywista marża/CPI nie są znane, więc stosowana jest formuła zastępcza `stopa referencyjna NBP + 2 p.p.` zamiast faktycznej konstrukcji EDO — patrz sekcja "Dane historyczne" wyżej.
- **Portfel nie zawiera globalnych obligacji** — dwie nogi (akcje ACWI, obligacje EDO), nie trzy z pierwotnego briefu (akcje globalne + obligacje globalne + obligacje polskie). Uproszczenie na wyraźną decyzję użytkownika; obniża dywersyfikację geograficzną części dłużnej portfela.
