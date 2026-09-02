"""Generuje `data/calculator_data.json` -- prekalkulowaną siatkę wyników
akumulacji i dekumulacji, którą zasila interaktywny kalkulator (Artifact,
strona HTML). Ten sam wzorzec co kalkulator stockbroker.pl, na którym
częściowo wzorowana jest metodologia rolling-window: strona sama NIE liczy
symulacji na żywo (uniknięcie utrzymywania dwóch kopii logiki, Python i JS,
które mogłyby się rozjechać) -- tylko odpytuje wcześniej policzoną siatkę.

Siatka akumulacji: dla każdego archetypu, każdej możliwej kombinacji
włączonych kont podatkowych, każdej z 3 alokacji akcje/obligacje i każdej
z 9 stóp oszczędności (10%-90% co 10 p.p. -- patrz `SAVINGS_RATES` niżej),
wynik `run_rolling_accumulation` (mediana/min/max lat do FIRE, % okien bez
osiągniętego celu). Liczba kombinacji kont różni się między archetypami:
archetyp bez uprawnienia do PPK (B2B) ma PPK zablokowane przez
`Archetype.ppk_eligible` niezależnie od tego, czy "ppk" jest w
`enabled_accounts` (patrz `simulation.run_simulation`) -- więc liczenie
osobno wariantu z i bez PPK dla takiego archetypu dałoby identyczne wyniki
dwa razy. Zamiast tego dla archetypów bez PPK generowane są tylko warianty
kont {ike, ikze, oki} (2^3 = 8 kombinacji), a dla archetypów z PPK --
{ike, ikze, oki, ppk} (2^4 = 16). Strona kalkulatora replikuje tę samą
kanonizację klucza (patrz komentarz w JS), żeby zawsze trafiać w istniejący
wpis w siatce niezależnie od stanu checkboxa PPK dla archetypu bez PPK.

**Stopa oszczędności jako oddzielna, klikalna oś (nie stała cecha archetypu):**
`Archetype.savings_rate` w `scenarios.py` (50%/20%) pozostaje domyślnym
założeniem dla scenariuszy badawczych A1/A2/B1/B2 (`results/summary.csv`,
niezmienione w tym pliku) -- ale w kalkulatorze użytkownik ma suwak
10%-90%, więc siatka musi zawierać wynik dla każdej wartości osobno.
Realizowane przez `dataclasses.replace(archetype, savings_rate=sr)`:
dochód netto (`monthly_net_income`) archetypu zostaje bez zmian, zmienia
się tylko to, jaki jego procent trafia na inwestycje (i symetrycznie, jaki
zostaje na wydatki -- patrz `target = 25 * 12 * dochod * (1 - savings_rate)`
w `simulation.run_simulation`). Żadna zmiana w `simulation.py` nie była
potrzebna -- `savings_rate` był już polem dataclass, nie stałą wpisaną
w kod.

**Dekumulacja jest teraz sprzężona z konkretną kombinacją akumulacji**
(archetyp x konta x alokacja x stopa oszczędności), nie liczona osobno dla
samych alokacji jak we wcześniejszej wersji tego skryptu -- od kiedy
dekumulacja bramkuje IKE/IKZE/PPK wiekiem (`decumulation.py`), potrzebuje
wiedzieć, ILE kapitału jest w którym koncie i w jakim wieku dana kombinacja
w ogóle dochodzi do FIRE, a to zależy od wybranych kont. Reprezentatywny
wiek i podział kont na moment FIRE pochodzą z pojedynczej, ciągłej ścieżki
historycznej (`run_simulation` bez `start_month`) dla danej kombinacji --
ta sama logika co dla "wieku emeryta" jako parametru scenariusza w
klasycznych badaniach Bengena/Trinity (patrz docstring `decumulation.py`).
Jeśli ta ścieżka nie dochodzi do FIRE (np. niska stopa oszczędności),
kombinacja jest pomijana w siatce dekumulacji -- nie ma z czego wyprowadzić
wieku/podziału kont.

Horyzonty dekumulacji: `decumulation.DEFAULT_HORIZONS_YEARS` (10/15/20/25
lat -- 25 to maksimum, jakie mieści się w dostępnych danych; 30+ lat
świadomie pominięte, patrz docstring `decumulation.py`).
"""

from __future__ import annotations

import dataclasses
import itertools
import json
from pathlib import Path

import pandas as pd

from src.data_loader import build_processed_dataset
from src.decumulation import DEFAULT_HORIZONS_YEARS, run_rolling_decumulation, summarize_decumulation
from src.scenarios import ALLOCATIONS, ARCHETYPE_A, ARCHETYPE_B
from src.simulation import Archetype, SimulationAssumptions, run_rolling_accumulation, run_simulation

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# {kod archetypu w kalkulatorze: obiekt Archetype} -- te same definicje co w scenarios.py
CALCULATOR_ARCHETYPES: dict[str, Archetype] = {"A": ARCHETYPE_A, "B": ARCHETYPE_B}

TOGGLEABLE_ACCOUNTS = ("ike", "ikze", "oki")  # ppk dochodzi osobno, tylko gdy archetyp uprawniony

# 10%-90% co 10 p.p. -- zakres i krok wprost z prośby użytkownika ("od 10 do 90")
SAVINGS_RATES: tuple[float, ...] = tuple(r / 100 for r in range(10, 91, 10))


