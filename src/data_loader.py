"""Pobieranie i normalizacja historycznych danych rynkowych oraz
makroekonomicznych dla modelu FIRE-PL (podrozdz. 3.2 pracy / sekcja 2
`fire_model_spec.md`).

Zweryfikowana (nie zakładana) dostępność źródeł -- patrz plan Etapu 2:
- Damodaran `histretSP.xls` (10-letnie obligacje skarbowe USA) -- pobierany
  automatycznie, ale **nie jest już częścią `build_processed_dataset`**:
  na wyraźną decyzję użytkownika model nie ma globalnej nogi obligacyjnej,
  portfel to wyłącznie akcje (ACWI) i polskie obligacje detaliczne (EDO).
  Funkcje `fetch_damodaran_returns`/`_parse_damodaran_xls` zostają dostępne
  i przetestowane na wypadek przyszłego porównania.
- NBP kursów średnich USD/PLN -- pobierany automatycznie z dwóch źródeł:
  żywego REST API dla 2002+ (twardy limit tego konkretnego API, nie błąd
  zapytania) i rocznych plików archiwalnych `static.nbp.pl` dla 1995-2001
  (zweryfikowano ręcznie: archiwum sięga dalej, do co najmniej 1985 r., ale
  z innym układem kolumn przed 1995 r., nieobsługiwanym przez ten moduł).
- GUS: CPI i przeciętne wynagrodzenie. Pierwsza wersja korzystała wyłącznie
  z BDL API (2002/2003+, `fetch_gus_cpi`/`fetch_gus_avg_wage`, wciąż
  dostępne), ale przy weryfikacji długości historii okazało się, że
  1) `stat.gov.pl` publikuje w treści swoich stron gotowe tablice roczne
  sięgające 1950 r. dla obu zmiennych, i 2) zmienna BDL użyta pierwotnie dla
  wynagrodzenia to inna seria (raportowana na poziomie powiatu) niż ta,
  do której faktycznie odwołuje się ustawa o IKE (art. 13a: limit liczony
  od wynagrodzenia "w gospodarce narodowej") -- różnica realna, nie tylko
  kosmetyczna (dla 2002 r.: 2239,56 zł w BDL vs 2133,21 zł w gospodarce
  narodowej). `load_gus_cpi_history`/`load_gus_avg_wage_history` (dane od
  1950 r., wynagrodzenie sprzed denominacji 1995 r. przeliczone /10 000)
  zastępują te dwie funkcje w `build_processed_dataset` -- i poprawność,
  i dłuższa historia, nie tylko jedno z nich.
- Globalny indeks akcyjny (MSCI ACWI Index, ok. 2500 spółek z rynków
  rozwiniętych i rozwijających się) -- ZASTĘPUJE pierwotny podział
  "S&P 500 (Damodaran) + WIG" jedną globalną nogą akcyjną, na wyraźną
  decyzję użytkownika (odejście od architektury opisanej w sekcji 2/3.2
  pracy). Pierwsza wersja używała notowań ETF-u iShares MSCI ACWI
  (od marca 2008), ale start tuż przed kryzysem 2008 nadmiernie obciążał
  wynik -- zastąpiono to samym indeksem (nie konkretnym funduszem), którego
  historia sięga grudnia 1987 r. (464 miesiące, obejmujące krach 1987,
  bessę dot-com, kryzys 2008 i COVID jako kolejne, nie jedyne trudne
  okresy). Dane pochodzą z wbudowanej funkcji eksportu CSV serwisu
  curvo.eu (curvo.eu/backtest/en/market-index/msci-acwi) -- REST API
  dostawców danych giełdowych (`query1/query2.finance.yahoo.com`,
  `stooq.com`/`stooq.pl`, `nasdaq.com`, `macrotrends.net`) było
  zablokowane lub niedostępne z tego środowiska. Odświeżenie tych danych
  w przyszłości wymaga powtórzenia tego samego pobrania -- patrz README,
  sekcja "Dane historyczne".
- WIG i TBSP.Index -- BRAK automatycznego pobierania: typowe źródło
  (stooq.pl) jest chronione wyzwaniem antybotowym (JS proof-of-work), którego
  celowo nie obchodzę. `load_wig_manual`/`load_tbsp_manual` wczytują plik
  ręcznie pobrany przez użytkownika -- instrukcja w README. Żadne z nich nie
  jest już częścią `build_processed_dataset` (WIG zastąpiony przez ACWI,
  TBSP przez EDO -- patrz niżej), funkcje pozostają dostępne, gdyby
  rozdział IV pracy chciał osobno porównać wyniki z rynkiem polskim.
- Polska noga obligacji to teraz detaliczne obligacje EDO (10-letnie,
  indeksowane inflacją), nie TBSP.Index -- druga decyzja użytkownika
  zmieniająca architekturę z sekcji 2 pracy. Marże poszczególnych serii
  EDO zebrane ręcznym skryptem (`build_edo_reference_rate_monthly`) ze
  statycznych, niezabezpieczonych antybotowo stron ofertowych Ministerstwa
  Finansów -- ale tylko od stycznia 2017 (starsze archiwalne strony nie
  przechowują już konkretnej liczby). Tam, gdzie marża EDO jest nieznana
  (przed EDO -- do września 2013 -- lub między wrześniem 2013 a grudniem
  2016), stosowana jest zastępcza formuła `stopa_referencyjna_NBP + 2%`,
  zgodnie z instrukcją użytkownika -- stopa referencyjna NBP pochodzi z
  oficjalnego, w pełni maszynowego archiwum `static.nbp.pl`, bez
  zabezpieczeń antybotowych. Zaczyna się 6.02.1998 -- to NIE jest luka
  w danych, tylko fakt instytucjonalny: stopa referencyjna jako
  narzędzie polityki pieniężnej została ustanowiona dopiero wtedy, gdy
  na mocy ustawy o NBP z 1997 r. powstała Rada Polityki Pieniężnej
  (zweryfikowano). Ten instrument po prostu nie istniał wcześniej --
  to twardy, uzasadniony ekonomicznie/instytucjonalnie dolny limit,
  nie coś do dalszego wydłużania.

Konsekwencja metodologiczna: po wydłużeniu kursu NBP (do 1995 r.) i danych
GUS (do 1950 r.), **jedynym wiążącym ograniczeniem dolnym pełnej symulacji
pozostaje stopa referencyjna NBP, od 6 lutego 1998 r.** -- używana we
wzorze zastępczym dla EDO tam, gdzie marża tej obligacji jest nieznana.
W przeciwieństwie do wcześniejszych ograniczeń (zakres API, brak
digitalizacji starszych danych), to nie jest luka techniczna: stopa
referencyjna jako narzędzie polityki pieniężnej po prostu nie istniała
przed powstaniem Rady Polityki Pieniężnej w 1998 r. -- twardy,
uzasadniony instytucjonalnie limit, nie coś do dalszego wydłużania.
Indeks MSCI ACWI (1987+), kurs NBP (1995+) i dane GUS (1950+) same w sobie
sięgają dalej.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

DAMODARAN_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/histretSP.xls"
DAMODARAN_SHEET_NAME = "Returns by year"
DAMODARAN_HEADER_ROW = 19  # zweryfikowane ręcznie na pobranym pliku (0-indeksowane)

NBP_API_BASE = "https://api.nbp.pl/api/exchangerates/rates/A/USD"
NBP_API_MIN_YEAR = 2002  # zweryfikowane: zapytania o wcześniejsze lata zwracają 404

# Dla lat sprzed 2002 (poza zakresem żywego REST API) NBP publikuje osobne,
# roczne pliki archiwalne (tabela A) pod static.nbp.pl -- bez zabezpieczeń
# antybotowych, zweryfikowane ręcznie wstecz aż do 1985 r. Archiwum ma jednak
# inny układ kolumn przed 1995 r. (dane tygodniowe, kolumny wg nazw krajów
# w kolejności alfabetycznej, nie kod waluty) -- zamiast dorabiać osobny
# parser dla tego układu, granica dolna ustawiona jest na 1995 r., gdzie
# układ jest już spójny z kolejnymi latami (jedna różnica: nagłówek "100 USD"
# zamiast "1 USD" w 1995 r. -- obsłużone przez wykrywanie mnożnika w parserze).
NBP_ARCHIVE_URL = "https://static.nbp.pl/dane/kursy/Archiwum/archiwum_tab_a_{year}.xls"
NBP_ARCHIVE_MIN_YEAR = 1995
NBP_ARCHIVE_DIR = RAW_DIR / "nbp_archive"

# ID zmiennych GUS BDL API, zweryfikowane ręcznie przez przeglądanie hierarchii
# /api/v1/subjects (K15 "CENY" -> G405 "WSKAŹNIKI CEN" -> P2955, oraz
# K40 "WYNAGRODZENIA I ŚWIADCZENIA SPOŁECZNE" -> G403 "WYNAGRODZENIA" -> P2497)
# i porównanie zwracanych wartości z powszechnie znanymi danymi historycznymi
# (np. inflacja 2022 = 114.4 tj. +14,4%, przeciętne wynagrodzenie 2024 = 8630,27 zł).
GUS_API_BASE = "https://bdl.stat.gov.pl/api/v1/data/by-variable"
GUS_CPI_VARIABLE_ID = 217230       # "Wskaźnik cen tow. i usł. konsumpcyjnych, ogółem" (rok poprzedni = 100), roczny
GUS_AVG_WAGE_VARIABLE_ID = 64428   # "Przeciętne miesięczne wynagrodzenia brutto, ogółem" (zł), roczny

# Polska noga obligacji: detaliczne obligacje EDO (10-letnie, indeksowane inflacją) zamiast
# TBSP.Index -- na wyraźną decyzję użytkownika. Marże poszczególnych serii EDO (miesiąc emisji
# -> marża ponad inflację) zostały zebrane ręcznie z oficjalnych stron ofertowych Ministerstwa
# Finansów (obligacjeskarbowe.pl/oferta-obligacji/obligacje-10-letnie-edo/edoMMYY/, gdzie MMYY to
# miesiąc/rok WYKUPU = miesiąc emisji + 10 lat) -- strony te są statyczne (server-rendered), więc
# dają się pobrać zwykłym zapytaniem HTTP, bez żadnego zabezpieczenia antybotowego. EDO wystartowało
# we wrześniu 2013 r. -- to pierwsza faktycznie istniejąca seria (sierpień 2013 already zwraca 404).
# Margines jest jednak podawany na stronie tylko dla serii od stycznia 2017 -- starsze archiwalne
# strony zachowują boilerplate opisu obligacji, ale nie przechowują już konkretnej liczby.
EDO_LAUNCH_MONTH = "2013-09"
RETAIL_BOND_FALLBACK_MARGIN = 0.02  # zgodne z aktualną, obowiązującą od dłuższego czasu marżą EDO


# ---------------------------------------------------------------------------
# Damodaran: roczne stopy zwrotu S&P 500 (z dywidendami) i 10-letnich UST
# ---------------------------------------------------------------------------

def _download_damodaran_xls(cache_path: Path) -> None:
    """Pobiera surowy plik `histretSP.xls` i zapisuje go bez modyfikacji do
    `cache_path`. Wydzielone z `fetch_damodaran_returns`, żeby parsowanie
    (`_parse_damodaran_xls`) dało się testować bez łączności sieciowej.
    """
    response = requests.get(DAMODARAN_URL, timeout=30)
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)


def _parse_damodaran_xls(path: Path) -> pd.DataFrame:
    """Parsuje arkusz 'Returns by year' pliku Damodarana wg zweryfikowanego
    układu (nagłówek w wierszu `DAMODARAN_HEADER_ROW`). Zwraca DataFrame
    indeksowany rokiem (int) z kolumnami `sp500_annual_return`,
    `ust10y_annual_return`; wiersze bez poprawnego roku (stopki, przypisy
    na dole arkusza) są odrzucane.
    """
    raw = pd.read_excel(path, sheet_name=DAMODARAN_SHEET_NAME, header=DAMODARAN_HEADER_ROW)
    df = raw[["Year", "S&P 500 (includes dividends)", "US T. Bond (10-year)"]].copy()
    df = df.rename(
        columns={
            "S&P 500 (includes dividends)": "sp500_annual_return",
            "US T. Bond (10-year)": "ust10y_annual_return",
        }
    )
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df.dropna(subset=["Year"])
    df["Year"] = df["Year"].astype(int)
    return df.set_index("Year").sort_index()


def fetch_damodaran_returns(
    cache_path: Path = RAW_DIR / "histretSP.xls", force_refresh: bool = False
) -> pd.DataFrame:
    """Pobiera (z cache lub sieci) roczne stopy zwrotu S&P 500 i 10-letnich
    obligacji skarbowych USA. Domyślnie czyta z `data/raw/histretSP.xls`,
    jeśli plik już istnieje -- `force_refresh=True` wymusza ponowne pobranie
    (Damodaran aktualizuje plik raz w roku, patrz sekcja 2 spec).
    """
    if force_refresh or not cache_path.exists():
        _download_damodaran_xls(cache_path)
    return _parse_damodaran_xls(cache_path)


def annualize_to_monthly(annual_return: float) -> float:
    """Przelicza roczną stopę zwrotu na miesięczną przy założeniu
    równomiernego kapitalizowania geometrycznego w ciągu roku.

    Dane Damodarana (podobnie jak GUS) są dostępne wyłącznie w
    granulacji rocznej, podczas gdy model wymaga kroku miesięcznego
    (podrozdz. 3.1). Ten wzór to najprostsze możliwe założenie: każdy z
    12 miesięcy danego roku "dostaje" tę samą stopę zwrotu, której
    12-krotne złożenie geometryczne odtwarza dokładnie zwrot roczny.
    Ignoruje to rzeczywistą wewnątrzroczną zmienność i sezonowość -- jawnie
    wymienione jako uproszczenie modelu w README.
    """
    return (1.0 + annual_return) ** (1.0 / 12.0) - 1.0


# ---------------------------------------------------------------------------
# NBP: średni kurs USD/PLN (tabela A)
# ---------------------------------------------------------------------------

def _fetch_nbp_year(year: int) -> pd.DataFrame:
    """Pobiera dzienne kursy średnie USD/PLN dla jednego roku kalendarzowego
    (NBP API akceptuje zakresy dat w ramach jednego zapytania, ale dla
    prostoty i przejrzystości cache'u odpytujemy rok po roku).

    Dla roku bieżącego koniec zakresu jest ucinany do dzisiejszej daty --
    NBP API odpowiada błędem 400 "Invalid date range" (nie 404) przy
    zapytaniu o dni, dla których notowanie jeszcze nie istnieje.
    """
    end_date = min(pd.Timestamp(year=year, month=12, day=31), pd.Timestamp.today())
    url = f"{NBP_API_BASE}/{year}-01-01/{end_date.date()}/"
    response = requests.get(url, params={"format": "json"}, timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = [(r["effectiveDate"], r["mid"]) for r in payload["rates"]]
    return pd.DataFrame(rows, columns=["date", "usd_pln"])


def _download_nbp_archive_year(year: int, cache_path: Path) -> None:
    """Pobiera surowy roczny plik archiwum NBP (tabela A) i zapisuje go bez
    modyfikacji -- wydzielone z parsowania (`_parse_nbp_archive_year`), tak
    samo jak przy Damodaranie, żeby parsowanie dało się testować bez sieci."""
    response = requests.get(NBP_ARCHIVE_URL.format(year=year), timeout=30)
    response.raise_for_status()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)


def _parse_nbp_archive_year(path: Path) -> pd.DataFrame:
    """Parsuje jeden roczny plik archiwum NBP (1995+, tabela A) i zwraca
    dzienne kursy średnie USD/PLN (kolumny `date`, `usd_pln`).

    Układ kolumn jest w tych plikach spójny od 1995 r. co do kolumny USD
    (nagłówek "1 USD", a w 1995 r. wyjątkowo "100 USD"), ale kolumna daty
    NIE zawsze ma własny nagłówek tekstowy: część lat (np. 2000) w ogóle
    nie ma osobnej etykiety "Data" -- daty zaczynają się od razu pod
    nagłówkiem "KURS ŚREDNI" w pierwszej kolumnie. Zamiast więc szukać
    tekstowej etykiety kolumny daty, ustalamy ją jako pierwszą kolumnę,
    w której wiersz *pod* nagłówkiem zawiera rzeczywistą datę.
    """
    raw = pd.read_excel(path, sheet_name=0, header=None)
    header_row, usd_col, multiplier = None, None, 1.0
    for i in range(min(5, len(raw))):
        for j, val in enumerate(raw.iloc[i]):
            if not isinstance(val, str):
                continue
            m = re.match(r"(\d+)\s*usd", val.strip().lower())
            if m:
                header_row, usd_col, multiplier = i, j, float(m.group(1))
        if usd_col is not None:
            break

    if usd_col is None:
        raise ValueError(f"Nie znaleziono kolumny USD w pliku archiwum NBP: {path}")

    first_data_row = raw.iloc[header_row + 1]
    date_col = next(
        (j for j, val in enumerate(first_data_row) if isinstance(val, (pd.Timestamp, dt.datetime))),
        None,
    )
    if date_col is None:
        raise ValueError(f"Nie znaleziono kolumny daty w pliku archiwum NBP: {path}")

    data = raw.iloc[header_row + 1 :, [date_col, usd_col]].copy()
    data.columns = ["date", "usd_pln"]
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["usd_pln"] = pd.to_numeric(data["usd_pln"], errors="coerce") / multiplier
    return data.dropna(subset=["date", "usd_pln"])


def _fetch_nbp_daily_for_year(year: int) -> pd.DataFrame:
    """Zwraca dzienne kursy USD/PLN dla jednego roku, z właściwego źródła:
    żywego REST API dla lat >= `NBP_API_MIN_YEAR` (2002+), archiwalnego
    pliku rocznego dla wcześniejszych (od `NBP_ARCHIVE_MIN_YEAR`, 1995+)."""
    if year >= NBP_API_MIN_YEAR:
        return _fetch_nbp_year(year)
    cache_path = NBP_ARCHIVE_DIR / f"archiwum_tab_a_{year}.xls"
    if not cache_path.exists():
        _download_nbp_archive_year(year, cache_path)
    return _parse_nbp_archive_year(cache_path)


def fetch_nbp_usdpln_monthly(
    start_year: int = NBP_ARCHIVE_MIN_YEAR,
    end_year: int | None = None,
    cache_path: Path = RAW_DIR / "nbp_usdpln.csv",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Pobiera (z cache lub sieci) miesięczne kursy średnie USD/PLN
    (ostatnia notowana wartość każdego miesiąca) od `start_year` do
    `end_year` (domyślnie do roku bieżącego).

    Lata >= 2002 pochodzą z żywego REST API NBP (`api.nbp.pl`), lata
    1995-2001 z rocznych plików archiwalnych (`static.nbp.pl`) --
    `_fetch_nbp_daily_for_year` dobiera właściwe źródło automatycznie.
    `start_year` poniżej 1995 jest odrzucane jawnym `ValueError`: archiwum
    NBP sięga wprawdzie dalej (zweryfikowano ręcznie do 1985 r.), ale ma
    tam inny układ kolumn (dane tygodniowe wg nazw krajów), którego ten
    moduł nie parsuje -- patrz komentarz przy stałych modułu.
    """
    if start_year < NBP_ARCHIVE_MIN_YEAR:
        raise ValueError(
            f"Ten moduł obsługuje dane NBP dopiero od {NBP_ARCHIVE_MIN_YEAR} r. "
            f"(wcześniejsze archiwum ma inny, nieobsługiwany układ kolumn). "
            f"Podano start_year={start_year}."
        )
    end_year = end_year or pd.Timestamp.today().year

    if not force_refresh and cache_path.exists():
        daily = pd.read_csv(cache_path, parse_dates=["date"])
    else:
        daily = pd.concat(
            [_fetch_nbp_daily_for_year(y) for y in range(start_year, end_year + 1)],
            ignore_index=True,
        )
        daily["date"] = pd.to_datetime(daily["date"])
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        daily.to_csv(cache_path, index=False)

    daily = daily.set_index("date").sort_index()
    monthly = daily["usd_pln"].resample("ME").last().to_frame()
    monthly.index = monthly.index.to_period("M")
    return monthly


# ---------------------------------------------------------------------------
# GUS BDL API: CPI oraz przeciętne miesięczne wynagrodzenie brutto
# ---------------------------------------------------------------------------

def fetch_gus_series(variable_id: int, cache_path: Path, force_refresh: bool = False) -> pd.DataFrame:
    """Generyczny fetcher GUS BDL API dla jednej zmiennej na poziomie kraju
    (`unit-level=0`). Współdzielony przez `fetch_gus_cpi` i
    `fetch_gus_avg_wage`, bo obie serie mają identyczny kształt odpowiedzi
    API -- unika duplikowania logiki HTTP+cache dla dwóch bardzo podobnych
    źródeł. Zwraca roczny DataFrame indeksowany rokiem (int) z kolumną `value`.
    """
    if not force_refresh and cache_path.exists():
        return pd.read_csv(cache_path, index_col="year")

    response = requests.get(
        f"{GUS_API_BASE}/{variable_id}", params={"format": "json", "unit-level": 0}, timeout=30
    )
    response.raise_for_status()
    payload = response.json()
    values = payload["results"][0]["values"]
    df = pd.DataFrame(values)[["year", "val"]].rename(columns={"val": "value"})
    df["year"] = df["year"].astype(int)
    df = df.set_index("year").sort_index()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path)
    return df


