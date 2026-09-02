"""Faza dystrybucji (dekumulacji) kapitału -- test ryzyka sekwencji stóp
zwrotu (SORR) metodą Reguły 4% na wielu historycznych oknach startowych
(Bengen 1994 / Trinity Study 1998), zgodnie z podrozdz. 1.3 pracy. To druga
połowa hipotezy badawczej ("naiwne FIRE naraża na ryzyko przedwczesnego
wyczerpania kapitału"), której wcześniejsze etapy (akumulacja) w ogóle nie
testowały.

Zaprojektowana jako NIEZALEŻNA od fazy akumulacji analiza rolling-window --
standardowe podejście Bengena/Trinity: pytanie brzmi "gdyby ktoś przeszedł
na FIRE w miesiącu M z portfelem równym 25-krotności rocznych wydatków, czy
przetrwałby N lat wypłat", nie "co się stanie zaraz po zakończeniu
KONKRETNEGO okna akumulacji" (te dwa podejścia dają różne, ale
komplementarne informacje; to pierwsze faktycznie mierzy SORR).

Świadome uproszczenie zakresu (odnotowane też w README): portfel liczony
jest jako JEDNA, połączona całość -- bez podziału na konta IKE/IKZE/PPK/
/OKI/standard. Nie modelujemy tu kolejności wypłat z poszczególnych kont,
kar za wcześniejsze wypłaty z PPK/IKZE ani podatku od zysku przy sprzedaży
na rachunku standardowym -- to osobny, duży temat (spec sam nazywa fazę
dekumulacji "osobnym modelem"). Test przetrwania kapitału jest z natury
niezależny od poziomu dochodów (wypłata 4% z portfela X zachowuje się
identycznie w ujęciu względnym niezależnie od tego, czy X to 500 tys. czy
5 mln zł), więc ten moduł operuje na ZNORMALIZOWANYM portfelu (start = 1.0)
i nie wymaga archetypu jako wejścia.

Ograniczenie horyzontu -- policzone, nie zgadywane: dane obejmują ~28 lat.
Klasyczne 30 lat z Trinity Study nie zmieściłoby się w ŻADNYM oknie (zero
kompletnych testów). Testujemy więc horyzonty, które faktycznie mieszczą
się z sensowną liczbą okien: 10, 15 i 20 lat.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.simulation import SimulationAssumptions

DEFAULT_HORIZONS_YEARS = (10, 15, 20)
REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"


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


def run_decumulation_window(
    start_month: pd.Period,
    market_data: pd.DataFrame,
    assumptions: SimulationAssumptions,
    horizon_years: int,
    swr: float = 0.04,
) -> dict | None:
    """Symuluje wypłaty regułą SWR z portfela znormalizowanego do 1.0,
    począwszy od `start_month`, przez `horizon_years`. Wypłata w pierwszym
    miesiącu to `swr/12` wartości startowej; każdego stycznia jest
    podwyższana o zrealizowaną inflację GUS z poprzedniego roku (klasyczna
    reguła Bengena: stała kwota realna, nie stały % aktualnego salda).
    Zwrot portfela to ta sama ważona stopa equity/bond co w akumulacji
    (z TER), bez rozbicia na konta -- patrz docstring modułu.

    Zwraca `None`, jeśli w danych brakuje wystarczająco długiego ogona
    (mniej niż `horizon_years*12` miesięcy od `start_month`) -- takie okno
    jest pomijane w agregacji, nie liczone jako porażka.
    """
    data = _clean_decumulation_data(market_data)
    window = data[data.index >= start_month]

    horizon_months = horizon_years * 12
    if len(window) < horizon_months:
        return None
    window = window.iloc[:horizon_months]

    ter_monthly = assumptions.acwi_ter_annual / 12
    balance = 1.0
    min_balance = 1.0
    monthly_withdrawal = swr / 12.0
    current_year: int | None = None

    for month, row in window.iterrows():
        if month.year != current_year:
            if current_year is not None:
                inflation_last_year = (
                    data.loc[data.index.year == current_year, "cpi_prev_year_100"].iloc[-1] - 100.0
                ) / 100.0
                monthly_withdrawal *= 1.0 + inflation_last_year
            current_year = month.year

        balance -= monthly_withdrawal
        min_balance = min(min_balance, balance)
        if balance <= 0:
            return {"start_month": start_month, "survived": False, "ending_balance": 0.0, "min_balance": 0.0}

        equity_gross = (1 + row["acwi_monthly_return"]) * (1 + row["usd_pln_change"]) - 1
        bond_return = row["edo_reference_monthly_return"]
        blended_return = (
            assumptions.equity_weight * (equity_gross - ter_monthly) + assumptions.bond_weight * bond_return
        )
        balance *= 1.0 + blended_return
        min_balance = min(min_balance, balance)

    return {
        "start_month": start_month,
        "survived": True,
        "ending_balance": balance,
        "min_balance": min_balance,
    }


def run_rolling_decumulation(
    market_data: pd.DataFrame,
    assumptions: SimulationAssumptions,
    horizon_years: int,
    swr: float = 0.04,
    step_months: int = 6,
) -> pd.DataFrame:
    """Uruchamia `run_decumulation_window` dla wielu miesięcy startowych
    (co `step_months`), pomijając te bez wystarczająco długiego ogona
    danych. Zwraca DataFrame: jeden wiersz na okno (`start_month`,
    `survived`, `ending_balance`, `min_balance`)."""
    start_months = _clean_decumulation_data(market_data).index[::step_months]

    rows = []
    for start in start_months:
        result = run_decumulation_window(start, market_data, assumptions, horizon_years, swr)
        if result is not None:
            rows.append(result)

    return pd.DataFrame(rows)


def summarize_decumulation(results: pd.DataFrame) -> dict:
    """Agreguje wynik `run_rolling_decumulation`: wskaźnik sukcesu (% okien,
    w których portfel przetrwał cały horyzont), mediana/min salda końcowego
    wśród tych, które przetrwały, mediana najgłębszego obsunięcia (drawdown,
    liczone na wszystkich oknach -- nawet te, które ostatecznie przetrwały,
    mogły po drodze zejść nisko)."""
    if results.empty:
        return {
            "n_windows": 0,
            "success_rate": None,
            "ending_balance_median": None,
            "ending_balance_min": None,
            "min_balance_median": None,
        }
    survived = results[results["survived"]]
    return {
        "n_windows": len(results),
        "success_rate": len(survived) / len(results),
        "ending_balance_median": survived["ending_balance"].median() if len(survived) else None,
        "ending_balance_min": survived["ending_balance"].min() if len(survived) else None,
        "min_balance_median": results["min_balance"].median(),
    }


def run_all_decumulation(
    market_data: pd.DataFrame | None = None,
    allocations: dict[str, float] | None = None,
    horizons_years: tuple[int, ...] = DEFAULT_HORIZONS_YEARS,
    swr: float = 0.04,
    output_dir: Path = RESULTS_DIR,
) -> pd.DataFrame:
    """Uruchamia analizę dekumulacji dla każdej kombinacji alokacji x
    horyzontu, zapisuje `results/decumulation_summary.csv` i zwraca ją jako
    DataFrame (indeks: alokacja, horyzont)."""
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
            results = run_rolling_decumulation(market_data, assumptions, horizon, swr)
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
