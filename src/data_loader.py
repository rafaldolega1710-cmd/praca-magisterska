"""Pobieranie i normalizacja historycznych danych rynkowych oraz
makroekonomicznych dla modelu FIRE-PL (podrozdz. 3.2 pracy / sekcja 2
`fire_model_spec.md`).

Zweryfikowana (nie zakładana) dostępność źródeł -- patrz plan Etapu 2:
- Damodaran `histretSP.xls` (10-letnie obligacje skarbowe USA -- noga
  globalnych obligacji) -- pobierany automatycznie.
- NBP API kursów średnich USD/PLN -- pobierany automatycznie, ale wyłącznie
  od 2002-01-02 (twardy limit publicznego REST API, nie błąd zapytania).
- GUS BDL API (CPI, przeciętne wynagrodzenie) -- pobierany automatycznie,
  konkretne ID zmiennych zweryfikowane ręcznie (patrz stałe modułu niżej).
- Globalny ETF akcyjny (iShares MSCI ACWI, ticker ACWI) -- ZASTĘPUJE
  pierwotny podział "S&P 500 (Damodaran) + WIG" jedną globalną nogą akcyjną,
  na wyraźną decyzję użytkownika (odejście od architektury opisanej w
  sekcji 2/3.2 pracy). Dane historyczne uzyskane przez rzeczywistą sesję
  przeglądarki na stronie Yahoo Finance -- nie istnieje tu skryptowalne
  API: `query1/query2.finance.yahoo.com` blokuje zapytania z tego
  środowiska ("Edge: Too Many Requests" nawet przy pierwszym zapytaniu),
  `stooq.com` i `stooq.pl` chronione są wyzwaniem antybotowym, `nasdaq.com`
  było nieosiągalne, a `macrotrends.net` zwrócił 403. Odświeżenie tych
  danych w przyszłości wymaga powtórzenia tego samego, ręcznego/przez
  przeglądarkę procesu -- patrz README, sekcja "Dane historyczne".
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
  oficjalnego, w pełni maszynowego archiwum `static.nbp.pl` (1998+, bez
  zabezpieczeń antybotowych).

Konsekwencja metodologiczna: pełna symulacja obejmująca WSZYSTKIE klasy
aktywów (w tym część zagraniczną przeliczaną na PLN) jest możliwa dopiero
od 2002 r. (zakres NBP API), a globalna noga akcyjna (ACWI) dodatkowo
zawęża to do marca 2008 r. (data powstania funduszu) -- krótsza historia
niż dawałby S&P 500 (od 1928 r.), ale za to jeden, spójny, faktycznie
inwestowalny instrument zamiast dwóch osobnych indeksów.
"""

from __future__ import annotations

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