def fetch_gus_cpi(cache_path: Path = RAW_DIR / "gus_cpi.csv", force_refresh: bool = False) -> pd.DataFrame:
    """Roczny wskaźnik cen towarów i usług konsumpcyjnych GUS (BDL API,
    2003+), w konwencji "rok poprzedni = 100" (np. 114.4 oznacza inflację
    +14,4% w danym roku -- tak jak w 2022 r.). Żeby uzyskać stopę inflacji
    jako ułamek, odejmij 100 i podziel przez 100: `(value - 100) / 100`.

    Zastąpiona w `build_processed_dataset` przez `load_gus_cpi_history`
    (dłuższa historia, od 1950 r.) -- ta funkcja zostaje dostępna i
    przetestowana jako alternatywne, żywe źródło (przydatne, gdyby
    zależało na najnowszym roku szybciej niż aktualizowana jest ręcznie
    odświeżana tablica długiej historii).
    """
    df = fetch_gus_series(GUS_CPI_VARIABLE_ID, cache_path, force_refresh)
    return df.rename(columns={"value": "cpi_prev_year_100"})


def fetch_gus_avg_wage(
    cache_path: Path = RAW_DIR / "gus_avg_wage.csv", force_refresh: bool = False
) -> pd.DataFrame:
    """Roczne przeciętne miesięczne wynagrodzenie brutto (BDL API, 2002+).

    UWAGA METODOLOGICZNA: ta zmienna BDL (`Przeciętne miesięczne
    wynagrodzenia brutto`, raportowana na poziomie powiatu) okazała się przy
    weryfikacji INNĄ serią niż ta, do której faktycznie odwołuje się ustawa
    o IKE (art. 13a: limit = wielokrotność "przeciętnego prognozowanego
    wynagrodzenia miesięcznego **w gospodarce narodowej**" z ustawy
    budżetowej) -- dla 2002 r. ta funkcja zwraca 2239,56 zł, podczas gdy
    oficjalna seria "w gospodarce narodowej" (patrz `load_gus_avg_wage_history`)
    podaje 2133,21 zł. Zastąpiona w `build_processed_dataset` przez
    `load_gus_avg_wage_history` z tego właśnie powodu -- zostaje dostępna
    i przetestowana, ale NIE jako źródło do liczenia limitów IKE/IKZE/OKI.
    """
    df = fetch_gus_series(GUS_AVG_WAGE_VARIABLE_ID, cache_path, force_refresh)
    return df.rename(columns={"value": "avg_gross_wage_pln"})


