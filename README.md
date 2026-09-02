# praca-magisterska

Repozytorium robocze do pracy magisterskiej.

## FIRE-PL Simulator

Deterministyczny, miesięczny model symulacji akumulacji **i dekumulacji** kapitału w ramach koncepcji FIRE (Financial Independence, Retire Early) w warunkach polskiego systemu podatkowo-emerytalnego. Testuje 4 scenariusze akumulacji (2 archetypy gospodarstw domowych × z/bez wykorzystania wehikułów podatkowych IKE/IKZE/PPK/OKI, każdy w 3 wariantach alokacji), na wielu historycznych oknach startowych, oraz fazę wypłat regułą 4% — i stanowi podstawę rozdziału IV pracy magisterskiej ("Studium przypadku realizacji założeń FIRE na polskim rynku kapitałowym"). Metodologia opisana jest szczegółowo w rozdziale III pracy (podrozdziały 3.1–3.4). Wyniki dostępne też jako [interaktywny kalkulator](#interaktywny-kalkulator) (`kalkulator.html`).

### Status

- **Silnik podatkowy (`src/tax_engine.py`)** — zaimplementowany i przetestowany. Kaskadowa alokacja nadwyżki budżetowej (PPK → IKZE → IKE → OKI → rachunek standardowy), mechanika PPK, kompensacja strat kapitałowych, harmonogram zwrotu ulgi IKZE.
- **Pipeline danych historycznych (`src/data_loader.py`)** — zaimplementowany i przetestowany. Automatyczne pobieranie (Damodaran, NBP, GUS) zweryfikowane na żywo; WIG i TBSP.Index (oba opcjonalne) wymagają ręcznego pobrania pliku (patrz niżej).
- **Pętla symulacyjna i scenariusze (`src/simulation.py`, `src/scenarios.py`)** — zaimplementowane i przetestowane. Faza akumulacji liczona jest teraz **na wielu historycznych oknach startowych** (`run_rolling_accumulation`), nie jedną ścieżką — patrz sekcja "Symulacja i scenariusze".
- **Faza dystrybucji / dekumulacja (`src/decumulation.py`)** — zaimplementowana i przetestowana. Reguła 4% + wskaźnik przetrwania na wielu oknach historycznych (test SORR) — patrz sekcja "Dekumulacja".
- **Interaktywny kalkulator (`kalkulator.html`, `src/build_calculator_data.py`)** — zaimplementowany. Samodzielna strona HTML (bez zależności zewnętrznych poza Google Fonts) z checkboxami IKE/IKZE/PPK/OKI, wyborem archetypu i alokacji — patrz sekcja "Interaktywny kalkulator".

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

**Ważne ograniczenie zweryfikowane podczas implementacji:** po wydłużeniu kursu NBP (do 1995 r.) i danych GUS (do 1950 r.), **jedynym pozostałym ograniczeniem dolnym jest stopa referencyjna NBP — od 6 lutego 1998 r.** — używana w formule zastępczej dla EDO. To jednak nie luka techniczna: stopa referencyjna jako narzędzie polityki pieniężnej **nie istniała** przed powstaniem Rady Polityki Pieniężnej na mocy ustawy o NBP z 1997 r. (zweryfikowano) — twardy, uzasadniony instytucjonalnie limit, nie coś do dalszego wydłużania. Efektywne okno symulacji to **luty 1998 – dziś** (rośnie z każdym miesiącem wraz z nowymi danymi NBP/GUS; ~27,9 roku przy pierwszym uruchomieniu tego etapu, ~28,5 roku — luty 1998 – lipiec 2026 — przy uruchomieniu wyników w sekcjach "Symulacja i scenariusze"/"Dekumulacja" niżej), w górę z ~24,6 roku przed Etapem 3.x.

### Struktura repozytorium

```
data/
├── raw/                # pobrane szeregi źródłowe (Damodaran, WIG, TBSP, GUS, NBP)
├── processed/          # ujednolicone dane (rok/miesiąc, PLN, realne)
└── calculator_data.json  # prekalkulowana siatka wyników (wejście dla kalkulator.html)
src/
├── tax_engine.py          # kaskada podatkowa: IKE/IKZE/PPK/OKI, tax drag, kompensacja strat
├── data_loader.py         # pobieranie i normalizacja danych: Damodaran, NBP, GUS, ACWI, EDO
├── simulation.py          # miesięczna pętla symulacyjna (akumulacja), run_rolling_accumulation
├── scenarios.py           # archetypy A/B, scenariusze A1/A2/B1/B2, run_all_scenarios()
├── decumulation.py        # faza dystrybucji: reguła 4%, run_rolling_decumulation
└── build_calculator_data.py  # generuje data/calculator_data.json dla kalkulatora.html
kalkulator.html   # interaktywny kalkulator (samodzielna strona HTML)
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

**Metodologia horyzontu (Etap 4 — zmiana względem wcześniejszych etapów):** każda kombinacja scenariusz × alokacja liczona jest teraz **dwiema metodami naraz**:
- **`run_rolling_accumulation`** (metoda główna, wzorowana na Bengenie/Trinity Study, ta sama idea co w kalkulatorze [stockbroker.pl](https://stockbroker.pl/kalkulator-wolnosci-finansowej/)) — uruchamia pełną symulację startując z **każdego** miesiąca w danych co 6 miesięcy (`step_months=6`, 57 punktów startowych z ~342-miesięcznego zbioru — kompromis między rozdzielczością a czasem obliczeń: pełna rozdzielczość miesięczna to ~15 s na kombinację, co 6. miesiąc — ~2–4 s, a przy 12 kombinacjach × 2 metody to różnica idąca w minuty), aż do końca dostępnych danych. Zbiera lata do FIRE z okien, które zdążyły osiągnąć cel, i zwraca **medianę** ("przeciętny" wynik), **min** ("szczęśliwy" wynik) oraz **maks. wśród okien, które cel osiągnęły** ("pechowy" wynik), a także **% okien, którym w ogóle zabrakło czasu** do końca danych.
- **`run_simulation`** (metoda pomocnicza, jak w Etapach 1–3) — jedna, nieprzetworzona historyczna ścieżka od pierwszego do ostatniego dostępnego miesiąca, zapisywana do `results/scenario_{kod}_equity{wariant}_monthly.csv` — użyteczna do wykresów pełnej trajektorii portfela, ale wrażliwa na wybór akurat tego jednego okresu jako punktu startowego.

**Realny wynik metody głównej (rolling, uruchomienie 2026-09, 57 okien startowych na kombinację, dane luty 1998 – lipiec 2026):**

| Scenariusz | Alokacja | Cel osiągnięty w % okien | Mediana | Szczęśliwy (min) | Pechowy (maks.) |
|---|---|---|---|---|---|
| A1 (Informatyk, z programami) | 80/20 | 40% | 17,8 lat | 14,8 lat | 18,8 lat |
| A1 | 60/40 | 35% | 19,1 lat | 17,3 lat | 20,4 lat |
| A1 | 40/60 | 26% | 20,6 lat | 19,3 lat | 22,4 lat |
| A2 (Informatyk, bez programów) | 80/20 | 39% | 18,1 lat | 15,3 lat | 19,0 lat |
| A2 | 60/40 | 33% | 19,7 lat | 17,8 lat | 21,2 lat |
| A2 | 40/60 | 25% | 21,2 lat | 19,8 lat | 22,9 lat |
| B1 (Rodzina 2+2, z programami) | 80/20 | 0% | — | — | — |
| B1 | 60/40 | 0% | — | — | — |
| B1 | 40/60 | 0% | — | — | — |
| B2 (Rodzina 2+2, bez programów) | 80/20 | 0% | — | — | — |
| B2 | 60/40 | 0% | — | — | — |
| B2 | 40/60 | 0% | — | — | — |

(Pełna precyzja liczb — w `results/summary.csv`, kolumny `years_to_fire_median/min/max`, `rolling_pct_not_reached`. Ten sam plik ma też `portfolio_at_fire_median/min/max` i `age_at_fire_median/min/max` — dla A1 80/20 mediana kapitału na koniec akumulacji to ok. 6,8 mln zł przy medianie wieku 47,8 lat (start oszczędzania: 30 lat) — patrz sekcja "Dekumulacja" niżej, gdzie ten wiek bezpośrednio decyduje o dostępności IKE/IKZE/PPK w fazie wypłat.)

**Ważne o kolumnie "cel osiągnięty w % okien":** dla archetypu A wynosi zaledwie 25–40%, mimo że pojedyncza ścieżka historyczna (metoda pomocnicza, niżej) *zawsze* dochodzi do celu w tym samym zbiorze danych. To nie jest sprzeczność, tylko efekt ograniczonej długości danych: mediana czasu do FIRE (~18–21 lat) to prawie dwie trzecie całego ~28-letniego okna (1998–2026), więc każde okno startowe później niż mniej więcej w pierwszej jednej trzeciej danych **fizycznie nie ma już dość miesięcy do końca danych**, żeby zdążyć — niezależnie od tego, jak dobre byłyby zwroty. To ograniczenie dostępnych danych, nie prognoza złych zwrotów rynkowych; opisane wprost też w kalkulatorze (`kalkulator.html`).

**Rodzina 2+2 (B1/B2) nie domyka się w żadnym z testowanych okien startowych i żadnej z 3 alokacji** — spójne z niższą (20%) stopą oszczędności tego archetypu i z wynikiem metody pomocniczej (pojedyncza ścieżka, niżej), gdzie też nie dociera do celu w dostępnym oknie.

Dwie ilustracje bezpośrednio odpowiadające na pytania hipotezy badawczej (na medianach z metody rolling):
- **Wartość tarczy podatkowej (A1 vs A2, ta sama alokacja):** przy 80/20 A1 domyka się w 17,8 roku (mediana) wobec 18,1 roku dla A2; przy 60/40 to 19,1 vs 19,7; przy 40/60 — 20,6 vs 21,2. Różnica rośnie wraz ze spadkiem udziału akcji — im mniej "pracy" wykonuje sama giełda, tym bardziej liczy się tarcza podatkowa (niższy skumulowany podatek od dywidend i rebalancingu, widoczny w kolumnach `single_path_cumulative_*_tax` metody pomocniczej).
- **Wpływ alokacji (80/20 vs 60/40 vs 40/60, ten sam scenariusz):** dla obu wariantów archetypu A wyższy udział akcji konsekwentnie przyspiesza medianę dojścia do celu i **podnosi odsetek okien, które w ogóle zdążyły** (A1: 40% przy 80/20 vs 26% przy 40/60) — bo krótszy oczekiwany czas do FIRE zostawia więcej okien startowych z wystarczającym zapasem danych. Archetyp B nie domyka się w żadnym wariancie.

**Metoda pomocnicza (pojedyncza historyczna ścieżka 1998–2025, ~27,9 roku) — dla porównania:**

| Scenariusz | Alokacja | Cel osiągnięty? | Lata do FIRE | Wartość portfela na koniec okna |
|---|---|---|---|---|
| A1 | 80/20 | Tak | 18,8 | 34,6 mln zł |
| A1 | 60/40 | Tak | 18,8 | 31,5 mln zł |
| A1 | 40/60 | Tak | 20,5 | 28,5 mln zł |
| A2 | 80/20 | Tak | 18,8 | 33,6 mln zł |
| A2 | 60/40 | Tak | 19,7 | 30,5 mln zł |
| A2 | 40/60 | Tak | 21,5 | 27,7 mln zł |
| B1 | 80/20 | Nie | — | 10,6 mln zł |
| B1 | 60/40 | Nie | — | 9,63 mln zł |
| B1 | 40/60 | Nie | — | 8,67 mln zł |
| B2 | 80/20 | Nie | — | 9,18 mln zł |
| B2 | 60/40 | Nie | — | 8,34 mln zł |
| B2 | 40/60 | Nie | — | 7,57 mln zł |

**Założenia modelu (`SimulationAssumptions`, `src/simulation.py`) — jawnie udokumentowane uproszczenia:**

| Założenie | Wartość | Uzasadnienie |
|---|---|---|
| Wiek na starcie oszczędzania | 30 lat (oba archetypy) | `Archetype.start_age` — porównywalne scenariusze; decyduje o wieku w chwili FIRE, a ten z kolei o dostępności IKE/IKZE/PPK w fazie wypłat (patrz "Dekumulacja") |
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

### Dekumulacja

Etap 4 dodaje **fazę dystrybucji** (`src/decumulation.py`), dotąd całkowicie nietestowaną — poprzednie etapy kończyły się w momencie osiągnięcia celu FIRE, nie sprawdzając, czy zgromadzony kapitał faktycznie *przetrwa* wypłaty. To druga połowa hipotezy badawczej pracy (podrozdz. 1.3, 4.3): "naiwne FIRE naraża na ryzyko przedwczesnego wyczerpania kapitału" (sequence of returns risk, SORR).

`python -m src.decumulation` uruchamia **regułę 4%** (Bengen 1994 / Trinity Study 1998) na portfelu **znormalizowanym do 1.0** (= dokładnie równym celowi FIRE w chwili przejścia na wypłaty — test jest z natury niezależny od poziomu dochodów), testowanej na wielu historycznych oknach startowych, co 6 miesięcy. Wypłata w pierwszym miesiącu to `4%/12` wartości startowej; każdego stycznia jest podwyższana o zrealizowaną inflację GUS z poprzedniego roku (klasyczna reguła Bengena: stała kwota realna, nie stały % aktualnego salda). Zapisuje `results/decumulation_summary.csv`.

**Zaprojektowana jako niezależna od KONKRETNEGO okna akumulacji** — pytanie brzmi "gdyby ktoś przeszedł na FIRE w miesiącu M z portfelem 25× rocznych wydatków, czy przetrwałby N lat wypłat", nie "co się stanie zaraz po zakończeniu konkretnego okna akumulacji" (to standardowe podejście Bengena/Trinity — te dwa pytania dają różne, komplementarne informacje, ale tylko pierwsze faktycznie mierzy SORR).

**Nowość: bramkowanie wiekowe IKE/IKZE/PPK.** Polskie prawo wiąże bezpodatkowy dostęp do tych kont z wiekiem, nie z samym faktem osiągnięcia celu FIRE — IKE i PPK dopiero od 60. r.ż., IKZE (ryczałt 10%) dopiero od 65. r.ż.; OKI i rachunek standardowy są dostępne zawsze. Jeśli ktoś (typowy scenariusz "naiwnego FIRE" z hipotezy pracy) osiąga cel FIRE przed 60/65 r.ż., przez lata do tego wieku fizycznie nie ma bezkarnego dostępu do zablokowanych kont — nawet jeśli portfel jako CAŁOŚĆ byłby wystarczający. Wiek na starcie wypłat i podział portfela na konta pochodzą z pojedynczej, ciągłej ścieżki historycznej dla danej kombinacji (archetyp × konta × alokacja × stopa oszczędności) — traktowane jak stały parametr scenariusza, tak jak "wiek emeryta" w klasycznych badaniach Bengena/Trinity, nie wyprowadzane osobno dla każdego z wielu testowanych okien wypłat.

Moduł rozróżnia teraz dwa tryby porażki: **`capital_exhausted`** (klasyczne wyczerpanie kapitału, jak w Bengenie) i **`liquidity_gap`** (kapitał jako całość wciąż istnieje, ale jest zablokowany wiekiem — portfel "przeżyłby", gdyby dało się do niego dowolnie sięgnąć). To bezpośredni test realnego ryzyka "FIRE przez IKE/IKZE w Polsce", nie tylko klasycznego SORR. Świadome uproszczenie: zablokowane środki są po prostu niedostępne w tym modelu (nie modelujemy decyzji o wypłacie z karą — utraty dopłat PPK, podatku od zysku IKE, przejścia IKZE na skalę PIT) — bardziej konserwatywne niż rzeczywistość, nie zaniża ryzyka.

**Horyzonty do 25 lat (nie klasycznych 30) — policzone, nie zgadywane:** dane obejmują ~28,5 roku (342 miesiące); 30-letni horyzont Trinity Study nie zmieściłby się w **żadnym** oknie startowym (zabrakłoby 18 miesięcy nawet zaczynając od pierwszego dostępnego miesiąca), 35/40 lat tym bardziej. 10/15/20/25 lat to horyzonty, które faktycznie mieszczą się w danych (odpowiednio 38, 28, 18 i 8 okien przy kroku 6 miesięcy) — 25 lat z bardzo małym zapasem, więc ten wynik trzeba czytać z odpowiednią ostrożnością.

**Bazowy wynik bez bramkowania wiekowego** (`results/decumulation_summary.csv`, portfel jako jedna pula, reprezentuje "gdyby wiek nie miał znaczenia"):

| Alokacja | Horyzont | Okien | Wskaźnik przetrwania | Saldo końcowe (mediana) | Najgorszy przypadek (wśród ocalałych) |
|---|---|---|---|---|---|
| 80/20 | 10 lat | 38 | 100% | 139% celu | 43% |
| 80/20 | 15 lat | 28 | 100% | 160% celu | 37% |
| 80/20 | 20 lat | 18 | 100% | 173% celu | 13% |
| 80/20 | 25 lat | 8 | **75%** | 83% celu | 28% |
| 60/40 | 10–20 lat | 38/28/18 | 100% | 137–172% celu | 57–65% |
| 60/40 | 25 lat | 8 | 100% | 133% celu | 49% |
| 40/60 | 10–25 lat | 38/28/18/8 | 100% | 134–174% celu | 92–117% |

**Ten sam test, z realistycznym bramkowaniem wiekowym, dla konkretnego scenariusza** (Rodzina 2+2, wszystkie konta, alokacja 80/20 — im wyższa stopa oszczędności, tym wcześniej FIRE i tym dłuższa luka do 60/65 lat):

| Stopa oszczędności | Wiek na starcie wypłat | Horyzont | Wskaźnik przetrwania | Porażki: brak płynności / wyczerpanie |
|---|---|---|---|---|
| 70% | 42,25 lat | 10 / 15 lat | 100% / 100% | 0 / 0 |
| 70% | 42,25 lat | 20 lat | **88,9%** (16/18) | **2** / 0 |
| 70% | 42,25 lat | 25 lat | **75%** (6/8) | **2** / 0 |
| 80% | 37,08 lat | 10 / 15 lat | 100% / 100% | 0 / 0 |
| 80% | 37,08 lat | 20 lat | **88,9%** (16/18) | **2** / 0 |
| 80% | 37,08 lat | 25 lat | **62,5%** (5/8) | **3** / 0 |

**To jest sedno tego, co dodaje bramkowanie wiekowe:** przy 20-letnim horyzoncie wskaźnik przetrwania spada z bazowych 100% do 88,9% — dwa okna, które w naiwnej (bez wieku) analizie SORR w ogóle by nie zawiodły, tutaj zawodzą, bo w wieku 37–42 lat żadne z kont IKE/PPK (60 lat) ani IKZE (65 lat) jeszcze nie jest odblokowane, więc wypłaty idą wyłącznie z OKI i rachunku standardowego. **Wszystkie zaobserwowane porażki w całej siatce kalkulatora (1612 kombinacji archetyp × konta × alokacja × stopa × horyzont) są typu `liquidity_gap`, zero typu `capital_exhausted`** — w tym zbiorze danych reguła 4% nigdy nie wyczerpuje kapitału naprawdę, ale u młodych "naiwnych FIRE" (agresywna stopa oszczędności, wczesne odejście z pracy) realnie zabraknie płynnych środków, mimo że portfel jako całość by wystarczył. To bezpośrednie potwierdzenie hipotezy badawczej pracy w jej dosłownym brzmieniu: ryzyko nie leży w rynku, tylko w konstrukcji prawnej kont.

Zastrzeżenia: (1) to nie jest "reguła 4% jest bezpieczna" w sensie klasycznego badania Bengena (tam horyzont to 30 lat, tu maksymalnie 25); (2) im dłuższy horyzont, tym mniej niezależnych okien testowych (8 dla 25 lat) i tym większe ryzyko, że wynik odzwierciedla akurat te konkretne dekady polskiej historii, nie ogólną prawidłowość; (3) wiek i podział kont są reprezentatywne (z jednej, ciągłej ścieżki), nie wyprowadzone osobno dla każdego testowanego okna wypłat — patrz "Ograniczenia modelu".

### Interaktywny kalkulator

`kalkulator.html` — samodzielna, interaktywna strona HTML (bez zależności zewnętrznych poza Google Fonts, otwiera się bezpośrednio w przeglądarce, bez serwera) — pozwala **klikaniem** wybrać archetyp gospodarstwa, zaznaczyć, z których kont podatkowych (IKE/IKZE/PPK/OKI) korzysta, ustawić suwakiem **stopę oszczędności (10%–90%, co 10 p.p.)** i wybrać alokację akcje/obligacje, żeby na żywo zobaczyć medianę i zakres (szczęśliwy/pechowy przypadek) lat do FIRE, kapitał, z jakim poszczególne okna kończyły akumulację, oraz — w osobnej sekcji, dla horyzontu 10/15/20/25 lat — wskaźnik przetrwania reguły 4% **z uwzględnieniem wieku dostępu do IKE/IKZE/PPK**.

**Architektura: prekalkulowana siatka wyników + statyczna strona z lookupem**, ten sam wzorzec co kalkulator [stockbroker.pl](https://stockbroker.pl/kalkulator-wolnosci-finansowej/) (który też nie liczy na żywo, tylko odpytuje wcześniej policzone współczynniki) — unika utrzymywania dwóch kopii logiki symulacyjnej (Python + JavaScript), które mogłyby się rozjechać. `python -m src.build_calculator_data` uruchamia pełną siatkę: 648 kombinacji akumulacji (2 archetypy × [8 lub 16 kombinacji kont, zależnie od uprawnienia do PPK] × 3 alokacje × 9 stóp oszczędności) i — dla każdej z nich, która na ilustracyjnej ciągłej ścieżce historycznej dochodzi do FIRE — 4 kombinacje dekumulacji (horyzonty 10/15/20/25 lat), i zapisuje `data/calculator_data.json`, osadzony bezpośrednio w `kalkulator.html`. Suwak stopy oszczędności **nie interpoluje** między policzonymi wartościami — zawsze "przeskakuje" do najbliższego z 9 punktów siatki (10/20/…/90%), zgodnie z architekturą lookupu.

**Stopa oszczędności jako niezależna od archetypu oś, nie jego stała cecha:** `Archetype.savings_rate` w `scenarios.py` (50% dla Informatyka, 20% dla Rodziny) pozostaje domyślnym założeniem dla scenariuszy badawczych A1/A2/B1/B2 (`results/summary.csv`) — ale w kalkulatorze użytkownik może dowolnie zmieniać stopę oszczędności dla każdego archetypu, niezależnie od tego założenia. `build_calculator_data.py` generuje wariant archetypu przez `dataclasses.replace(archetype, savings_rate=sr)` dla każdej z 9 wartości — dochód netto archetypu zostaje bez zmian, zmienia się tylko, jaki jego procent trafia na inwestycje (a symetrycznie: jaki zostaje na wydatki, czyli mianownik celu FIRE). Żadna zmiana w `simulation.py` nie była do tego potrzebna.

**Dekumulacja sprzężona z kombinacją, nie tylko z alokacją:** od kiedy fazę wypłat bramkuje wiek dostępu do IKE/IKZE/PPK (patrz sekcja "Dekumulacja" niżej), potrzebny jest wiek w chwili FIRE i podział portfela na konta — a oba zależą od tego, KTÓRE konta były włączone i z jaką stopą oszczędności. Te dwie wartości pochodzą z pojedynczej, ciągłej ścieżki historycznej dla danej kombinacji (nie z konkretnego okna rolling) — jeśli ta ścieżka nie dochodzi do FIRE, kombinacja jest pomijana w siatce dekumulacji, o czym kalkulator informuje wprost zamiast pokazywać puste pole.

**PPK dla archetypu bez uprawnienia (Informatyk B2B):** checkbox jest wyszarzony i wymuszony na "wyłączone" — kanonizacja klucza wyszukiwania w JS pomija PPK dla takiego archetypu niezależnie od stanu checkboxa, spójnie z tym, że `run_simulation` i tak ignoruje PPK, gdy `archetype.ppk_eligible=False` (patrz `tax_engine.allocate_monthly_surplus`).

**Jak model projektuje dochód wstecz, skoro nie zna rzeczywistych zarobków archetypu sprzed lat:** dla okna startującego np. 15 lat temu model nie twierdzi, że "Informatyk B2B zarabiał wtedy dokładnie X zł" — takich danych po prostu nie ma (nie istnieje archiwalna, granularna seria zarobków dla wymyślonego profilu). Zamiast tego (`simulation.run_simulation`, `base_wage = data["avg_gross_wage_pln"].iloc[0]` po przycięciu do okna): dzisiejszy dochód netto archetypu (np. 19 000 zł dla Informatyka) jest **zakotwiczony w pierwszym miesiącu tego konkretnego okna startowego**, a potem w każdym kolejnym miesiącu skalowany współczynnikiem `wage_index = ówczesne_przeciętne_wynagrodzenie_GUS / przeciętne_wynagrodzenie_GUS_w_miesiącu_startowym`. Innymi słowy: symulacja testuje "osobę o dzisiejszym profilu dochodowym, której kariera **rosłaby w tym samym tempie procentowym**, w jakim faktycznie rosło przeciętne wynagrodzenie w gospodarce narodowej w tamtym okresie" — jednocześnie stosując do jej portfela faktyczne, historyczne zwroty ACWI/EDO/kursu USD-PLN z tych samych miesięcy. To test wrażliwości na sekwencję zwrotów rynkowych i tempo wzrostu płac wzięte z prawdziwej historii (SORR), a nie próba zrekonstruowania czyjejś rzeczywistej pensji sprzed lat — dokładnie ten sam mechanizm już wcześniej stał za medianą/min/maks. w rolling-window akumulacji (sekcja "Symulacja i scenariusze"), suwak stopy oszczędności niczego tu nie zmienia.

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
- **Rolling-window akumulacja próbkowana co 6 miesięcy** (`step_months=6`), nie dla każdego pojedynczego miesiąca — kompromis wydajnościowy (patrz sekcja "Symulacja i scenariusze"). Przy 342-miesięcznym zbiorze to 57 okien na kombinację zamiast ~342 — wystarczające do sensownej mediany/zakresu, ale gęstsze próbkowanie dałoby nieznacznie inne (nie systematycznie odchylone) wartości brzegowe.
- **Wysoki odsetek okien rolling "bez wystarczającego czasu"** (25–75% dla archetypu A, 100% dla archetypu B) to artefakt ograniczonej długości polskich danych (~28 lat), nie sygnał złych zwrotów rynkowych — patrz zastrzeżenie w sekcji "Symulacja i scenariusze". Klasyczne badania Bengena/Trinity dysponują ~100-letnią historią USA i tego problemu praktycznie nie mają.
- **Dekumulacja bramkuje wiekiem dostęp do IKE/IKZE/PPK (w kalkulatorze), ale bez modelowania podatku/kar przy wcześniejszej wypłacie** — zablokowane konto jest po prostu niedostępne, nie "dostępne z karą" (utrata dopłat PPK, podatek od zysku IKE, przejście IKZE na skalę PIT) — świadomie konserwatywne uproszczenie, patrz sekcja "Dekumulacja". `results/decumulation_summary.csv` (uruchomienie `python -m src.decumulation` bez archetypu) to nadal wersja bez bramkowania wiekowego — czysty test SORR na połączonym saldzie, użyteczny jako baseline "gdyby wiek nie miał znaczenia".
- **Horyzonty dekumulacji skrócone do 10/15/20/25 lat** (nie klasycznych 30 z Trinity Study) — ~28,5-letnie dane fizycznie nie mieszczą pełnego 30-letniego okna. Im dłuższy testowany horyzont, tym mniej niezależnych okien startowych (zaledwie 8 dla 25 lat) i tym mniejsza pewność, że wynik uogólnia się poza konkretne przetestowane dekady — wynik dla 25 lat należy traktować z odpowiednią ostrożnością.
- **Reprezentatywny wiek i podział kont w dekumulacji pochodzą z JEDNEJ, ciągłej ścieżki historycznej** (nie z konkretnego okna rolling akumulacji) — traktowane jak stały parametr scenariusza (analogicznie do "wieku emeryta" w klasycznych badaniach Bengena/Trinity), nie wyprowadzane osobno dla każdego z wielu testowanych okien wypłat. Każde konto w dekumulacji rośnie też tą samą, wspólną stopą equity/bond co cały portfel — brak realnego różnicowania alokacji między kontami.
