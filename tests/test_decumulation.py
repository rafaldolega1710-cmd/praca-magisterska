"""Testy fazy dekumulacji (`src/decumulation.py`).

Tak jak w `test_simulation.py`, testy operują na małym, syntetycznym
`market_data` o kontrolowanych zwrotach -- nie na prawdziwych danych
historycznych.
"""

import pandas as pd
import pytest

from src.decumulation import (
    run_decumulation_window,
    run_rolling_decumulation,
    summarize_decumulation,
)
from src.simulation import SimulationAssumptions


def make_market_data(
    n_months: int = 24,
    start: str = "2020-01",
    acwi_return: float = 0.0,
    edo_return: float = 0.0,
    usd_pln: float = 4.0,
    cpi: float = 100.0,  # 100 = zerowa inflacja (rok poprzedni = 100)
) -> pd.DataFrame:
    index = pd.period_range(start=start, periods=n_months, freq="M")
    return pd.DataFrame(
        {
            "acwi_monthly_return": acwi_return,
            "usd_pln": usd_pln,
            "edo_reference_monthly_return": edo_return,
            "cpi_prev_year_100": cpi,
        },
        index=index,
    )


class TestRunDecumulationWindow:
    def test_insufficient_runway_returns_none(self):
        market_data = make_market_data(n_months=6)
        assumptions = SimulationAssumptions()
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1
        )
        assert result is None  # 6 miesiecy danych, potrzeba 12

    def test_survives_with_zero_returns_zero_inflation_matches_exact_withdrawal(self):
        market_data = make_market_data(n_months=12, acwi_return=0.0, edo_return=0.0, cpi=100.0)
        assumptions = SimulationAssumptions(equity_weight=0.8, bond_weight=0.2, acwi_ter_annual=0.0)
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1, swr=0.04
        )
        assert result is not None
        assert result["survived"] is True
        # brak wzrostu, brak inflacji -> saldo koncowe = 1 - 12*(0.04/12) = 0.96 dokladnie
        assert result["ending_balance"] == pytest.approx(0.96, abs=1e-9)

    def test_huge_swr_exhausts_portfolio(self):
        market_data = make_market_data(n_months=12, acwi_return=0.0, edo_return=0.0)
        assumptions = SimulationAssumptions()
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=1, swr=1.5
        )
        assert result is not None
        assert result["survived"] is False
        assert result["ending_balance"] == pytest.approx(0.0)
        assert result["min_balance"] == pytest.approx(0.0)

    def test_inflation_raises_withdrawal_each_january_not_mid_year(self):
        # 20% inflacji w pierwszym roku -- wyplata powinna wzrosnac dopiero
        # w 13. miesiacu (styczen kolejnego roku), nie wczesniej
        market_data = make_market_data(n_months=24, acwi_return=0.0, edo_return=0.0, cpi=120.0)
        assumptions = SimulationAssumptions(equity_weight=0.8, bond_weight=0.2, acwi_ter_annual=0.0)
        result = run_decumulation_window(
            market_data.index[0], market_data, assumptions, horizon_years=2, swr=0.04
        )
        # rok 1 (mies. 1-12): wyplacono 12*(0.04/12) = 0.04 -> saldo po roku 1 = 0.96
        # rok 2 (mies. 13-24): wyplata podniesiona o 20% (inflacja z roku 1) -> 0.04/12*1.2 miesiecznie
        expected = 0.96 - 12 * (0.04 / 12 * 1.2)
        assert result["ending_balance"] == pytest.approx(expected, abs=1e-9)


class TestRunRollingDecumulation:
    def test_skips_windows_without_enough_runway(self):
        market_data = make_market_data(n_months=24)
        assumptions = SimulationAssumptions()
        results = run_rolling_decumulation(
            market_data, assumptions, horizon_years=1, step_months=1
        )
        # 24 miesiace danych, horyzont 12 mies. -> tylko pierwsze 13 miesiecy
        # startowych ma wystarczajaco duzo miejsca (24-12=12, wiec starty 0..12)
        assert len(results) == 13
        assert set(results.columns) >= {"start_month", "survived", "ending_balance", "min_balance"}


class TestSummarizeDecumulation:
    def test_empty_results(self):
        summary = summarize_decumulation(pd.DataFrame())
        assert summary["n_windows"] == 0
        assert summary["success_rate"] is None

    def test_mixed_survival_computes_success_rate_and_medians(self):
        results = pd.DataFrame(
            [
                {"start_month": 1, "survived": True, "ending_balance": 1.2, "min_balance": 0.5},
                {"start_month": 2, "survived": True, "ending_balance": 0.8, "min_balance": 0.3},
                {"start_month": 3, "survived": False, "ending_balance": 0.0, "min_balance": 0.0},
            ]
        )
        summary = summarize_decumulation(results)
        assert summary["n_windows"] == 3
        assert summary["success_rate"] == pytest.approx(2 / 3)
        assert summary["ending_balance_median"] == pytest.approx(1.0)  # mediana z [1.2, 0.8]
        assert summary["ending_balance_min"] == pytest.approx(0.8)
        assert summary["min_balance_median"] == pytest.approx(0.3)  # mediana z [0.5, 0.3, 0.0]