def load_gus_cpi_history(path: Path = RAW_DIR / "gus_cpi_1950.csv") -> pd.DataFrame:
    """Roczny wskaźnik cen towarów i usług konsumpcyjnych GUS od 1950 r.,
    w tej samej konwencji co `fetch_gus_cpi` ("rok poprzedni = 100") --
    wartości dla lat 2002+ pokrywają się dokładnie z BDL API (zweryfikowano
    ręcznie, np. 2022: 114,4 w obu źródłach), więc to czysto wydłużenie
    historii, nie zmiana metodologii.

    Źródło: `stat.gov.pl` -- strona "Roczne wskaźniki cen towarów i usług
    konsumpcyjnych od 1950 r." udostępnia gotowy plik CSV do pobrania
    (link na stronie, nie ukryte API) -- pobrany i zapisany jako zrzut,
    analogicznie do `load_acwi_history`.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Brak pliku {path}. Źródło: stat.gov.pl, sekcja Ceny/Wskaźniki cen, "
            f"'Roczne wskaźniki cen towarów i usług konsumpcyjnych od 1950 r.'"
        )
    return pd.read_csv(path, index_col="year")


def load_gus_avg_wage_history(path: Path = RAW_DIR / "gus_avg_wage_1950.csv") -> pd.DataFrame:
    """Roczne przeciętne miesięczne wynagrodzenie **w gospodarce narodowej**
    (zł) od 1950 r. -- to jest właściwa, ustawowo wskazana podstawa
    przeliczania limitów IKE/IKZE/OKI (`tax_engine.annual_limit`, podrozdz.
    3.3; art. 13a ustawy o IKE mówi wprost o wynagrodzeniu "w gospodarce
    narodowej", nie w "sektorze przedsiębiorstw" -- patrz uwaga w
    `fetch_gus_avg_wage`).

    Źródło: `stat.gov.pl`, strona "Przeciętne miesięczne wynagrodzenie w
    gospodarce narodowej w latach 1950-2025" -- tabela w treści strony
    (bez osobnego eksportu CSV/XLSX dla tej konkretnej tablicy), przepisana
    ręcznie z widocznej treści strony i zapisana jako zrzut. Wartości sprzed
    1995 r. są w oryginale w starych złotych (PLZ, sprzed denominacji
    1995-01-01) -- przeliczone tu na nowe złote (/10 000) dla spójności
    z resztą modelu.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Brak pliku {path}. Źródło: stat.gov.pl, sekcja Rynek pracy, "
            f"'Przeciętne miesięczne wynagrodzenie w gospodarce narodowej w latach 1950-2025'."
        )
    return pd.read_csv(path, index_col="year")


