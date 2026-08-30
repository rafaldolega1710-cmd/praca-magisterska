"""Definicje czterech scenariuszy badawczych (podrozdz. 3.4 pracy / sekcja 4
`fire_model_spec.md`) oraz uruchomienie ich wszystkich przez `simulation.run_simulation`.

Macierz: 2 archetypy (Informatyk B2B, Rodzina 2+2) x 2 warianty (z/bez
wehikułów podatkowych) = A1, A2, B1, B2. Każdy z nich uruchamiany jest
dodatkowo w 3 wariantach alokacji akcje/obligacje (80/20, 60/40, 40/60) --
to jest właśnie "elastyczna alokacja aktywów" z hipotezy badawczej pracy
(portfel akcyjny to ACWI, obligacyjny to wyłącznie polskie detaliczne EDO,
bez globalnych obligacji -- na wyraźną decyzję użytkownika).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_loader import build_processed_dataset
from src.simulation import Archetype, SimulationAssumptions, run_simulation

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
)

# {kod scenariusza: (archetyp, use_tax_vehicles)}
SCENARIOS: dict[str, tuple[Archetype, bool]] = {
    "A1": (ARCHETYPE_A, True),   # z programami -- pełna kaskada PPK/IKZE/IKE/OKI
    "A2": (ARCHETYPE_A, False),  # bez programów -- 100% nadwyżki na rachunek standardowy
    "B1": (ARCHETYPE_B, True),
    "B2": (ARCHETYPE_B, False),
}

# Warianty alokacji akcje/obligacje testowane dla każdego scenariusza --
# "elastyczna alokacja aktywów" z hipotezy badawczej (podrozdz. 4.2 spec).
ALLOCATIONS: dict[str, float] = {"80_20": 0.80, "60_40": 0.60, "40_60": 0.40}


def run_all_scenarios(
    market_data: pd.DataFrame | None = None,
    output_dir: Path = RESULTS_DIR,
) -> pd.DataFrame:
    """Uruchamia wszystkie 4 scenariusze x 3 warianty alokacji (12 przebiegów
    łącznie) na tych samych danych rynkowych, zapisuje pełną miesięczną
    ścieżkę każdego do `results/scenario_{kod}_equity{waga}_monthly.csv`
    oraz zbiorcze podsumowanie do `results/summary.csv`. Zwraca DataFrame
    podsumowania (jeden wiersz na kombinację scenariusz x alokacja) --
    zestaw metryk z sekcji 7 spec ("Co dalej"): czy i kiedy osiągnięto FIRE,
    wartość końcowa portfela, skumulowany tax drag.
    """
    if market_data is None:
        market_data = build_processed_dataset()

    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for code, (archetype, use_tax_vehicles) in SCENARIOS.items():
        for allocation_code, equity_weight in ALLOCATIONS.items():
            assumptions = SimulationAssumptions(equity_weight=equity_weight, bond_weight=1 - equity_weight)
            ledger, summary = run_simulation(archetype, market_data, use_tax_vehicles, assumptions)
            ledger.to_csv(output_dir / f"scenario_{code}_equity{allocation_code}_monthly.csv")
            summary["scenario"] = code
            summary["allocation"] = allocation_code
            summaries.append(summary)

    summary_df = pd.DataFrame(summaries).set_index(["scenario", "allocation"])
    summary_df.to_csv(output_dir / "summary.csv")
    return summary_df


if __name__ == "__main__":
    result = run_all_scenarios()
    print(result)