def _accounts_key(enabled_accounts: frozenset[str]) -> str:
    """Kanoniczny klucz tekstowy dla kombinacji kont, spójny z tym, co
    `run_simulation` zapisuje w podsumowaniu (`",".join(sorted(...))`)."""
    return ",".join(sorted(enabled_accounts)) if enabled_accounts else "none"


def _account_combinations(archetype: Archetype) -> list[frozenset[str]]:
    """Wszystkie kombinacje kont warte policzenia dla danego archetypu:
    2^3 (bez PPK) albo 2^4 (z PPK), zależnie od `ppk_eligible`."""
    accounts = TOGGLEABLE_ACCOUNTS + (("ppk",) if archetype.ppk_eligible else ())
    combos = []
    for r in range(len(accounts) + 1):
        for subset in itertools.combinations(accounts, r):
            combos.append(frozenset(subset))
    return combos


def build_grids(market_data: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Zwraca (wiersze_akumulacji, wiersze_dekumulacji) dla pełnej siatki --
    patrz docstring modułu co do sprzężenia obu."""
    accumulation_rows: list[dict] = []
    decumulation_rows: list[dict] = []

    for archetype_code, base_archetype in CALCULATOR_ARCHETYPES.items():
        account_combos = _account_combinations(base_archetype)
        for savings_rate in SAVINGS_RATES:
            archetype = dataclasses.replace(base_archetype, savings_rate=savings_rate)
            for enabled_accounts in account_combos:
                accounts_key = _accounts_key(enabled_accounts)
                for allocation_code, equity_weight in ALLOCATIONS.items():
                    assumptions = SimulationAssumptions(equity_weight=equity_weight, bond_weight=1 - equity_weight)

                    result = run_rolling_accumulation(archetype, market_data, enabled_accounts, assumptions)
                    accumulation_rows.append(
                        {
                            "archetype": archetype_code,
                            "accounts": accounts_key,
                            "allocation": allocation_code,
                            "equity_weight": equity_weight,
                            "savings_rate": round(savings_rate, 2),
                            "n_windows": result["n_windows"],
                            "pct_not_reached": round(result["pct_windows_not_reached"], 4),
                            "years_median": _round_or_none(result["years_to_fire_median"]),
                            "years_min": _round_or_none(result["years_to_fire_min"]),
                            "years_max": _round_or_none(result["years_to_fire_max"]),
                            "portfolio_median": _round_or_none(result["portfolio_at_fire_median"], 0),
                            "portfolio_min": _round_or_none(result["portfolio_at_fire_min"], 0),
                            "portfolio_max": _round_or_none(result["portfolio_at_fire_max"], 0),
                            "age_at_fire_median": _round_or_none(result["age_at_fire_median"], 1),
                        }
                    )

                    # reprezentatywny wiek/podzial kont z pojedynczej, ciaglej
                    # sciezki historycznej -- patrz docstring modulu
                    _, single_path = run_simulation(archetype, market_data, enabled_accounts, assumptions)
                    if not single_path["fire_reached"]:
                        continue
                    age_at_fire = single_path["age_at_fire"]
                    account_split = single_path["account_split_at_fire"]

                    for horizon in DEFAULT_HORIZONS_YEARS:
                        results = run_rolling_decumulation(
                            market_data,
                            assumptions,
                            horizon,
                            swr=0.04,
                            account_split=account_split,
                            start_age_at_fire=age_at_fire,
                        )
                        summary = summarize_decumulation(results)
                        decumulation_rows.append(
                            {
                                "archetype": archetype_code,
                                "accounts": accounts_key,
                                "allocation": allocation_code,
                                "savings_rate": round(savings_rate, 2),
                                "horizon_years": horizon,
                                "age_at_fire": round(age_at_fire, 2),
                                "n_windows": summary["n_windows"],
                                "success_rate": _round_or_none(summary["success_rate"]),
                                "ending_balance_median": _round_or_none(summary["ending_balance_median"]),
                                "ending_balance_min": _round_or_none(summary["ending_balance_min"]),
                                "min_balance_median": _round_or_none(summary["min_balance_median"]),
                                "n_failures_liquidity_gap": summary["n_failures_liquidity_gap"],
                                "n_failures_capital_exhausted": summary["n_failures_capital_exhausted"],
                            }
                        )

    return accumulation_rows, decumulation_rows


def _round_or_none(value, ndigits: int = 4):
    return None if value is None or pd.isna(value) else round(float(value), ndigits)


def build_calculator_data(
    market_data: pd.DataFrame | None = None,
    output_path: Path = DATA_DIR / "calculator_data.json",
) -> dict:
    if market_data is None:
        market_data = build_processed_dataset()

    from src.simulation import _clean_market_data

    cleaned = _clean_market_data(market_data)
    accumulation_rows, decumulation_rows = build_grids(market_data)

    payload = {
        "meta": {
            "data_range": f"{cleaned.index.min()} - {cleaned.index.max()}",
            "n_months": len(cleaned),
            "swr": 0.04,
            "decumulation_horizons": list(DEFAULT_HORIZONS_YEARS),
        },
        "archetypes": {
            code: {
                "name": archetype.name,
                "ppk_eligible": archetype.ppk_eligible,
                "monthly_net_income": archetype.monthly_net_income,
                "savings_rate": archetype.savings_rate,
                "start_age": archetype.start_age,
            }
            for code, archetype in CALCULATOR_ARCHETYPES.items()
        },
        "accumulation": accumulation_rows,
        "decumulation": decumulation_rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build_calculator_data()
    print(f"accumulation: {len(result['accumulation'])} wierszy")
    print(f"decumulation: {len(result['decumulation'])} wierszy")