# ---------------------------------------------------------------------------
# Polska noga obligacji: EDO (detaliczne, indeksowane inflacją) + stopa
# referencyjna NBP jako formuła zastępcza tam, gdzie marża EDO jest nieznana
# ---------------------------------------------------------------------------

def fetch_nbp_reference_rate(cache_path: Path = RAW_DIR / "nbp_reference_rate.csv") -> pd.DataFrame:
    """Wczytuje archiwum stopy referencyjnej NBP (podstawowej stopy polityki
    pieniężnej ustalanej przez RPP -- to jest formuła zastępcza "referencyjna
    NBP + 2%" z instrukcji użytkownika, nie kurs walutowy). Źródło: oficjalne, publiczne, w pełni
    machineczytelne archiwum `static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml`
    (bez zabezpieczeń antybotowych) -- plik zostal juz pobrany i sparsowany
    do `data/raw/nbp_reference_rate.csv` (kolumny: `effective_from`,
    `reference_rate_pct`), obejmuje okres od 1998-02-26 do dziś. Ta funkcja
    tylko wczytuje ten plik -- w przeciwieństwie do pozostałych `fetch_*`
    nie odpytuje sieci przy każdym wywołaniu (archiwum zmienia się rzadko,
    tylko przy decyzjach RPP o zmianie stóp).
    """
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Brak pliku {cache_path}. Źródło: "
            f"static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml (id=\"ref\")."
        )
    df = pd.read_csv(cache_path, parse_dates=["effective_from"])
    return df.set_index("effective_from").sort_index()