def fetch_nbp_usdpln_monthly(
    start_year: int = NBP_API_MIN_YEAR,
    end_year: int | None = None,
    cache_path: Path = RAW_DIR / "nbp_usdpln.csv",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Pobiera (z cache lub sieci) miesięczne kursy średnie USD/PLN
    (ostatnia notowana wartość każdego miesiąca) od `start_year` do
    `end_year` (domyślnie do roku bieżącego).

    `start_year` poniżej 2002 jest odrzucane jawnym `ValueError` --
    zweryfikowano ręcznie, że publiczne REST API NBP (`api.nbp.pl`) po
    prostu nie ma wcześniejszych danych (zwraca 404), więc lepiej to
    zasygnalizować jawnie niż dać cichy, mylący wynik.
    """
    if start_year < NBP_API_MIN_YEAR:
        raise ValueError(
            f"NBP API (api.nbp.pl) udostępnia dane dopiero od {NBP_API_MIN_YEAR} r. "
            f"(zweryfikowano ręcznie -- wcześniejsze zapytania zwracają 404). "
            f"Podano start_year={start_year}."
        )
    end_year = end_year or pd.Timestamp.today().year

    if not force_refresh and cache_path.exists():
        daily = pd.read_csv(cache_path, parse_dates=["date"])
    else:
        daily = pd.concat(
            [_fetch_nbp_year(y) for y in range(start_year, end_year + 1)],
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
    """Roczny wskaźnik cen towarów i usług konsumpcyjnych GUS, w konwencji
    "rok poprzedni = 100" (np. 114.4 oznacza inflację +14,4% w danym roku
    -- tak jak w 2022 r.). Żeby uzyskać stopę inflacji jako ułamek, odejmij
    100 i podziel przez 100: `(value - 100) / 100`.
    """
    df = fetch_gus_series(GUS_CPI_VARIABLE_ID, cache_path, force_refresh)
    return df.rename(columns={"value": "cpi_prev_year_100"})


def fetch_gus_avg_wage(
    cache_path: Path = RAW_DIR / "gus_avg_wage.csv", force_refresh: bool = False
) -> pd.DataFrame:
    """Roczne przeciętne miesięczne wynagrodzenie brutto w gospodarce
    narodowej (zł) -- podstawa przeliczania limitów IKE/IKZE/OKI
    (`tax_engine.annual_limit`, podrozdz. 3.3)."""
    df = fetch_gus_series(GUS_AVG_WAGE_VARIABLE_ID, cache_path, force_refresh)
    return df.rename(columns={"value": "avg_gross_wage_pln"})


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
    cpi_annual = fetch_gus_cpi()
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
# Globalny ETF akcyjny (iShares MSCI ACWI) -- zastępuje S&P 500 + WIG
# ---------------------------------------------------------------------------

def load_acwi_history(path: Path = RAW_DIR / "acwi_monthly.csv") -> pd.DataFrame:
    """Wczytuje miesięczną historię kursu iShares MSCI ACWI ETF (ticker
    `ACWI`, notowania skorygowane o dywidendy -- kolumna Adj Close z Yahoo
    Finance) i zwraca miesięczne stopy zwrotu (kolumna `acwi_monthly_return`).

    W przeciwieństwie do pozostałych funkcji `fetch_*`/`load_*_manual`, ten
    plik NIE pochodzi ani z automatycznego zapytania HTTP, ani z ręcznego
    pobrania przez użytkownika, tylko z rzeczywistej sesji przeglądarki
    (finance.yahoo.com/quote/ACWI/history, zakres "Max", interwał
    "Monthly") -- każde inne wypróbowane źródło (Yahoo REST API, stooq,
    nasdaq.com, macrotrends.net) było zablokowane lub niedostępne z tego
    środowiska. Odświeżenie danych o kolejne miesiące wymaga powtórzenia
    tej samej procedury (patrz README) -- traktuj ten plik jak zrzut
    (snapshot), nie jak wynik powtarzalnego, automatycznego pobierania.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Brak pliku {path}. Patrz README -- sekcja 'Dane historyczne' -- "
            f"po sposób uzyskania historii ACWI (dane nie są pobierane "
            f"automatycznie z tego środowiska)."
        )
    df = pd.read_csv(path)
    df["month"] = pd.PeriodIndex(df["month"], freq="M")
    df = df.set_index("month").sort_index()
    returns = df["adj_close"].pct_change().to_frame(name="acwi_monthly_return")
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

    Noga akcyjna to globalny ETF (`load_acwi_history`, ACWI), nie
    S&P 500 + WIG osobno. Noga obligacji to Damodaran (globalne, UST10Y) +
    EDO/NBP-referencyjna (polskie, `build_edo_reference_rate_monthly`), nie
    TBSP.Index. Obie zmiany na wyraźną decyzję użytkownika -- patrz
    docstring modułu.

    Użyty jest outer join po indeksie miesięcznym: żadna seria nie jest po
    cichu ucinana do najkrótszej wspólnej historii. Decyzję, czy dany
    scenariusz symulacji wymaga kompletu kolumn (co w praktyce ogranicza
    start symulacji do marca 2008 -- daty powstania ACWI, najpóźniejszej
    ze wszystkich granic dolnych -- patrz docstring modułu), podejmuje
    `simulation.py`, nie ten moduł.
    """
    damodaran_annual = fetch_damodaran_returns()
    cpi_annual = fetch_gus_cpi()
    wage_annual = fetch_gus_avg_wage()
    usdpln_monthly = fetch_nbp_usdpln_monthly()
    acwi_monthly = load_acwi_history(acwi_path)
    edo_monthly = build_edo_reference_rate_monthly()

    ust10y_monthly = _broadcast_annual_to_monthly(
        damodaran_annual.assign(
            ust10y_annual_return=damodaran_annual["ust10y_annual_return"].apply(annualize_to_monthly)
        ),
        "ust10y_annual_return",
    ).rename("ust10y_monthly_return")
    cpi_monthly = _broadcast_annual_to_monthly(cpi_annual, "cpi_prev_year_100")
    wage_monthly = _broadcast_annual_to_monthly(wage_annual, "avg_gross_wage_pln")

    combined = pd.concat(
        [acwi_monthly["acwi_monthly_return"], ust10y_monthly, usdpln_monthly["usd_pln"],
         edo_monthly["edo_reference_monthly_return"], cpi_monthly, wage_monthly],
        axis=1,
        join="outer",
    ).sort_index()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_path)
    return combined
