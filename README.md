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

(Pełna precyzja liczb — w `results/summary.csv`, kolumny `years_to_fire_median/min/max`, `rolling_pct_not_reached`.)

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

**Zaprojektowana jako niezależna od fazy akumulacji** — pytanie brzmi "gdyby ktoś przeszedł na FIRE w miesiącu M z portfelem 25× rocznych wydatków, czy przetrwałby N lat wypłat", nie "co się stanie zaraz po zakończeniu konkretnego okna akumulacji" (to standardowe podejście Bengena/Trinity — te dwa pytania dają różne, komplementarne informacje, ale tylko pierwsze faktycznie mierzy SORR).

**Horyzonty skrócone do 10/15/20 lat (nie klasycznych 30) — policzone, nie zgadywane:** dane obejmują ~28 lat (342 miesiące); 30-letni horyzont Trinity Study nie zmieściłby się w **żadnym** oknie startowym (zero kompletnych testów). 10/15/20 lat to horyzonty, które faktycznie mieszczą się z sensowną liczbą okien (odpowiednio 38, 28, 18 przy kroku 6 miesięcy).

**Świadome uproszczenie zakresu:** portfel liczony jest jako **jedna, połączona całość** — bez podziału na konta IKE/IKZE/PPK/OKI/standard, bez modelowania kolejności wypłat z poszczególnych kont, kar za wcześniejsze wypłaty z PPK/IKZE ani podatku przy wypłacie z rachunku standardowego. Sam spec (`fire_model_spec.md`) nazywa fazę dekumulacji "osobnym modelem" — tu dostarczamy dobrze uzasadnioną odpowiedź na pytanie o SORR (przetrwa/nie przetrwa portfel jako całość), nie pełną replikę mechaniki podatkowej fazy wypłat.

**Realny wynik (uruchomienie 2026-09, reguła 4%, dane luty 1998 – lipiec 2026):**

| Alokacja | Horyzont | Okien testowanych | Wskaźnik przetrwania | Saldo końcowe (mediana) | Saldo końcowe (najgorszy przypadek) |
|---|---|---|---|---|---|
| 80/20 | 10 lat | 38 | 100% | 139% celu startowego | 43% |
| 80/20 | 15 lat | 28 | 100% | 160% celu startowego | 37% |
| 80/20 | 20 lat | 18 | 100% | 173% celu startowego | 13% |
| 60/40 | 10 lat | 38 | 100% | 137% celu startowego | 65% |
| 60/40 | 15 lat | 28 | 100% | 150% celu startowego | 71% |
| 60/40 | 20 lat | 18 | 100% | 172% celu startowego | 57% |
| 40/60 | 10 lat | 38 | 100% | 134% celu startowego | 92% |
| 40/60 | 15 lat | 28 | 100% | 146% celu startowego | 105% |
| 40/60 | 20 lat | 18 | 100% | 174% celu startowego | 100% |

(Pełna precyzja liczb, wraz z medianą najgłębszego obsunięcia po drodze — w `results/decumulation_summary.csv`.) **Reguła 4% przetrwała wszystkie testowane okna, na wszystkich alokacjach i horyzontach** w dostępnym oknie polskich danych — nawet w najgorszym przetestowanym przypadku (80/20, 20 lat) portfel skończył z 13% wartości startowej, nie zerem. Ma to jednak dwie ważne zastrzeżenia: (1) to nie jest to samo co "reguła 4% jest bezpieczna" w sensie klasycznego badania Bengena (tam horyzont to 30 lat, tu maksymalnie 20 — patrz wyżej), (2) im dłuższy horyzont, tym mniej niezależnych okien testowych (18 dla 20 lat) i tym większe ryzyko, że wynik odzwierciedla akurat te konkretne dekady polskiej historii rynkowej, a nie ogólną prawidłowość.

### Interaktywny kalkulator

`kalkulator.html` — samodzielna, interaktywna strona HTML (bez zależności zewnętrznych poza Google Fonts, otwiera się bezpośrednio w przeglądarce, bez serwera) — pozwala **klikaniem** wybrać archetyp gospodarstwa, zaznaczyć, z których kont podatkowych (IKE/IKZE/PPK/OKI) korzysta, i wybrać alokację akcje/obligacje, żeby na żywo zobaczyć medianę i zakres (szczęśliwy/pechowy przypadek) lat do FIRE oraz — w osobnej sekcji — wskaźnik przetrwania reguły 4% na wybranym horyzoncie dekumulacji.

**Architektura: prekalkulowana siatka wyników + statyczna strona z lookupem**, ten sam wzorzec co kalkulator [stockbroker.pl](https://stockbroker.pl/kalkulator-wolnosci-finansowej/) (który też nie liczy na żywo, tylko odpytuje wcześniej policzone współczynniki) — unika utrzymywania dwóch kopii logiki symulacyjnej (Python + JavaScript), które mogłyby się rozjechać. `python -m src.build_calculator_data` uruchamia pełną siatkę (72 kombinacje akumulacji: 2 archetypy × [8 lub 16 kombinacji kont, zależnie od uprawnienia do PPK] × 3 alokacje, plus 9 kombinacji dekumulacji: 3 alokacje × 3 horyzonty) i zapisuje `data/calculator_data.json` (~22 KB), który jest osadzony bezpośrednio w `kalkulator.html`.

**PPK dla archetypu bez uprawnienia (Informatyk B2B):** checkbox jest wyszarzony i wymuszony na "wyłączone" — kanonizacja klucza wyszukiwania w JS pomija PPK dla takiego archetypu niezależnie od stanu checkboxa, spójnie z tym, że `run_simulation` i tak ignoruje PPK, gdy `archetype.ppk_eligible=False` (patrz `tax_engine.allocate_monthly_surplus`).

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
- **Dekumulacja liczona na połączonym saldzie portfela**, bez podziału na konta IKE/IKZE/PPK/OKI/standard i bez modelowania podatku/kar przy wypłacie z poszczególnych kont — patrz sekcja "Dekumulacja".
- **Horyzonty dekumulacji skrócone do 10/15/20 lat** (nie klasycznych 30 z Trinity Study) — ~28-letnie dane fizycznie nie mieszczą pełnego 30-letniego okna. Im dłuższy testowany horyzont, tym mniej niezależnych okien startowych (18 dla 20 lat) i tym mniejsza pewność, że wynik uogólnia się poza konkretne przetestowane dekady.