def _nbp_reference_rate_at(period: pd.Period, rate_history: pd.DataFrame) -> float:
    """Zwraca stopę referencyjną NBP (jako ułamek, np. 0.0375) obowiązującą
    na koniec danego miesiąca -- stopa referencyjna to skokowa (nie ciągła)
    funkcja czasu, zmieniana decyzjami Rady Polityki Pieniężnej, więc
    bierzemy ostatnią wartość, która weszła w życie przed końcem miesiąca."""
    month_end = period.to_timestamp(how="end")
    applicable = rate_history[rate_history.index <= month_end]
    if applicable.empty:
        raise ValueError(f"Brak stopy referencyjnej NBP przed okresem {period}")
    return applicable["reference_rate_pct"].iloc[-1] / 100.0


def load_edo_margins(path: Path = RAW_DIR / "edo_margins.csv") -> pd.DataFrame:
    """Wczytuje ręcznie zebrane marże serii obligacji EDO (patrz komentarz
    przy stałych modułu wyżej) -- roczny DataFrame indeksowany miesiącem
    emisji (`YYYY-MM`) z kolumnami `first_year_rate_pct` (może być `NaN`)
    i `margin_pct` (może być `NaN` dla miesięcy sprzed stycznia 2017,
    dla których strona źródłowa nie przechowuje już konkretnej liczby)."""
    if not path.exists():
        raise FileNotFoundError(
            f"Brak pliku {path}. Marże EDO nie są pobierane w locie (wymagałoby to "
            f"~150 zapytań HTTP przy każdym uruchomieniu) -- zebrany zrzut powinien "
            f"być zacommitowany w repo."
        )
    return pd.read_csv(path, index_col="issuance_month")


