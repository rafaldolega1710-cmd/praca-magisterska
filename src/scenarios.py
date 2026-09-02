"""Definicje czterech scenariuszy badawczych (podrozdz. 3.4 pracy / sekcja 4
`fire_model_spec.md`) oraz uruchomienie ich wszystkich przez `simulation.py`.

Macierz: 2 archetypy (Informatyk B2B, Rodzina 2+2) x 2 warianty (z/bez
wehikułów podatkowych) = A1, A2, B1, B2. Każdy z nich uruchamiany jest
dodatkowo w 3 wariantach alokacji akcje/obligacje (80/20, 60/40, 40/60) --
to jest właśnie "elastyczna alokacja aktywów" z hipotezy badawczej pracy
(portfel akcyjny to ACWI, obligacyjny to wyłącznie polskie detaliczne EDO,
bez globalnych obligacji -- na wyraźną decyzję użytkownika).

Etap 4: każda kombinacja liczona jest DWOMA metodami naraz --
`run_simulation` (jedna, ciągła ścieżka historyczna, jak we wcześniejszych
etapach -- zostaje jako ilustracyjna, pełna miesięczna trajektoria do
`results/scenario_*_monthly.csv`) oraz `run_rolling_accumulation` (wiele
okien startowych, metodologia Bengena/Trinity Study -- mediana/min/max lat
do FIRE, odporne na to, że akurat trafiliśmy na któryś konkretny rok).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_loader import build_processed_dataset
from src.simulation import (
    ALL_ACCOUNTS,
    NO_ACCOUNTS,
    Archetype,
    SimulationAssumptions,
    run_rolling_accumulation,
    run_simulation,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"

# Archetyp A: samodzielny specjalista IT na kontrakcie B2B (podrozdz. 3.4)
# ~19 000 zł netto/mies., stopa oszczędności 50%, podatek liniowy 19%,
# limit IKZE 1,8x (dział. gosp.), brak PPK (brak automatycznego zapisu dla B2B).
ARCHETYPE_A = Archetype(
    name="Informatyk B2B",
    monthly_net_income=19_000.0,
    savings_rate=0.50,
    employment_form="b2b",
    marginal_tax_rate=0.19,
    ppk_eligible=False,
    household_multiplier=1,
    start_age=30,  # zaczyna oszczedzac na starcie kariery -- patrz README, "Zalozenia modelu"
)

# Archetyp B: rodzina 2+2, oboje rodzice na UoP (podrozdz. 3.4)
# 13 000 zł netto łącznie/mies., stopa oszczędności 20%, limit IKZE 1,2x,
# PPK aktywne dla obojga (household_multiplier=2 -> podwójne roczne limity
# IKE/IKZE/PPK), zakładana skala podatkowa 12% (dochód poniżej progu).
ARCHETYPE_B = Archetype(
    name="Rodzina 2+2",
    monthly_net_income=13_000.0,
    savings_rate=0.20,
    employment_form="uop",
    marginal_tax_rate=0.12,
    ppk_eligible=True,
    household_multiplier=2,
    start_age=30,  # ten sam wiek startowy co archetyp A -- porownywalne scenariusze
)

# {kod scenariusza: (archetyp, enabled_accounts)}
SCENARIOS: dict[str, tuple[Archetype, frozenset[str]]] = {
    "A1": (ARCHETYPE_A, ALL_ACCOUNTS),  # z programami -- pełna kaskada IKZE/IKE/OKI (PPK niedostępne dla B2B)
    "A2": (ARCHETYPE_A, NO_ACCOUNTS),   # bez programów -- 100% nadwyżki na rachunek standardowy
    "B1": (ARCHETYPE_B, ALL_ACCOUNTS),
    "B2": (ARCHETYPE_B, NO_ACCOUNTS),
}

# Warianty alokacji akcje/obligacje testowane dla każdego scenariusza --
# "elastyczna alokacja aktywów" z hipotezy badawczej (podrozdz. 4.2 spec).
ALLOCATIONS: dict[str, float] = {"80_20": 0.80, "60_40": 0.60, "40_60": 0.40}


def run_all_scenarios(
    market_data: pd.DataFrame | None = None,
    output_dir: Path = RESULTS_DIR,
) -> pd.DataFrame:
    """Uruchamia wszystkie 4 scenariusze x 3 warianty alokacji (12 kombinacji
    łącznie) na tych samych danych rynkowych, dwoma metodami na raz:

    - `run_simulation` (jedna, ciągła historyczna ścieżka) -- zapisuje pełną
      miesięczną trajektorię do `results/scenario_{kod}_equity{waga}_monthly.csv`,
      przydatną do wykresów/ilustracji.
    - `run_rolling_accumulation` (wiele okien startowych) -- mediana/min/max
      lat do FIRE, odporne na wybór konkretnego roku startowego.

    Zapisuje zbiorcze podsumowanie (obie metody, jeden wiersz na kombinację
    scenariusz x alokacja) do `results/summary.csv` i zwraca je jako DataFrame.
    """
    if market_data is None:
        market_data = build_processed_dataset()

    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for code, (archetype, enabled_accounts) in SCENARIOS.items():
        for allocation_code, equity_weight in ALLOCATIONS.items():
            assumptions = SimulationAssumptions(equity_weight=equity_weight, bond_weight=1 - equity_weight)

            ledger, single_path_summary = run_simulation(archetype, market_data, enabled_accounts, assumptions)
            ledger.to_csv(output_dir / f"scenario_{code}_equity{allocation_code}_monthly.csv")

            rolling_summary = run_rolling_accumulation(archetype, market_data, enabled_accounts, assumptions)

            row = {
                "scenario": code,
                "allocation": allocation_code,
                "archetype": archetype.name,
                "enabled_accounts": single_path_summary["enabled_accounts"],
                "equity_weight": equity_weight,
                "single_path_fire_reached": single_path_summary["fire_reached"],
                "single_path_years_to_fire": single_path_summary["years_to_fire"],
                "single_path_final_value": single_path_summary["final_portfolio_value"],
                "single_path_age_at_fire": single_path_summary["age_at_fire"],
                "single_path_cumulative_dividend_tax": single_path_summary["cumulative_dividend_tax"],
                "single_path_cumulative_rebalancing_tax": single_path_summary["cumulative_rebalancing_tax"],
                "rolling_n_windows": rolling_summary["n_windows"],
                "rolling_pct_not_reached": rolling_summary["pct_windows_not_reached"],
                "years_to_fire_median": rolling_summary["years_to_fire_median"],
                "years_to_fire_min": rolling_summary["years_to_fire_min"],
                "years_to_fire_max": rolling_summary["years_to_fire_max"],
                # kapital i wiek, z ktorym poszczegolne okna konczyly akumulacje
                # (start_age=30 dla obu archetypow -- patrz Archetype.start_age)
                "portfolio_at_fire_median": rolling_summary["portfolio_at_fire_median"],
                "portfolio_at_fire_min": rolling_summary["portfolio_at_fire_min"],
                "portfolio_at_fire_max": rolling_summary["portfolio_at_fire_max"],
                "age_at_fire_median": rolling_summary["age_at_fire_median"],
                "age_at_fire_min": rolling_summary["age_at_fire_min"],
                "age_at_fire_max": rolling_summary["age_at_fire_max"],
            }
            summaries.append(row)

    summary_df = pd.DataFrame(summaries).set_index(["scenario", "allocation"])
    summary_df.to_csv(output_dir / "summary.csv")
    return summary_df


if __name__ == "__main__":
    result = run_all_scenarios()
    print(result)
