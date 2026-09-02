"""Faza dystrybucji (dekumulacji) kapitału -- test ryzyka sekwencji stóp
zwrotu (SORR) metodą Reguły 4% na wielu historycznych oknach startowych
(Bengen 1994 / Trinity Study 1998), zgodnie z podrozdz. 1.3 pracy. To druga
połowa hipotezy badawczej ("naiwne FIRE naraża na ryzyko przedwczesnego
wyczerpania kapitału"), której wcześniejsze etapy (akumulacja) w ogóle nie
testowały.

Zaprojektowana jako NIEZALEŻNA od KONKRETNEGO okna akumulacji analiza
rolling-window -- standardowe podejście Bengena/Trinity: pytanie brzmi
"gdyby ktoś przeszedł na FIRE w miesiącu M z portfelem równym 25-krotności
rocznych wydatków, czy przetrwałby N lat wypłat", nie "co się stanie zaraz
po zakończeniu KONKRETNEGO okna akumulacji" (te dwa podejścia dają różne,
ale komplementarne informacje; to pierwsze faktycznie mierzy SORR). Wiek
i podział portfela na konta (patrz niżej) są natomiast REPREZENTATYWNE dla
danego scenariusza (archetyp x konta x alokacja x stopa oszczędności) --
tak jak w klasycznych badaniach Bengena/Trinity, gdzie wiek emeryta jest
ustalonym parametrem scenariusza, a nie czymś wyprowadzanym z konkretnego,
pojedynczego przebiegu.

Wiek i dostępność kont IKE/IKZE/PPK (dodane w tym etapie): polskie prawo
wiąże bezpodatkowy/preferencyjny dostęp do tych kont z WIEKIEM, nie z samym
faktem osiągnięcia celu FIRE -- IKE i PPK dopiero od 60. r.ż., IKZE
(ryczałt 10%) dopiero od 65. r.ż. OKI i rachunek standardowy są dostępne
zawsze (OKI zaprojektowane jako płynny wehikuł bez blokady wiekowej --
stąd `priority_mode="liquidity_first"` już w `tax_engine.allocate_monthly_surplus`).
Jeśli ktoś osiąga cel FIRE przed 60/65 r.ż. (typowy scenariusz "naiwnego
FIRE" z hipotezy pracy), przez lata do tego wieku fizycznie nie ma
bezkarnego dostępu do zablokowanych kont -- nawet jeśli PORTFEL JAKO CAŁOŚĆ
byłby wystarczający, może zabraknąć PŁYNNYCH środków na pokrycie wypłaty.
Ten moduł rozróżnia dlatego dwa tryby porażki: `"capital_exhausted"`
(klasyczne wyczerpanie kapitału, jak w Bengenie) i `"liquidity_gap"`
(kapitał jako całość istnieje, ale jest zablokowany wiekiem) -- to drugie
jest bezpośrednim testem realnego ryzyka "FIRE przez IKE/IKZE w Polsce",
nie tylko klasycznego SORR.

Świadome uproszczenie zakresu, które POZOSTAJE (odnotowane też w README):
nie modelujemy tu kar za wcześniejszą (przed wiekiem) WYPŁATĘ (np. utraty
dopłat PPK, opodatkowania zysku IKE, czy przejścia IKZE na skalę PIT) --
środki zablokowane wiekiem są po prostu niedostępne do wypłaty w tym
modelu, nie "dostępne z karą". To świadomie bardziej konserwatywne
założenie (nie zaniża ryzyka) i unika podwójnej komplikacji (modelowania
JEDNOCZEŚNIE decyzji "czy zapłacić karę" i testu SORR). Każde konto rośnie
tą samą ważoną stopą equity/bond co cały portfel (spójne z akumulacją,
gdzie `_add_contribution` też stosuje jedną, wspólną alokację do
wszystkich kont) -- w rzeczywistości inwestor mógłby różnicować alokację
między kontami, ale to nie jest tu modelowane.

Ograniczenie horyzontu -- policzone, nie zgadywane: dane obejmują ~28,5
roku (342 miesiące, luty 1998 - lipiec 2026). Testowane horyzonty: 10, 15,
20 i 25 lat. 25 lat (300 miesięcy) mieści się w danych, ale z bardzo małym
zapasem -- tylko okna startujące w pierwszych ~42 miesiącach zbioru mają
wystarczająco dużo danych naprzód, więc liczba niezależnych okien jest tu
mała i wynik dla 25 lat należy traktować z odpowiednią ostrożnością.
Klasyczne 30 lat z Trinity Study (360 miesięcy) i tym bardziej 35/40 lat
NIE MIESZCZĄ SIĘ w żadnym oknie startowym tego zbioru danych -- nawet
zaczynając od pierwszego dostępnego miesiąca zabrakłoby odpowiednio
18/78/138 miesięcy danych. To nie przeoczenie: rozszerzenie do tych
horyzontów wymagałoby zmiany metodologii (np. block-bootstrap zamiast
nieprzetworzonych sekwencji historycznych) -- świadoma decyzja, żeby tego
NIE robić w tym etapie, bo odchodziłoby od zasady "jedna, nieprzetworzona
historyczna ścieżka" przyjętej dla całego modelu.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.simulation import SimulationAssumptions

DEFAULT_HORIZONS_YEARS = (10, 15, 20, 25)
REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"

# Progi wieku uprawniające do bezpodatkowego/preferencyjnego dostepu --
# patrz docstring modulu. OKI i rachunek standardowy: zawsze dostepne.
ACCOUNT_ACCESS_AGE: dict[str, float] = {"ike": 60.0, "ppk": 60.0, "ikze": 65.0}
ALWAYS_ACCESSIBLE_ACCOUNTS = frozenset({"oki", "standard"})
ACCOUNT_KEYS = ("ppk", "ikze", "ike", "oki", "standard")


def _clean_decumulation_data(market_data: pd.DataFrame) -> pd.DataFrame:
    """CPI ffillowane (dla indeksacji wypłat), przycięte do zakresu, w którym
    dostępne są składniki zwrotu portfela -- świadomie NIE wymaga
    `avg_gross_wage_pln` (w przeciwieństwie do `simulation._clean_market_data`),
    bo dekumulacja nie zależy od dochodu/archetypu."""
    data = market_data.sort_index().copy()
    data["cpi_prev_year_100"] = data["cpi_prev_year_100"].ffill()
    data = data.dropna(subset=["acwi_monthly_return", "usd_pln", "edo_reference_monthly_return"])
    data["usd_pln_change"] = data["usd_pln"].pct_change().fillna(0.0)
    return data


def _unlocked_accounts(current_age: float) -> set[str]:
    unlocked = set(ALWAYS_ACCESSIBLE_ACCOUNTS)
    for account, access_age in ACCOUNT_ACCESS_AGE.items():
        if current_age >= access_age:
            unlocked.add(account)
    return unlocked


def run_decumulation_window(
    start_month: pd.Period,
    market_data: pd.DataFrame,
    assumptions: SimulationAssumptions,
    horizon_years: int,
    swr: float = 0.04,
    account_split: dict[str, float] | None = None,
    start_age_at_fire: float | None = None,
) -> dict | None:
    """Symuluje wypłaty regułą SWR z portfela znormalizowanego do 1.0,
    począwszy od `start_month`, przez `horizon_years`. Wypłata w pierwszym
    miesiącu to `swr/12` wartości startowej; każdego stycznia jest
    podwyższana o zrealizowaną inflację GUS z poprzedniego roku (klasyczna
    reguła Bengena: stała kwota realna, nie stały % aktualnego salda).
    Zwrot portfela to ta sama ważona stopa equity/bond co w akumulacji
    (z TER), stosowana identycznie do każdego konta.

    `account_split` (ułamki sumujące się do 1.0, klucze `ACCOUNT_KEYS`) i
    `start_age_at_fire` (wiek w chwili rozpoczęcia wypłat) włączają test
    dostępności wiekowej IKE/IKZE/PPK (patrz docstring modułu) -- oba muszą
    być podane razem albo wcale. Gdy pominięte (domyślnie), portfel jest
    traktowany jak jedna, w pełni płynna pula (dawne zachowanie tego
    modułu, sprzed wprowadzenia bramkowania wiekowego).

    Zwraca `None`, jeśli w danych brakuje wystarczająco długiego ogona
    (mniej niż `horizon_years*12` miesięcy od `start_month`) -- takie okno
    jest pomijane w agregacji, nie liczone jako porażka. W przeciwnym razie
    zwraca słownik z `survived`, `failure_reason` (`None`, `"liquidity_gap"`
    -- kapitał całkowity istnieje, ale jest zablokowany wiekiem, albo
    `"capital_exhausted"` -- klasyczne wyczerpanie), `ending_balance`
    (suma wszystkich kont, także tych wciąż zablokowanych na koniec
    horyzontu), `min_balance`, `locked_balance_at_end` (ułamek salda
    końcowego wciąż niedostępny w chwili zakończenia testu) i `age_at_end`.
    """
    if (account_split is None) != (start_age_at_fire is None):
        raise ValueError("account_split i start_age_at_fire trzeba podac razem albo wcale")

    data = _clean_decumulation_data(market_data)
    window = data[data.index >= start_month]

    horizon_months = horizon_years * 12
    if len(window) < horizon_months:
        return None
    window = window.iloc[:horizon_months]

    age_aware = account_split is not None
    if age_aware:
        balances = {acct: account_split.get(acct, 0.0) for acct in ACCOUNT_KEYS}
    else:
        balances = {"standard": 1.0}  # pula bez podzialu -- caly balans zawsze "odblokowany"

    ter_monthly = assumptions.acwi_ter_annual / 12
    min_balance = sum(balances.values())
    monthly_withdrawal = swr / 12.0
    current_year: int | None = None

    def _fail(reason: str, age: float | None) -> dict:
        # nawet przy porazce raportujemy RZECZYWISTY kapital, jaki zostal
        # (a nie 0.0) -- przy "liquidity_gap" moze byc znaczacy: kapital
        # istnieje, tylko jest zablokowany wiekiem (patrz docstring modulu
        # i prosba uzytkownika o raportowanie kapitalu koncowego)
        total = sum(balances.values())
        unlocked_now = _unlocked_accounts(age) if age_aware and age is not None else set(balances.keys())
        locked = sum(v for k, v in balances.items() if k not in unlocked_now)
        return {
            "start_month": start_month,
            "survived": False,
            "failure_reason": reason,
            "ending_balance": total,
            "min_balance": min(min_balance, total),
            "locked_balance_at_end": locked / total if total > 0 else 0.0,
            "age_at_end": age,
        }

    for month_index, (month, row) in enumerate(window.iterrows()):
        if month.year != current_year:
            if current_year is not None:
                inflation_last_year = (
                    data.loc[data.index.year == current_year, "cpi_prev_year_100"].iloc[-1] - 100.0
                ) / 100.0
                monthly_withdrawal *= 1.0 + inflation_last_year
            current_year = month.year

        if age_aware:
            current_age = start_age_at_fire + month_index / 12.0
            unlocked = _unlocked_accounts(current_age)
            accessible_balance = sum(balances[a] for a in unlocked if a in balances)

            if accessible_balance + 1e-9 < monthly_withdrawal:
                return _fail("liquidity_gap", current_age)

            for account in unlocked:
                if account not in balances or balances[account] <= 0.0:
                    continue
                share = balances[account] / accessible_balance
                balances[account] -= monthly_withdrawal * share
        else:
            # bez podzialu na konta -- ta sama, nieprogowa arytmetyka co przed
            # wprowadzeniem bramkowania wiekowego (dopuszcza chwilowe przejscie
            # salda na ujemne, zaraportowane nizej jako dokladne 0.0)
            current_age = None
            balances["standard"] -= monthly_withdrawal

        total_balance = sum(balances.values())
        min_balance = min(min_balance, total_balance)
        if total_balance <= 0:
            if not age_aware:
                return {
                    "start_month": start_month,
                    "survived": False,
                    "failure_reason": "capital_exhausted",
                    "ending_balance": 0.0,
                    "min_balance": 0.0,
                    "locked_balance_at_end": 0.0,
                    "age_at_end": None,
                }
            return _fail("capital_exhausted", current_age)

        equity_gross = (1 + row["acwi_monthly_return"]) * (1 + row["usd_pln_change"]) - 1
        bond_return = row["edo_reference_monthly_return"]
        blended_return = (
            assumptions.equity_weight * (equity_gross - ter_monthly) + assumptions.bond_weight * bond_return
        )
        for account in balances:
            balances[account] *= 1.0 + blended_return
        total_balance = sum(balances.values())
        min_balance = min(min_balance, total_balance)

    final_age = start_age_at_fire + len(window) / 12.0 if age_aware else None
    final_unlocked = _unlocked_accounts(final_age) if age_aware else set(balances.keys())
    total_balance = sum(balances.values())
    locked_balance_at_end = sum(v for k, v in balances.items() if k not in final_unlocked)

    return {
        "start_month": start_month,
        "survived": True,
        "failure_reason": None,
        "ending_balance": total_balance,
        "min_balance": min_balance,
        "locked_balance_at_end": locked_balance_at_end / total_balance if total_balance > 0 else 0.0,
        "age_at_end": final_age,
    }


def run_rolling_decumulation(
    market_data: pd.DataFrame,
    assumptions: SimulationAssumptions,
    horizon_years: int,
    swr: float = 0.04,
    step_months: int = 6,
    account_split: dict[str, float] | None = None,
    start_age_at_fire: float | None = None,
) -> pd.DataFrame:
    """Uruchamia `run_decumulation_window` dla wielu miesięcy startowych
    (co `step_months`), pomijając te bez wystarczająco długiego ogona
    danych. Zwraca DataFrame: jeden wiersz na okno."""
    start_months = _clean_decumulation_data(market_data).index[::step_months]

    rows = []
    for start in start_months:
        result = run_decumulation_window(
            start, market_data, assumptions, horizon_years, swr, account_split, start_age_at_fire
        )
        if result is not None:
            rows.append(result)

    return pd.DataFrame(rows)


def summarize_decumulation(results: pd.DataFrame) -> dict:
    """Agreguje wynik `run_rolling_decumulation`: wskaźnik sukcesu (% okien,
    w których portfel przetrwał cały horyzont), mediana/min salda końcowego
    wśród tych, które przetrwały, mediana najgłębszego obsunięcia (drawdown,
    liczone na wszystkich oknach), oraz -- gdy dostępne (`failure_reason`
    ustawiony) -- rozbicie porażek na `"liquidity_gap"` (kapitał istniał,
    ale był zablokowany wiekiem) i `"capital_exhausted"` (klasyczne
    wyczerpanie), żeby było jasno widać, ile ryzyka wynika z blokady
    wiekowej IKE/IKZE/PPK, a ile z faktycznego wyczerpania kapitału."""
    if results.empty:
        return {
            "n_windows": 0,
            "success_rate": None,
            "ending_balance_median": None,
            "ending_balance_min": None,
            "min_balance_median": None,
            "n_failures_liquidity_gap": None,
            "n_failures_capital_exhausted": None,
        }
    survived = results[results["survived"]]
    failed = results[~results["survived"]]
    reasons = failed["failure_reason"] if "failure_reason" in failed.columns else pd.Series(dtype=object)
    return {
        "n_windows": len(results),
        "success_rate": len(survived) / len(results),
        "ending_balance_median": survived["ending_balance"].median() if len(survived) else None,
        "ending_balance_min": survived["ending_balance"].min() if len(survived) else None,
        "min_balance_median": results["min_balance"].median(),
        "n_failures_liquidity_gap": int((reasons == "liquidity_gap").sum()),
        "n_failures_capital_exhausted": int((reasons == "capital_exhausted").sum()),
    }


def run_all_decumulation(
    market_data: pd.DataFrame | None = None,
    allocations: dict[str, float] | None = None,
    horizons_years: tuple[int, ...] = DEFAULT_HORIZONS_YEARS,
    swr: float = 0.04,
    account_split: dict[str, float] | None = None,
    start_age_at_fire: float | None = None,
    output_dir: Path = RESULTS_DIR,
) -> pd.DataFrame:
    """Uruchamia analizę dekumulacji dla każdej kombinacji alokacji x
    horyzontu, zapisuje `results/decumulation_summary.csv` i zwraca ją jako
    DataFrame (indeks: alokacja, horyzont). `account_split`/`start_age_at_fire`
    -- gdy podane -- włączają bramkowanie wiekowe (patrz `run_decumulation_window`)
    jednolicie dla wszystkich alokacji w tym wywołaniu; domyślnie (None)
    zachowuje dawne, w pełni płynne zachowanie (np. do szybkiego,
    ilustracyjnego uruchomienia `python -m src.decumulation` bez
    archetypu)."""
    if market_data is None:
        from src.data_loader import build_processed_dataset

        market_data = build_processed_dataset()
    if allocations is None:
        allocations = {"80_20": 0.80, "60_40": 0.60, "40_60": 0.40}

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for allocation_code, equity_weight in allocations.items():
        assumptions = SimulationAssumptions(equity_weight=equity_weight, bond_weight=1 - equity_weight)
        for horizon in horizons_years:
            results = run_rolling_decumulation(
                market_data, assumptions, horizon, swr, account_split=account_split, start_age_at_fire=start_age_at_fire
            )
            summary = summarize_decumulation(results)
            summary["allocation"] = allocation_code
            summary["equity_weight"] = equity_weight
            summary["horizon_years"] = horizon
            summary["swr"] = swr
            rows.append(summary)

    summary_df = pd.DataFrame(rows).set_index(["allocation", "horizon_years"])
    summary_df.to_csv(output_dir / "decumulation_summary.csv")
    return summary_df


if __name__ == "__main__":
    result = run_all_decumulation()
    print(result)