def build_edo_reference_rate_monthly(
    edo_margins_path: Path = RAW_DIR / "edo_margins.csv",
    nbp_reference_path: Path = RAW_DIR / "nbp_reference_rate.csv",
) -> pd.DataFrame:
    """Buduje miesięczny szereg "referencyjnej stopy EDO" -- rocznej stopy,
    jaką w danym miesiącu oferowałaby świeżo kupiona 10-letnia obligacja
    detaliczna, w kolumnie `edo_reference_monthly_return` (już przeliczonej
    na stopę miesięczną przez `annualize_to_monthly`).

    Zgodnie z instrukcją: tam, gdzie znana jest rzeczywista marża danej
    serii EDO (`load_edo_margins`, od stycznia 2017), stopa roczna to
    `inflacja_GUS_roczna + marża` -- dokładnie formuła z
    `tax_engine.retail_bond_rate` dla okresów innych niż pierwszy rok.
    Tam, gdzie marża nie jest znana (EDO jeszcze nie istniało -- przed
    wrześniem 2013 -- albo archiwalna strona jej nie przechowuje -- między
    wrześniem 2013 a grudniem 2016), stosowana jest formuła zastępcza:
    `stopa_referencyjna_NBP + RETAIL_BOND_FALLBACK_MARGIN` (2 p.p., zgodnie
    z aktualną marżą EDO).
    """
    cpi_annual = load_gus_cpi_history()
    margins = load_edo_margins(edo_margins_path)
    nbp_rates = fetch_nbp_reference_rate(nbp_reference_path)

    months = pd.period_range(
        start=nbp_rates.index.min().to_period("M"), end=margins.index.max(), freq="M"
    )

    annual_rates = {}
    for month in months:
        key = str(month)
        margin = margins["margin_pct"].get(key)
        # formula EDO wymaga zarowno znanej marzy, jak i opublikowanego przez GUS
        # CPI za dany rok -- dla biezacego, jeszcze niezakonczonego roku (np. 2026,
        # gdy ostatni opublikowany odczyt to 2025) CPI po prostu jeszcze nie istnieje,
        # co traktujemy tak samo jak nieznana marze: spadamy do formuly zastepczej.
        if pd.notna(margin) and month.year in cpi_annual.index:
            inflation = (cpi_annual.loc[month.year, "cpi_prev_year_100"] - 100.0) / 100.0
            annual_rates[month] = inflation + margin / 100.0
        else:
            annual_rates[month] = _nbp_reference_rate_at(month, nbp_rates) + RETAIL_BOND_FALLBACK_MARGIN

    annual_series = pd.Series(annual_rates).sort_index()
    monthly_return = annual_series.apply(annualize_to_monthly).to_frame(name="edo_reference_monthly_return")
    return monthly_return


# ---------------------------------------------------------------------------
# WIG i TBSP.Index -- pliki pobrane ręcznie przez użytkownika (README)
# ---------------------------------------------------------------------------

def _parse_price_series_to_monthly_returns(path: Path, return_column_name: str) -> pd.DataFrame:
    """Wspólna logika parsowania dla plików WIG i TBSP.Index: obsługuje
    zarówno polski format stooq (`Data;Otwarcie;Najwyzszy;Najnizszy;
    Zamkniecie;Wolumen`, średnik), jak i angielski (`Date,Open,High,Low,
    Close,Volume`, przecinek). Liczy miesięczne stopy zwrotu z ostatniej
    notowanej wartości zamknięcia w danym miesiącu.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Brak pliku {path}. WIG i TBSP.Index nie są pobierane automatycznie "
            f"(źródło stooq.pl blokuje automatyzację zabezpieczeniem antybotowym) "
            f"-- pobierz plik ręcznie zgodnie z instrukcją w README i zapisz go "
            f"pod tą ścieżką."
        )

    raw_text = path.read_text(encoding="utf-8-sig")
    delimiter = ";" if raw_text.count(";") > raw_text.count(",") else ","
    df = pd.read_csv(path, sep=delimiter, encoding="utf-8-sig")

    column_aliases = {
        "data": "date", "date": "date",
        "zamkniecie": "close", "zamknięcie": "close", "close": "close",
    }
    df = df.rename(columns={c: column_aliases.get(c.strip().lower(), c) for c in df.columns})
    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError(
            f"Nieoczekiwany format pliku {path}: nie znaleziono kolumn daty/zamknięcia "
            f"wśród {list(df.columns)}."
        )

    # stooq zapisuje daty jako YYYYMMDD; inne źródła mogą użyć formatu ISO --
    # próbujemy najpierw ścisłego formatu stooq, a dla wierszy, które się nie
    # dopasowały, spadamy do ogólnego parsera pandas na oryginalnym tekście
    # (nie na już-sparsowanej kolumnie, żeby nie stracić surowych wartości).
    date_raw = df["date"].astype(str)
    parsed = pd.to_datetime(date_raw, format="%Y%m%d", errors="coerce")
    fallback_mask = parsed.isna()
    if fallback_mask.any():
        parsed.loc[fallback_mask] = pd.to_datetime(date_raw.loc[fallback_mask], errors="coerce")
    df["date"] = parsed
    df = df.dropna(subset=["date"]).set_index("date").sort_index()

    monthly_close = df["close"].resample("ME").last()
    monthly_return = monthly_close.pct_change().to_frame(name=return_column_name)
    monthly_return.index = monthly_return.index.to_period("M")
    return monthly_return.dropna()


def load_wig_manual(path: Path = RAW_DIR / "wig.csv") -> pd.DataFrame:
    """Wczytuje ręcznie pobrany plik notowań indeksu WIG i zwraca miesięczne
    stopy zwrotu (kolumna `wig_monthly_return`). Patrz README -- sekcja
    "Dane historyczne" -- po instrukcję, skąd pobrać plik źródłowy."""
    return _parse_price_series_to_monthly_returns(path, "wig_monthly_return")


def load_tbsp_manual(path: Path = RAW_DIR / "tbsp.csv") -> pd.DataFrame:
    """Wczytuje ręcznie pobrany plik notowań indeksu TBSP.Index i zwraca
    miesięczne stopy zwrotu (kolumna `tbsp_monthly_return`). Patrz README."""
    return _parse_price_series_to_monthly_returns(path, "tbsp_monthly_return")


# ---------------------------------------------------------------------------
# Globalny indeks akcyjny (MSCI ACWI Index) -- zastępuje S&P 500 + WIG
# ---------------------------------------------------------------------------

def load_acwi_history(path: Path = RAW_DIR / "acwi_monthly.csv") -> pd.DataFrame:
    """Wczytuje miesięczną historię poziomu indeksu MSCI ACWI (USD, ok. 2500
    spółek z rynków rozwiniętych i rozwijających się -- sam indeks, nie
    konkretny fundusz go odwzorowujący) i zwraca miesięczne stopy zwrotu
    (kolumna `acwi_monthly_return`).

    Pierwsza wersja tego modułu używała notowań ETF-u iShares MSCI ACWI
    (ticker ACWI, dane od marca 2008 -- data powstania funduszu). Na
    wyraźną prośbę zastąpiono to samym indeksem MSCI ACWI, którego historia
    sięga grudnia 1987 r. (464 miesiące zamiast ~220) -- start w 2008 r.,
    tuż przed globalnym kryzysem finansowym, sprawiał, że wynik symulacji
    był nadmiernie wrażliwy na wybór akurat tego, szczególnie niekorzystnego
    okresu jako punktu startowego. Dłuższa historia (obejmująca krach 1987,
    bessę dot-com 2000-2002, kryzys 2008 i COVID-19 jako kolejne, a nie
    jedyne trudne okresy) czyni wynik znacznie mniej podatnym na ten
    konkretny błąd doboru próby.

    Podobnie jak poprzednio, dane NIE pochodzą z automatycznego zapytania
    HTTP tego modułu -- REST API dostawców danych giełdowych jest
    zablokowane lub niedostępne z tego środowiska (patrz historia commitów).
    Pochodzą z funkcji eksportu CSV wbudowanej w narzędzie do backtestingu
    curvo.eu (curvo.eu/backtest/en/market-index/msci-acwi, waluta USD) --
    to legalny, zamierzony sposób pobrania danych z tej strony (przycisk
    "CSV" pod wykresem), nie obejście żadnego zabezpieczenia. Traktuj ten
    plik jak zrzut (snapshot); odświeżenie o kolejne miesiące wymaga
    ponownego pobrania z tego samego źródła.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Brak pliku {path}. Patrz README -- sekcja 'Dane historyczne' -- "
            f"po sposób uzyskania historii MSCI ACWI (dane nie są pobierane "
            f"automatycznie z tego środowiska)."
        )
    df = pd.read_csv(path)
    df["month"] = pd.PeriodIndex(df["month"], freq="M")
    df = df.set_index("month").sort_index()
    returns = df["index_level"].pct_change().to_frame(name="acwi_monthly_return")
    return returns.dropna()


# ---------------------------------------------------------------------------
# Normalizacja: połączenie wszystkich źródeł do wspólnego formatu miesięcznego
# ---------------------------------------------------------------------------

def _broadcast_annual_to_monthly(annual: pd.DataFrame, column: str) -> pd.Series:
    """Powiela roczną wartość na wszystkie 12 miesięcy danego roku --
    Damodaran, GUS CPI i GUS wynagrodzenie są z natury seriami rocznymi;
    ten model traktuje je jako stałe w obrębie roku, aż do kolejnej
    aktualizacji (dokładnie tak, jak limity IKE/IKZE są przeliczane raz na
    rok w `tax_engine.annual_limit`)."""
    months = pd.period_range(
        start=f"{annual.index.min()}-01", end=f"{annual.index.max()}-12", freq="M"
    )
    return pd.Series(
        [annual.loc[m.year, column] for m in months], index=months, name=column
    )


def build_processed_dataset(
    acwi_path: Path = RAW_DIR / "acwi_monthly.csv",
    output_path: Path = PROCESSED_DIR / "market_data.csv",
) -> pd.DataFrame:
    """Łączy wszystkie źródła we wspólny, miesięczny DataFrame i zapisuje go
    do `data/processed/market_data.csv`.

    Noga akcyjna to globalny indeks MSCI ACWI (`load_acwi_history`), nie
    S&P 500 + WIG osobno. Noga obligacji to wyłącznie polskie detaliczne
    EDO (`build_edo_reference_rate_monthly`) -- bez globalnych obligacji
    (Damodaran/UST10Y) i bez TBSP.Index. Obie zmiany na wyraźną decyzję
    użytkownika -- patrz docstring modułu.

    Użyty jest outer join po indeksie miesięcznym: żadna seria nie jest po
    cichu ucinana do najkrótszej wspólnej historii. Decyzję, czy dany
    scenariusz symulacji wymaga kompletu kolumn (co w praktyce ogranicza
    start symulacji do 6 lutego 1998 r. -- daty ustanowienia stopy
    referencyjnej NBP, jedynego pozostałego ograniczenia dolnego, i to
    instytucjonalnego, nie technicznego -- patrz docstring modułu),
    podejmuje `simulation.py`, nie ten moduł.
    """
    cpi_annual = load_gus_cpi_history()
    wage_annual = load_gus_avg_wage_history()
    usdpln_monthly = fetch_nbp_usdpln_monthly()
    acwi_monthly = load_acwi_history(acwi_path)
    edo_monthly = build_edo_reference_rate_monthly()

    cpi_monthly = _broadcast_annual_to_monthly(cpi_annual, "cpi_prev_year_100")
    wage_monthly = _broadcast_annual_to_monthly(wage_annual, "avg_gross_wage_pln")

    combined = pd.concat(
        [acwi_monthly["acwi_monthly_return"], usdpln_monthly["usd_pln"],
         edo_monthly["edo_reference_monthly_return"], cpi_monthly, wage_monthly],
        axis=1,
        join="outer",
    ).sort_index()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path)
    return combined
